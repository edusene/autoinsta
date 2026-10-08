"""Regras de negócio da conexão com o Instagram (OAuth, tokens, diagnóstico)."""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app import db
from app.errors import AppError
from app.repositories import instagram_repository as repo
from app.repositories import webhook_event_repository
from app.services import meta_client, token_service
from app.services.meta_client import MetaApiError

logger = logging.getLogger(__name__)

STATE_MAX_AGE_SECONDS = 600
PROFESSIONAL_TYPES = {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}
REFRESH_WITHIN_DAYS = 15


# --- configuração -----------------------------------------------------------

def missing_platform_config() -> list[str]:
    cfg = current_app.config
    keys = ["META_APP_ID", "META_APP_SECRET", "META_REDIRECT_URI", "META_VERIFY_TOKEN", "TOKEN_ENCRYPTION_KEY"]
    return [k for k in keys if not cfg.get(k)]


def _ensure_configured() -> None:
    missing = missing_platform_config()
    if missing:
        logger.error("Integração Meta sem configuração: %s", ", ".join(missing))
        raise AppError(
            "META_NOT_CONFIGURED",
            "A integração com o Instagram ainda não foi configurada pelo administrador da plataforma.",
            503,
        )


# --- OAuth ------------------------------------------------------------------

def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="instagram-oauth-state")


def build_connect_url(user_id: str) -> str:
    _ensure_configured()
    state = _serializer().dumps({"uid": user_id, "n": secrets.token_urlsafe(16)})
    return meta_client.build_authorize_url(state)


