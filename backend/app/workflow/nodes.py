"""Catálogo de tipos de nó + executores.

Para adicionar um nó novo:
  1. registre a definição em NODE_TYPES (campos aparecem automaticamente no editor);
  2. implemente o executor e registre em EXECUTORS.

Os campos de texto aceitam variáveis {{...}} (ver template.py).
"""
import re
from dataclasses import dataclass, field
from typing import Callable

from app.services import instagram_service, meta_client, openai_service
from app.workflow import conditions
from app.workflow.template import render, truncate_utf8

MESSAGE_MAX_BYTES = 1000  # limite oficial do texto de mensagens no Instagram
MAX_DELAY_SECONDS = 23 * 3600  # abaixo da janela de 24h para responder DMs
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,39}$")

MESSAGE_TRIGGER = "trigger.message_received"
COMMENT_TRIGGER = "trigger.comment_received"
NEW_CONTACT_TRIGGER = "trigger.new_contact"
STORY_MENTION_TRIGGER = "trigger.story_mention"
STORY_REPLY_TRIGGER = "trigger.story_reply"
IG_ME_LINK_TRIGGER = "trigger.ig_me_link"
MESSAGE_REACTION_TRIGGER = "trigger.message_reaction"
LIVE_COMMENT_TRIGGER = "trigger.live_comment"

# Gatilhos originados em conversa de DM: a resposta por DM é permitida (janela de 24h)
DM_TRIGGERS = [MESSAGE_TRIGGER, NEW_CONTACT_TRIGGER, STORY_MENTION_TRIGGER, STORY_REPLY_TRIGGER,
               IG_ME_LINK_TRIGGER, MESSAGE_REACTION_TRIGGER]

_text_help = "Aceita variáveis como {{contact.username}}, {{message.text}}, {{ai.response}}, {{vars.nome}}."

