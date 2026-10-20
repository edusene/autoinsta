"""Envio de DMs pela plataforma (workflows, caixa de entrada e disparos).

Toda mensagem enviada passa por aqui para:
  - ficar registrada na conversa (tabela messages);
  - ter os links trocados por links rastreados (/r/<código>) quando o CTR está ligado;
  - montar botões (template de botões ou respostas rápidas) com um payload que identifica a mensagem,
    para o clique voltar ao fluxo certo e contar no CTR.
"""
import logging
import re
import secrets
import uuid

from flask import current_app

from app import db
from app.repositories import contact_repository, message_repository
from app.services import meta_client
from app.workflow.template import truncate_utf8

logger = logging.getLogger(__name__)

MESSAGE_MAX_BYTES = 1000      # texto de DM / respostas rápidas
TEMPLATE_TEXT_MAX_CHARS = 640  # texto do template de botões
MAX_TEMPLATE_BUTTONS = 3
MAX_QUICK_REPLIES = 13
BUTTON_TITLE_MAX = 20
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
TRAILING_PUNCTUATION = ".,;:!?)]}"
BUTTON_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

# Payload dos botões: "ai1:<id da mensagem>:<id do botão>"
PAYLOAD_PREFIX = "ai1"


def build_payload(message_id: str, button_id: str) -> str:
    return f"{PAYLOAD_PREFIX}:{message_id}:{button_id}"


def parse_payload(payload: str | None) -> tuple[str, str] | None:
    parts = str(payload or "").split(":")
    if len(parts) != 3 or parts[0] != PAYLOAD_PREFIX:
        return None
    try:
        message_id = str(uuid.UUID(parts[1]))
    except ValueError:
        return None
    return (message_id, parts[2]) if BUTTON_ID_RE.match(parts[2]) else None


def tracked_url(code: str) -> str:
    return f"{current_app.config['PUBLIC_URL']}/r/{code}"


def _new_code() -> str:
    return secrets.token_urlsafe(6)


def _track_text(text: str, links: list[tuple[str, str]]) -> str:
    """Troca cada URL do texto por um link rastreado (acumula (código, url) em links)."""
    def replace(match: re.Match) -> str:
        raw = match.group(0)
        url = raw.rstrip(TRAILING_PUNCTUATION)
        if len(url) > 2000:
            return raw
        code = _new_code()
        links.append((code, url))
        return tracked_url(code) + raw[len(url):]
    return URL_RE.sub(replace, text)


def validate_buttons(buttons, style: str) -> list[str]:
    """Problemas na lista de botões (vazia = válida). style: buttons | quick_replies."""
    if not isinstance(buttons, list) or not buttons:
        return ["Adicione pelo menos um botão."]
    limit = MAX_QUICK_REPLIES if style == "quick_replies" else MAX_TEMPLATE_BUTTONS
    problems = []
    if len(buttons) > limit:
        problems.append(f"Use no máximo {limit} botões neste estilo.")
    seen = set()
    for i, b in enumerate(buttons, start=1):
        if not isinstance(b, dict):
            problems.append(f"Botão {i} inválido.")
            continue
        title = str(b.get("title") or "").strip()
        kind = b.get("type") or "reply"
        if not BUTTON_ID_RE.match(str(b.get("id") or "")) or b.get("id") in seen:
            problems.append(f"Botão {i}: identificador inválido ou repetido.")
        seen.add(b.get("id"))
        if not title:
            problems.append(f"Botão {i}: preencha o texto do botão.")
        elif len(title) > BUTTON_TITLE_MAX:
            problems.append(f"Botão {i}: o texto deve ter até {BUTTON_TITLE_MAX} caracteres.")
        if kind not in ("reply", "url"):
            problems.append(f"Botão {i}: tipo inválido.")
        elif kind == "url":
            if style == "quick_replies":
                problems.append(f"Botão {i}: respostas rápidas não aceitam link (use o estilo 'Botões').")
            elif not re.match(r"^https?://\S+$", str(b.get("url") or "").strip(), re.I) \
                    and "{{" not in str(b.get("url") or ""):
                problems.append(f"Botão {i}: informe um link começando com https://.")
    return problems