def _verify_state(state: str, user_id: str) -> None:
    try:
        data = _serializer().loads(state, max_age=STATE_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise AppError("OAUTH_STATE_EXPIRED", "A autorização expirou. Clique em Conectar novamente.")
    except BadSignature:
        raise AppError("OAUTH_STATE_INVALID", "Retorno de autorização inválido. Tente conectar novamente.")
    # O state precisa pertencer ao usuário logado que concluiu o fluxo (anti-CSRF).
    if data.get("uid") != user_id:
        raise AppError("OAUTH_STATE_INVALID", "Esta autorização foi iniciada por outra sessão.", 403)


def _parse_permissions(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return []


def complete_connection(user_id: str, code: str, state: str) -> dict:
    _ensure_configured()
    _verify_state(state, user_id)
    code = code.strip().removesuffix("#_")  # o "#_" anexado pelo Instagram não faz parte do código
    if not code:
        raise AppError("OAUTH_CODE_MISSING", "Código de autorização ausente.")

    try:
        short = meta_client.exchange_code(code)
        permissions = _parse_permissions(short.get("permissions"))
        if permissions:
            missing = [s for s in meta_client.REQUIRED_SCOPES if s not in permissions]
            if missing:
                raise AppError(
                    "INSTAGRAM_PERMISSIONS_MISSING",
                    "Algumas permissões não foram concedidas. Conecte novamente e aceite todas as permissões.",
                    details={"missing": missing},
                )
        else:
            permissions = list(meta_client.REQUIRED_SCOPES)
        long = meta_client.exchange_long_lived(short["access_token"])
        token = long["access_token"]
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(long.get("expires_in") or 0))
        profile = meta_client.get_me(token)
    except MetaApiError as exc:
        raise AppError(
            "INSTAGRAM_AUTH_FAILED",
            "Não foi possível concluir a autorização com o Instagram. Tente novamente.",
            502,
            details={"meta_message": exc.message},
        ) from exc

    if not profile.get("user_id"):
        raise AppError("INSTAGRAM_AUTH_FAILED", "A Meta não retornou o ID da conta.", 502)
    account_type = str(profile.get("account_type") or "").upper()
    if account_type and account_type not in PROFESSIONAL_TYPES:
        raise AppError(
            "INSTAGRAM_NOT_PROFESSIONAL",
            "Somente contas profissionais (Empresa ou Criador de conteúdo) podem ser conectadas.",
        )

    with db.connection() as conn:
        existing = repo.get_by_ig_user_id(conn, str(profile["user_id"]))
        if existing and str(existing["user_id"]) != user_id and existing["status"] == "connected":
            raise AppError(
                "INSTAGRAM_ALREADY_LINKED",
                "Esta conta do Instagram já está conectada a outro usuário da plataforma.",
                409,
            )
        # MVP: uma conta por usuário — desconecta outra conta anterior, se houver.
        previous = repo.get_connected_for_user(conn, user_id)
        if previous and previous["ig_user_id"] != str(profile["user_id"]):
            repo.delete_token(conn, previous["id"])
            repo.set_status(conn, previous["id"], "disconnected")

        account = repo.upsert_connected(conn, user_id, {**profile, "user_id": str(profile["user_id"])}, permissions)
        repo.save_token(conn, account["id"], user_id, token_service.encrypt(token), expires_at)

    _subscribe(account["id"], token)
    logger.info("Instagram conectado: account=%s user=%s", account["id"], user_id)
    return get_status(user_id)


def _subscribe(account_id: str, token: str) -> bool:
    try:
        meta_client.subscribe_webhooks(token)
    except MetaApiError as exc:
        with db.connection() as conn:
            repo.set_webhook_subscribed(conn, account_id, False, f"Falha ao ativar webhooks: {exc.message}")
        return False
    with db.connection() as conn:
        repo.set_webhook_subscribed(conn, account_id, True)
    return True


def resubscribe(user_id: str) -> dict:
    account = _require_connected(user_id)
    ok = _subscribe(account["id"], get_access_token(account["id"]))
    if not ok:
        raise AppError("WEBHOOK_SUBSCRIBE_FAILED", "Não foi possível ativar os webhooks. Veja o diagnóstico.", 502)
    return get_status(user_id)


def disconnect(user_id: str) -> dict:
    with db.connection() as conn:
        account = repo.get_for_user(conn, user_id)
        if not account:
            raise AppError("INSTAGRAM_NOT_CONNECTED", "Instagram não conectado.", 404)
        repo.delete_token(conn, account["id"])
        repo.set_status(conn, account["id"], "disconnected")
    logger.info("Instagram desconectado: account=%s user=%s", account["id"], user_id)
    return get_status(user_id)


# --- leitura ----------------------------------------------------------------

def get_status(user_id: str) -> dict:
    with db.connection() as conn:
        account = repo.get_for_user(conn, user_id)
        token = repo.get_token(conn, account["id"]) if account else None
    if not account or account["status"] == "disconnected":
        return {"connected": False, "status": "disconnected", "account": None}
    return {
        "connected": account["status"] == "connected",
        "status": account["status"],
        "account": {
            "id": account["id"],
            "username": account["username"],
            "name": account["name"],
            "account_type": account["account_type"],
            "profile_picture_url": account["profile_picture_url"],
            "webhook_subscribed": account["webhook_subscribed"],
            "last_webhook_at": account["last_webhook_at"],
            "connected_at": account["connected_at"],
            "token_expires_at": token["expires_at"] if token else None,
            "last_error": account["last_error"],
        },
    }


def _require_connected(user_id: str) -> dict:
    with db.connection() as conn:
        account = repo.get_connected_for_user(conn, user_id)
    if not account:
        raise AppError("INSTAGRAM_NOT_CONNECTED", "Instagram não conectado.", 409)
    return account


def get_access_token(account_id: str) -> str:
    with db.connection() as conn:
        row = repo.get_token(conn, account_id)
    if not row:
        raise AppError("INSTAGRAM_NOT_CONNECTED", "Instagram não conectado.", 409)
    if row["expires_at"] and row["expires_at"] <= datetime.now(timezone.utc):
        mark_token_invalid(account_id, "Token expirado.")
        raise AppError("INSTAGRAM_TOKEN_EXPIRED", "A conexão com o Instagram expirou. Reconecte a conta.", 409)
    return token_service.decrypt(row["access_token_encrypted"])


def mark_token_invalid(account_id: str, reason: str) -> None:
    with db.connection() as conn:
        repo.set_status(conn, account_id, "token_expired", reason)
    logger.warning("Token inválido para account=%s: %s", account_id, reason)


# --- diagnóstico ------------------------------------------------------------

def diagnostics(user_id: str) -> dict:
    checks: list[dict] = []

    def add(key: str, label: str, ok: bool | None, detail: str = "") -> None:
        checks.append({"key": key, "label": label, "status": "ok" if ok else ("warning" if ok is None else "error"),
                       "detail": detail})

    missing = missing_platform_config()
    add("platform_config", "Configuração da plataforma (Meta App)", not missing,
        f"Variáveis ausentes no servidor: {', '.join(missing)}" if missing else "")

    with db.connection() as conn:
        account = repo.get_for_user(conn, user_id)
        token_row = repo.get_token(conn, account["id"]) if account else None
        recent_events = webhook_event_repository.count_recent_for_account(conn, account["id"]) if account else 0

    connected = bool(account and account["status"] == "connected")
    add("account_connected", "Conta conectada", connected,
        "" if connected else ("Conexão expirada — clique em Reconectar." if account and account["status"] == "token_expired"
                              else "Clique em Conectar Instagram."))

    if connected and token_row:
        try:
            token = token_service.decrypt(token_row["access_token_encrypted"])
            me = meta_client.get_me(token)
            add("token_valid", "Token válido", True,
                f"Expira em {token_row['expires_at']:%d/%m/%Y}" if token_row["expires_at"] else "")
            account_type = str(me.get("account_type") or "").upper()
            add("professional_account", "Conta profissional", account_type in PROFESSIONAL_TYPES or None,
                account_type or "Tipo de conta não informado pela Meta.")
        except MetaApiError as exc:
            if exc.is_token_error:
                mark_token_invalid(account["id"], exc.message)
            add("token_valid", "Token válido", False, exc.message)
        except AppError as exc:
            add("token_valid", "Token válido", False, exc.message)

        perms = set(account["permissions"] or [])
        missing_perms = [s for s in meta_client.REQUIRED_SCOPES if s not in perms]
        add("permissions", "Permissões verificadas", not missing_perms,
            f"Faltando: {', '.join(missing_perms)}" if missing_perms else ", ".join(sorted(perms)))

        add("webhook_subscribed", "Webhook configurado", account["webhook_subscribed"],
            "Campos: messages, comments" if account["webhook_subscribed"]
            else (account["last_error"] or "Clique em 'Reativar webhooks'."))

        if account["last_webhook_at"]:
            add("webhook_received", "Eventos recebidos", True,
                f"Último evento: {account['last_webhook_at']:%d/%m/%Y %H:%M} UTC · {recent_events} nas últimas 24h")
        else:
            add("webhook_received", "Eventos recebidos", None,
                "Nenhum evento recebido ainda. Envie uma DM de teste para a conta conectada. "
                "Se não chegar, confira a URL de callback do webhook no painel da Meta e o modo do app (Live).")

    return {"healthy": all(c["status"] == "ok" for c in checks), "checks": checks}


# --- manutenção (worker) ----------------------------------------------------

def refresh_expiring_tokens() -> int:
    with db.connection() as conn:
        rows = repo.list_tokens_to_refresh(conn, REFRESH_WITHIN_DAYS)
    refreshed = 0
    for row in rows:
        account_id = row["instagram_account_id"]
        try:
            data = meta_client.refresh_long_lived(token_service.decrypt(row["access_token_encrypted"]))
        except MetaApiError as exc:
            if exc.is_token_error:
                mark_token_invalid(account_id, exc.message)
            continue
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in") or 0))
        with db.connection() as conn:
            account = repo.get_by_id(conn, account_id)
            repo.save_token(conn, account_id, account["user_id"], token_service.encrypt(data["access_token"]), expires_at)
        refreshed += 1
    if rows:
        logger.info("Tokens renovados: %s de %s", refreshed, len(rows))
    return refreshed


# --- callbacks da Meta (deauthorize / data deletion) ------------------------

def handle_deauthorize(ig_user_id: str) -> None:
    with db.connection() as conn:
        account = repo.get_by_ig_user_id(conn, ig_user_id)
        if account:
            repo.delete_token(conn, account["id"])
            repo.set_status(conn, account["id"], "disconnected", "Acesso removido pelo usuário no Instagram.")
    logger.info("Deauthorize recebido para ig_user_id=%s (conta encontrada: %s)", ig_user_id, bool(account))


def handle_data_deletion(ig_user_id: str) -> str:
    """Remove a conta e os dados ligados a ela (tokens, contatos, eventos de contato)."""
    with db.connection() as conn:
        repo.delete_by_ig_user_id(conn, ig_user_id)
    code = secrets.token_hex(8)
    logger.info("Exclusão de dados concluída para ig_user_id=%s (code=%s)", ig_user_id, code)
    return code