NODE_TYPES: dict[str, dict] = {
    # ----- gatilhos -----
    MESSAGE_TRIGGER: {
        "category": "trigger",
        "label": "Mensagem recebida",
        "description": "Dispara quando alguém envia uma DM para a conta conectada.",
        "outputs": ["default"],
        "fields": [],
        "variables": ["message.text", "contact.username", "contact.name", "contact.id"],
    },
    COMMENT_TRIGGER: {
        "category": "trigger",
        "label": "Comentário recebido",
        "description": "Dispara quando alguém comenta em uma publicação/reel da conta. "
                       "Exige Advanced Access e conta pública.",
        "outputs": ["default"],
        "fields": [
            {"name": "media_id", "label": "ID da publicação (opcional)", "type": "text", "required": False,
             "help": "Deixe vazio para disparar em qualquer publicação."},
        ],
        "variables": ["comment.text", "comment.id", "comment.media_id", "contact.username"],
    },
    NEW_CONTACT_TRIGGER: {
        "category": "trigger",
        "label": "Novo contato",
        "description": "Dispara na primeira mensagem de alguém que nunca falou com a conta (boas-vindas). "
                       "A Meta não informa novos seguidores; esta é a alternativa oficial.",
        "outputs": ["default"],
        "fields": [],
        "variables": ["message.text", "contact.username", "contact.name", "contact.id"],
    },
    STORY_MENTION_TRIGGER: {
        "category": "trigger",
        "label": "Menção no story",
        "description": "Dispara quando alguém marca a conta em um story.",
        "outputs": ["default"],
        "fields": [],
        "variables": ["story.url", "contact.username", "contact.name"],
    },
    STORY_REPLY_TRIGGER: {
        "category": "trigger",
        "label": "Resposta ao story",
        "description": "Dispara quando alguém responde um story da conta por DM. Sem workflow deste tipo, "
                       "a resposta segue para os workflows de \"Mensagem recebida\".",
        "outputs": ["default"],
        "fields": [],
        "variables": ["message.text", "story.id", "story.url", "contact.username"],
    },
    IG_ME_LINK_TRIGGER: {
        "category": "trigger",
        "label": "Link ig.me",
        "description": "Dispara quando a conversa é aberta por um link ig.me/sua_conta?ref=ORIGEM "
                       "(bio, anúncio, QR code).",
        "outputs": ["default"],
        "fields": [
            {"name": "ref", "label": "Referência (opcional)", "type": "text", "required": False,
             "max_length": 100, "help": "Só dispara para este ref (ex.: promo). Vazio = qualquer link."},
        ],
        "variables": ["referral.ref", "referral.source", "message.text", "contact.username"],
    },
    MESSAGE_REACTION_TRIGGER: {
        "category": "trigger",
        "label": "Reação a mensagem",
        "description": "Dispara quando alguém reage (ex.: ❤️) a uma mensagem da conta.",
        "outputs": ["default"],
        "fields": [],
        "variables": ["reaction.emoji", "reaction.type", "contact.username"],
    },
    LIVE_COMMENT_TRIGGER: {
        "category": "trigger",
        "label": "Comentário em live",
        "description": "Dispara com comentários durante uma transmissão ao vivo. A Meta só permite "
                       "responder por DM (resposta privada) e enquanto a live está no ar.",
        "outputs": ["default"],
        "fields": [],
        "variables": ["comment.text", "comment.id", "contact.username"],
    },
    # ----- ações -----
    "action.send_message": {
        "category": "action",
        "label": "Enviar mensagem (DM)",
        "description": "Responde por DM. A Meta só permite responder até 24h após a última mensagem do usuário.",
        "outputs": ["default"],
        "allowed_triggers": DM_TRIGGERS,
        "fields": [
            {"name": "text", "label": "Mensagem", "type": "textarea", "required": True, "max_length": 1000,
             "help": _text_help},
        ],
    },
    "action.private_reply": {
        "category": "action",
        "label": "Responder comentário por DM",
        "description": "Envia uma DM para quem comentou (resposta privada oficial). Só 1 por comentário, até 7 dias.",
        "outputs": ["default"],
        "allowed_triggers": [COMMENT_TRIGGER, LIVE_COMMENT_TRIGGER],
        "fields": [
            {"name": "text", "label": "Mensagem", "type": "textarea", "required": True, "max_length": 1000,
             "help": _text_help},
        ],
    },
    "action.reply_comment": {
        "category": "action",
        "label": "Responder comentário publicamente",
        "description": "Publica uma resposta visível no comentário.",
        "outputs": ["default"],
        "allowed_triggers": [COMMENT_TRIGGER],
        "fields": [
            {"name": "text", "label": "Resposta", "type": "textarea", "required": True, "max_length": 1000,
             "help": _text_help},
        ],
    },
    "action.delay": {
        "category": "action",
        "label": "Esperar",
        "description": "Pausa o fluxo antes de continuar (processado em segundo plano).",
        "outputs": ["default"],
        "fields": [
            {"name": "seconds", "label": "Segundos", "type": "number", "required": True, "default": 30,
             "min": 1, "max": MAX_DELAY_SECONDS,
             "help": "Máximo de 23h: depois de 24h a Meta não permite mais responder a DM."},
        ],
    },
    "action.ai": {
        "category": "action",
        "label": "IA (OpenAI)",
        "description": "Gera um texto com IA e salva em {{ai.response}} e {{vars.<nome>}}.",
        "outputs": ["default"],
        "fields": [
            {"name": "instructions", "label": "Instruções (system prompt)", "type": "textarea", "required": True,
             "max_length": 4000, "default": "Você é um atendente simpático. Responda em português, em até 3 frases."},
            {"name": "input", "label": "Entrada", "type": "textarea", "required": True, "max_length": 4000,
             "default": "{{message.text}}", "help": "Somente este texto é enviado à OpenAI. " + _text_help},
            {"name": "model", "label": "Modelo (opcional)", "type": "text", "required": False,
             "help": "Vazio = modelo padrão das Configurações."},
            {"name": "temperature", "label": "Temperatura (opcional)", "type": "number", "required": False,
             "min": 0, "max": 2, "step": 0.1, "help": "Ignorada por modelos que não suportam."},
            {"name": "max_output_tokens", "label": "Máx. de tokens na resposta", "type": "number",
             "required": False, "min": 16, "max": 4000, "default": 400},
            {"name": "save_as", "label": "Salvar em variável", "type": "text", "required": True,
             "default": "resposta_ia", "pattern": "identifier"},
        ],
    },
    "action.set_variable": {
        "category": "action",
        "label": "Definir variável",
        "description": "Cria ou altera uma variável do fluxo ({{vars.nome}}).",
        "outputs": ["default"],
        "fields": [
            {"name": "name", "label": "Nome", "type": "text", "required": True, "pattern": "identifier"},
            {"name": "value", "label": "Valor", "type": "textarea", "required": False, "max_length": 2000,
             "help": _text_help},
            {"name": "mode", "label": "Modo", "type": "select", "required": True, "default": "set",
             "options": [{"value": "set", "label": "Substituir"}, {"value": "append", "label": "Acrescentar ao final"}]},
        ],
    },
    "action.end": {
        "category": "action",
        "label": "Finalizar",
        "description": "Encerra o workflow.",
        "outputs": [],
        "fields": [],
    },
    # ----- condições -----
    "condition.check": {
        "category": "condition",
        "label": "Condição",
        "description": "Segue pelo caminho Sim ou Não.",
        "outputs": ["true", "false"],
        "fields": [
            {"name": "left", "label": "Valor verificado", "type": "text", "required": True,
             "default": "{{message.text}}", "help": _text_help},
            {"name": "operator", "label": "Operador", "type": "select", "required": True, "default": "contains",
             "options": [{"value": k, "label": v} for k, v in conditions.OPERATORS.items()]},
            {"name": "value", "label": "Comparar com", "type": "text", "required": False, "max_length": 1000},
            {"name": "case_sensitive", "label": "Diferenciar maiúsculas/acentos", "type": "checkbox",
             "required": False, "default": False},
        ],
    },
}


