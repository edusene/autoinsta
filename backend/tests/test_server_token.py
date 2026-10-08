"""Conexão com token gerado no painel da Meta (sem OAuth)."""
import json

import pytest

from app import db
from app.services import meta_client

TOKEN = "IGAApaineltoken0000000000000000"
IG_ID = "17841400000000077"


@pytest.fixture
def server_token(app):
    keys = {"INSTAGRAM_ACCESS_TOKEN": TOKEN, "INSTAGRAM_ACCOUNT_ID": IG_ID,
            "INSTAGRAM_TOKEN_OWNER_EMAIL": "alice@example.com"}
    original = {k: app.config[k] for k in keys}
    app.config.update(keys)
    yield app
    app.config.update(original)


@pytest.fixture
def me_ok(meta_mock):
    meta_mock.set("get_me", {"id": "app-scoped-1", "user_id": IG_ID, "username": "loja_painel",
                             "account_type": "BUSINESS"})
    return meta_mock


def test_status_shows_option_only_for_owner(user, other_user, server_token):
    assert user.get("/api/instagram/status").get_json()["data"]["connect_options"]["server_token"] is True
    assert other_user.get("/api/instagram/status").get_json()["data"]["connect_options"]["server_token"] is False


def test_owner_connects_with_server_token(user, server_token, me_ok):
    resp = user.post("/api/instagram/connect-token")
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]
    assert data["connected"] is True
    assert data["account"]["username"] == "loja_painel"
    assert data["account"]["connection_method"] == "server_token"
    # webhooks assinados com o token do painel; token nunca exposto e criptografado no banco
    assert me_ok.named("subscribe_webhooks")[0][1][0] == TOKEN
    assert TOKEN not in json.dumps(data)
    with db.connection() as conn:
        assert TOKEN not in conn.execute("select access_token_encrypted from oauth_tokens").fetchone()[
            "access_token_encrypted"]


def test_other_user_cannot_use_server_token(other_user, server_token, me_ok):
    resp = other_user.post("/api/instagram/connect-token")
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "SERVER_TOKEN_FORBIDDEN"
    assert me_ok.named("get_me") == []


def test_not_configured(user):
    resp = user.post("/api/instagram/connect-token")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "SERVER_TOKEN_NOT_CONFIGURED"


def test_account_id_mismatch(user, server_token, meta_mock):
    meta_mock.set("get_me", {"id": "x", "user_id": "999", "username": "outra", "account_type": "BUSINESS"})
    resp = user.post("/api/instagram/connect-token")
    assert resp.get_json()["error"]["code"] == "INSTAGRAM_ACCOUNT_MISMATCH"


def test_rejected_token(user, server_token, meta_mock):
    meta_mock.set("get_me", meta_client.MetaApiError("Invalid OAuth access token", status=400, code=190))
    resp = user.post("/api/instagram/connect-token")
    assert resp.status_code == 502
    assert resp.get_json()["error"]["code"] == "INSTAGRAM_TOKEN_INVALID"


def test_works_without_oauth_secret_and_redirect(user, server_token, me_ok, app):
    """Modo token não depende da chave secreta do Instagram nem da URL de redirecionamento."""
    original = {k: app.config[k] for k in ("META_REDIRECT_URI",)}
    app.config["META_REDIRECT_URI"] = ""
    try:
        assert user.post("/api/instagram/connect-token").status_code == 200
        assert user.get("/api/instagram/status").get_json()["data"]["connect_options"]["oauth"] is False
        checks = {c["key"]: c for c in user.get("/api/instagram/diagnostics").get_json()["data"]["checks"]}
        assert checks["platform_config"]["status"] == "ok"
        assert checks["permissions"]["status"] == "warning"  # não verificáveis em tokens do painel
    finally:
        app.config.update(original)


def test_webhook_rejected_without_any_secret(client, app):
    original = (app.config["META_APP_SECRET"], app.config["META_WEBHOOK_EXTRA_SECRETS"])
    app.config["META_APP_SECRET"], app.config["META_WEBHOOK_EXTRA_SECRETS"] = "", []
    try:
        resp = client.post("/webhooks/meta", data=b"{}", content_type="application/json",
                           headers={"X-Hub-Signature-256": "sha256=abc"})
        assert resp.status_code == 403
    finally:
        app.config["META_APP_SECRET"], app.config["META_WEBHOOK_EXTRA_SECRETS"] = original
