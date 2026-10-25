"""Cliente HTTP para a Instagram API with Instagram Login (APIs oficiais da Meta).

Somente endpoints confirmados na documentação oficial (Graph API v25.0):
  - POST https://api.instagram.com/oauth/access_token           (code -> token curto)
  - GET  https://graph.instagram.com/access_token               (token curto -> longo, 60 dias)
  - GET  https://graph.instagram.com/refresh_access_token       (renova token longo)
  - GET  https://graph.instagram.com/{v}/me                     (perfil profissional)
  - POST https://graph.instagram.com/{v}/me/subscribed_apps     (ativa webhooks da conta)
  - POST https://graph.instagram.com/{v}/me/messages            (DM, resposta privada, botões e respostas rápidas)
  - POST https://graph.instagram.com/{v}/{comment_id}/replies   (resposta pública)
  - GET  https://graph.instagram.com/{v}/{igsid}                (perfil do contato)

Tokens e segredos nunca são registrados em log.
"""
import logging
from urllib.parse import urlencode

import requests
from flask import current_app

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_HOST = "https://graph.instagram.com"
TIMEOUT = 15

# Permissões mínimas para o MVP (nomes atuais; os antigos "business_*" foram descontinuados).
REQUIRED_SCOPES = [
    "instagram_business_basic",
    "instagram_business_manage_messages",
    "instagram_business_manage_comments",
]
# messages também traz menções e respostas a stories; os demais alimentam os outros gatilhos
# messaging_postbacks: cliques nos botões (template de botões)
WEBHOOK_FIELDS = ["messages", "comments", "messaging_referral", "message_reactions", "live_comments",
                  "messaging_postbacks"]

# Códigos de erro da Graph API que indicam token inválido/expirado/revogado.
TOKEN_ERROR_CODES = {190}