def catalog() -> list[dict]:
    return [{"type": t, **d} for t, d in NODE_TYPES.items()]


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

class NodeError(Exception):
    """Falha esperada na execução de um nó (mensagem legível para o usuário)."""


@dataclass
class NodeResult:
    message: str
    handle: str = "default"
    delay_seconds: int | None = None
    stop: bool = False
    output: dict = field(default_factory=dict)


@dataclass
class Runtime:
    user_id: str
    account_id: str
    execution_id: str
    dry_run: bool = False  # eventos simulados: nada é enviado ao Instagram
    _token: str | None = None

    def token(self) -> str:
        if self._token is None:
            self._token = instagram_service.get_access_token(self.account_id)
        return self._token


# Nós que enviam algo ao Instagram (no modo simulado, apenas registram o que seria enviado)
SENDING_NODES = {"action.send_message", "action.private_reply", "action.reply_comment"}


def _meta_call(runtime: Runtime, fn: Callable, *args) -> dict:
    if runtime.dry_run:
        return {"simulated": True}
    try:
        return fn(runtime.token(), *args)
    except meta_client.MetaApiError as exc:
        if exc.is_token_error:
            instagram_service.mark_token_invalid(runtime.account_id, exc.message)
            raise NodeError("A conexão com o Instagram expirou ou foi revogada. Reconecte a conta.") from exc
        raise NodeError(f"Falha ao enviar para a Meta: {exc.message}") from exc


def _message_text(config: dict, ctx: dict, max_bytes: int = MESSAGE_MAX_BYTES) -> tuple[str, bool]:
    text = render(config.get("text"), ctx).strip()
    if not text:
        raise NodeError("O texto da mensagem ficou vazio após substituir as variáveis.")
    truncated = truncate_utf8(text, max_bytes)
    return truncated, truncated != text