def send(
    *, token: str, user_id: str, account_id: str, contact_id: str | None, text: str,
    recipient_igsid: str | None = None, comment_id: str | None = None,
    buttons: list[dict] | None = None, style: str = "text", track_links: bool = False,
    source: str = "workflow", workflow_id: str | None = None, node_id: str | None = None,
    execution_id: str | None = None, broadcast_id: str | None = None,
) -> dict:
    """Envia a DM e registra na conversa. Retorna {message_id, mid, text, truncated}.

    comment_id: resposta privada a um comentário (só texto).
    style: text | buttons (template, até 3 botões) | quick_replies (até 13 respostas).
    Erros da Meta são relançados (MetaApiError) depois de a mensagem ser marcada como falha.
    """
    buttons = list(buttons or [])
    if style == "text":
        buttons = []
    message_id = str(uuid.uuid4())
    links: list[tuple[str, str]] = []

    final_text = _track_text(text, links) if track_links else text
    # Links rastreados podem alongar o texto: se passar do limite, envia os links originais
    if style == "buttons":
        if len(final_text) > TEMPLATE_TEXT_MAX_CHARS:
            final_text, links = text, []
        truncated = len(final_text) > TEMPLATE_TEXT_MAX_CHARS
        final_text = final_text[:TEMPLATE_TEXT_MAX_CHARS]
    else:
        if truncate_utf8(final_text, MESSAGE_MAX_BYTES) != final_text:
            final_text, links = text, []
        cut = truncate_utf8(final_text, MESSAGE_MAX_BYTES)
        truncated, final_text = cut != final_text, cut

    meta_buttons = []
    for b in buttons:
        title = str(b.get("title") or "")[:BUTTON_TITLE_MAX]
        if (b.get("type") or "reply") == "url":
            url = str(b.get("url") or "").strip()
            if track_links:
                code = _new_code()
                links.append((code, url))
                url = tracked_url(code)
            meta_buttons.append({"type": "web_url", "url": url, "title": title})
        elif style == "quick_replies":
            meta_buttons.append({"content_type": "text", "title": title,
                                 "payload": build_payload(message_id, b["id"])})
        else:
            meta_buttons.append({"type": "postback", "title": title, "payload": build_payload(message_id, b["id"])})

    trackable = bool(links) or any((b.get("type") or "reply") == "reply" for b in buttons)
    stored_buttons = [{"id": b.get("id"), "title": b.get("title"), "type": b.get("type") or "reply",
                       **({"url": b.get("url")} if b.get("url") else {})} for b in buttons]

    if contact_id:
        with db.connection() as conn:
            message_repository.insert_outbound(
                conn, message_id=message_id, user_id=user_id, account_id=account_id, contact_id=contact_id,
                source=source, kind=style, text=text, buttons=stored_buttons, trackable=trackable,
                workflow_id=workflow_id, node_id=node_id, execution_id=execution_id, broadcast_id=broadcast_id,
            )
            for code, url in links:
                message_repository.add_link(conn, user_id, message_id, code, url)

    try:
        if comment_id:
            resp = meta_client.send_private_reply(token, comment_id, final_text)
        elif style == "buttons":
            resp = meta_client.send_button_template(token, recipient_igsid, final_text, meta_buttons)
        elif style == "quick_replies":
            resp = meta_client.send_quick_replies(token, recipient_igsid, final_text, meta_buttons)
        else:
            resp = meta_client.send_text_message(token, recipient_igsid, final_text)
    except meta_client.MetaApiError as exc:
        if contact_id:
            with db.connection() as conn:
                message_repository.mark_failed(conn, message_id, exc.message)
        raise

    mid = resp.get("message_id")
    if contact_id:
        with db.connection() as conn:
            message_repository.mark_sent(conn, message_id, account_id, mid)
            contact_repository.touch_outbound(conn, contact_id, text)
    return {"message_id": message_id, "mid": mid, "text": final_text, "truncated": truncated,
            "tracked_links": len(links)}