class MetaApiError(Exception):
    def __init__(self, message: str, status: int | None = None, code: int | None = None,
                 subcode: int | None = None, fbtrace_id: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.subcode = subcode
        self.fbtrace_id = fbtrace_id

    @property
    def is_token_error(self) -> bool:
        return self.code in TOKEN_ERROR_CODES

    def __str__(self) -> str:
        return f"Meta API erro (status={self.status}, code={self.code}, subcode={self.subcode}): {self.message}"


def _version() -> str:
    return current_app.config["META_GRAPH_API_VERSION"]


def _handle(resp: requests.Response, action: str) -> dict:
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.ok and "error" not in body:
        return body
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    message = err.get("message") or body.get("error_message") or resp.text[:300] or "erro desconhecido"
    exc = MetaApiError(
        message=message,
        status=resp.status_code,
        code=err.get("code") or body.get("code"),
        subcode=err.get("error_subcode"),
        fbtrace_id=err.get("fbtrace_id"),
    )
    logger.warning("Falha na Meta ao %s: %s (fbtrace_id=%s)", action, exc, exc.fbtrace_id)
    raise exc


def _request(method: str, url: str, action: str, token: str | None = None, **kwargs) -> dict:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        logger.warning("Erro de rede com a Meta ao %s: %s", action, type(exc).__name__)
        raise MetaApiError(f"Erro de rede ao comunicar com a Meta ({type(exc).__name__}).") from exc
    return _handle(resp, action)


# --- OAuth ------------------------------------------------------------------

def build_authorize_url(state: str) -> str:
    cfg = current_app.config
    params = {
        "client_id": cfg["META_APP_ID"],
        "redirect_uri": cfg["META_REDIRECT_URI"],
        "response_type": "code",
        "scope": ",".join(REQUIRED_SCOPES),
        "state": state,
        # Login pedido dentro do fluxo OAuth: sem isso o Instagram pode parar no feed após o login
        "force_reauth": "true",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Retorna {access_token, user_id, permissions} (token curto, 1h)."""
    cfg = current_app.config
    body = _request(
        "POST",
        TOKEN_URL,
        "trocar código OAuth",
        data={
            "client_id": cfg["META_APP_ID"],
            "client_secret": cfg["META_APP_SECRET"],
            "grant_type": "authorization_code",
            "redirect_uri": cfg["META_REDIRECT_URI"],
            "code": code,
        },
    )
    # A documentação mostra {"data": [{...}]}; aceitamos também o formato plano.
    if isinstance(body.get("data"), list) and body["data"]:
        body = body["data"][0]
    if not body.get("access_token"):
        raise MetaApiError("Resposta da Meta sem access_token.")
    return body


def exchange_long_lived(short_token: str) -> dict:
    """Retorna {access_token, token_type, expires_in} (token longo, ~60 dias)."""
    return _request(
        "GET",
        f"{GRAPH_HOST}/access_token",
        "obter token de longa duração",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": current_app.config["META_APP_SECRET"],
            "access_token": short_token,
        },
    )


def refresh_long_lived(token: str) -> dict:
    return _request(
        "GET",
        f"{GRAPH_HOST}/refresh_access_token",
        "renovar token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )


# --- Graph API --------------------------------------------------------------

def get_me(token: str) -> dict:
    return _request(
        "GET",
        f"{GRAPH_HOST}/{_version()}/me",
        "ler perfil da conta",
        token=token,
        params={"fields": "user_id,username,name,account_type,profile_picture_url"},
    )


def get_subscribed_fields(token: str) -> list[str]:
    """Campos de webhook que a conta tem assinados para este app."""
    body = _request("GET", f"{GRAPH_HOST}/{_version()}/me/subscribed_apps", "ler assinatura de webhooks", token=token)
    fields: list[str] = []
    for entry in body.get("data") or []:
        fields += [str(f) for f in entry.get("subscribed_fields") or []]
    return fields


def subscribe_webhooks(token: str, fields: list[str] | None = None) -> dict:
    return _request(
        "POST",
        f"{GRAPH_HOST}/{_version()}/me/subscribed_apps",
        "assinar webhooks",
        token=token,
        params={"subscribed_fields": ",".join(fields or WEBHOOK_FIELDS)},
    )


def send_text_message(token: str, recipient_igsid: str, text: str) -> dict:
    """DM para quem mandou mensagem nas últimas 24h."""
    return _request(
        "POST",
        f"{GRAPH_HOST}/{_version()}/me/messages",
        "enviar mensagem",
        token=token,
        json={"recipient": {"id": recipient_igsid}, "message": {"text": text}},
    )


def send_button_template(token: str, recipient_igsid: str, text: str, buttons: list[dict]) -> dict:
    """Template de botões: 1 a 3 botões (web_url ou postback), texto de até 640 caracteres."""
    return _request(
        "POST",
        f"{GRAPH_HOST}/{_version()}/me/messages",
        "enviar mensagem com botões",
        token=token,
        json={"recipient": {"id": recipient_igsid}, "message": {"attachment": {"type": "template", "payload": {
            "template_type": "button", "text": text, "buttons": buttons}}}},
    )


def send_quick_replies(token: str, recipient_igsid: str, text: str, replies: list[dict]) -> dict:
    """Respostas rápidas: até 13 opções de texto (título de até 20 caracteres)."""
    return _request(
        "POST",
        f"{GRAPH_HOST}/{_version()}/me/messages",
        "enviar respostas rápidas",
        token=token,
        json={"recipient": {"id": recipient_igsid}, "message": {"text": text, "quick_replies": replies}},
    )


def send_private_reply(token: str, comment_id: str, text: str) -> dict:
    """Resposta privada (DM) a um comentário: 1 por comentário, até 7 dias."""
    return _request(
        "POST",
        f"{GRAPH_HOST}/{_version()}/me/messages",
        "enviar resposta privada",
        token=token,
        json={"recipient": {"comment_id": comment_id}, "message": {"text": text}},
    )


def reply_to_comment(token: str, comment_id: str, text: str) -> dict:
    return _request(
        "POST",
        f"{GRAPH_HOST}/{_version()}/{comment_id}/replies",
        "responder comentário",
        token=token,
        params={"message": text},
    )


def get_user_profile(token: str, igsid: str, fields: str = "name,username") -> dict:
    """Só funciona após o usuário enviar mensagem (consentimento).

    Campos úteis: name, username, is_user_follow_business (a pessoa segue a conta).
    """
    return _request(
        "GET",
        f"{GRAPH_HOST}/{_version()}/{igsid}",
        "ler perfil do contato",
        token=token,
        params={"fields": fields},
    )