def exec_send_message(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    recipient = (ctx.get("contact") or {}).get("ig_id")
    if not recipient:
        raise NodeError("Contato sem ID do Instagram para envio.")
    text, truncated = _message_text(config, ctx)
    resp = _meta_call(rt, meta_client.send_text_message, recipient, text)
    return NodeResult("Mensagem enviada.", output={"text": text, "truncated": truncated,
                                                   "message_id": resp.get("message_id")})


def exec_private_reply(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    comment_id = (ctx.get("comment") or {}).get("id")
    if not comment_id:
        raise NodeError("Evento sem comentário para responder.")
    if ctx.get("_sys", {}).get("private_reply_sent"):
        raise NodeError("A Meta permite apenas uma resposta privada por comentário.")
    text, truncated = _message_text(config, ctx)
    resp = _meta_call(rt, meta_client.send_private_reply, comment_id, text)
    ctx.setdefault("_sys", {})["private_reply_sent"] = True
    return NodeResult("Resposta privada enviada.", output={"text": text, "truncated": truncated,
                                                           "message_id": resp.get("message_id")})


def exec_reply_comment(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    comment_id = (ctx.get("comment") or {}).get("id")
    if not comment_id:
        raise NodeError("Evento sem comentário para responder.")
    text, truncated = _message_text(config, ctx)
    resp = _meta_call(rt, meta_client.reply_to_comment, comment_id, text)
    return NodeResult("Comentário respondido.", output={"text": text, "truncated": truncated,
                                                        "reply_id": resp.get("id")})


def exec_delay(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    seconds = int(config.get("seconds") or 0)
    seconds = max(1, min(seconds, MAX_DELAY_SECONDS))
    return NodeResult(f"Aguardando {seconds}s.", delay_seconds=seconds, output={"seconds": seconds})


def exec_ai(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    model = (config.get("model") or "").strip() or ctx.get("_sys", {}).get("ai_default_model") \
        or openai_service.default_model()
    input_text = render(config.get("input") or "{{message.text}}", ctx).strip()
    if not input_text:
        raise NodeError("A entrada da IA ficou vazia após substituir as variáveis.")
    temperature = config.get("temperature")
    max_tokens = config.get("max_output_tokens")
    try:
        result = openai_service.generate_text(
            model=model,
            instructions=render(config.get("instructions"), ctx),
            input_text=input_text,
            temperature=float(temperature) if temperature not in (None, "") else None,
            max_output_tokens=int(max_tokens) if max_tokens not in (None, "") else None,
        )
    except openai_service.OpenAIServiceError as exc:
        raise NodeError(str(exc)) from exc
    if not result["text"]:
        raise NodeError("A IA retornou uma resposta vazia.")
    save_as = config.get("save_as") or "resposta_ia"
    ctx.setdefault("ai", {})["response"] = result["text"]
    ctx.setdefault("vars", {})[save_as] = result["text"]
    return NodeResult("Resposta da IA gerada.", output={"model": result["model"], "usage": result["usage"],
                                                        "response_preview": result["text"][:300]})


def exec_set_variable(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    name = config.get("name") or ""
    if not IDENTIFIER_RE.match(name):
        raise NodeError("Nome de variável inválido.")
    value = render(config.get("value"), ctx)
    variables = ctx.setdefault("vars", {})
    if config.get("mode") == "append":
        value = f"{variables.get(name, '')}{value}"
    variables[name] = value[:4000]
    return NodeResult(f"Variável '{name}' definida.", output={"name": name, "value": value[:300]})


def exec_condition(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    left = render(config.get("left"), ctx)
    right = render(config.get("value"), ctx)
    try:
        passed = conditions.evaluate(left, config.get("operator", ""), right, bool(config.get("case_sensitive")))
    except ValueError as exc:
        raise NodeError(str(exc)) from exc
    return NodeResult(
        "Condição verdadeira (Sim)." if passed else "Condição falsa (Não).",
        handle="true" if passed else "false",
        output={"left": left[:300], "operator": config.get("operator"), "value": right[:300], "result": passed},
    )


def exec_end(config: dict, ctx: dict, rt: Runtime) -> NodeResult:
    return NodeResult("Workflow finalizado.", stop=True)


EXECUTORS: dict[str, Callable[[dict, dict, Runtime], NodeResult]] = {
    "action.send_message": exec_send_message,
    "action.private_reply": exec_private_reply,
    "action.reply_comment": exec_reply_comment,
    "action.delay": exec_delay,
    "action.ai": exec_ai,
    "action.set_variable": exec_set_variable,
    "action.end": exec_end,
    "condition.check": exec_condition,
}
