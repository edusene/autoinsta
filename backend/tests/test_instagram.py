import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

from app import db
from app.services import meta_client
from tests.conftest import TestConfig

SCOPES = "instagram_business_basic,instagram_business_manage_messages,instagram_business_manage_comments"


def start_connect(user) -> str:
    url = user.get("/api/instagram/connect").get_json()["data"]["authorize_url"]
    parsed = urlparse(url)
    assert parsed.netloc == "www.instagram.com" and parsed.path == "/oauth/authorize"
    params = parse_qs(parsed.query)
    assert params["client_id"] == ["123"]
    assert params["response_type"] == ["code"]
    assert params["scope"] == [SCOPES]
    assert params["redirect_uri"] == [TestConfig.META_REDIRECT_URI]
    return params["state"][0]


def mock_oauth(meta_mock, ig_user_id="17840000000000009", account_type="BUSINESS", permissions=SCOPES):
    meta_mock.set("exchange_code", {"access_token": "IGshort", "user_id": ig_user_id, "permissions": permissions})
    meta_mock.set("exchange_long_lived", {"access_token": "IGAAlonglivedtoken", "token_type": "bearer",
                                          "expires_in": 5183944})
    meta_mock.set("get_me", {"user_id": ig_user_id, "username": "loja_teste", "name": "Loja",
                             "account_type": account_type})


def test_connect_flow(user, meta_mock):
    state = start_connect(user)
    mock_oauth(meta_mock)
    resp = user.post("/api/instagram/callback", json={"code": "AQBx#_", "state": state})
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]
    assert data["connected"] is True
    assert data["account"]["username"] == "loja_teste"
    assert data["account"]["webhook_subscribed"] is True

    # "#_" removido do code
    assert meta_mock.named("exchange_code")[0][1] == ("AQBx",)
    # webhooks assinados com o token longo
    assert meta_mock.named("subscribe_webhooks")[0][1][0] == "IGAAlonglivedtoken"

    # token nunca aparece na API e está criptografado no banco
    assert "IGAAlonglivedtoken" not in json.dumps(user.get("/api/instagram/status").get_json())
    assert "IGAAlonglivedtoken" not in json.dumps(user.get("/api/settings").get_json())
    with db.connection() as conn:
        row = conn.execute("select access_token_encrypted from oauth_tokens").fetchone()
    assert "IGAAlonglivedtoken" not in row["access_token_encrypted"]


def test_state_from_another_user_is_rejected(user, other_user, meta_mock):
    state = start_connect(user)
    mock_oauth(meta_mock)
    resp = other_user.post("/api/instagram/callback", json={"code": "abc", "state": state})
    assert resp.status_code == 403
    assert meta_mock.named("exchange_code") == []


def test_tampered_state_is_rejected(user, meta_mock):
    resp = user.post("/api/instagram/callback", json={"code": "abc", "state": "forjado.123"})
    assert resp.get_json()["error"]["code"] == "OAUTH_STATE_INVALID"


def test_missing_permissions(user, meta_mock):
    state = start_connect(user)
    mock_oauth(meta_mock, permissions="instagram_business_basic")
    resp = user.post("/api/instagram/callback", json={"code": "abc", "state": state})
    body = resp.get_json()["error"]
    assert body["code"] == "INSTAGRAM_PERMISSIONS_MISSING"
    assert "instagram_business_manage_messages" in body["details"]["missing"]


def test_personal_account_rejected(user, meta_mock):
    state = start_connect(user)
    mock_oauth(meta_mock, account_type="PERSONAL")
    resp = user.post("/api/instagram/callback", json={"code": "abc", "state": state})
    assert resp.get_json()["error"]["code"] == "INSTAGRAM_NOT_PROFESSIONAL"


def test_account_linked_to_another_user(user, other_user, meta_mock):
    mock_oauth(meta_mock)
    assert user.post("/api/instagram/callback", json={"code": "a", "state": start_connect(user)}).status_code == 200
    resp = other_user.post("/api/instagram/callback", json={"code": "b", "state": start_connect(other_user)})
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "INSTAGRAM_ALREADY_LINKED"


def test_meta_error_during_oauth(user, meta_mock):
    state = start_connect(user)
    meta_mock.set("exchange_code", meta_client.MetaApiError("Invalid code", status=400, code=100))
    resp = user.post("/api/instagram/callback", json={"code": "abc", "state": state})
    assert resp.status_code == 502
    assert resp.get_json()["error"]["code"] == "INSTAGRAM_AUTH_FAILED"


def test_webhook_subscription_failure_is_reported(user, meta_mock):
    state = start_connect(user)
    mock_oauth(meta_mock)
    meta_mock.set("subscribe_webhooks", meta_client.MetaApiError("Permissions error", status=403, code=200))
    data = user.post("/api/instagram/callback", json={"code": "abc", "state": state}).get_json()["data"]
    assert data["connected"] is True and data["account"]["webhook_subscribed"] is False


def test_disconnect_removes_token(user, connected_account):
    data = user.post("/api/instagram/disconnect").get_json()["data"]
    assert data == {"connected": False, "status": "disconnected", "account": None}
    with db.connection() as conn:
        assert conn.execute("select count(*) as n from oauth_tokens").fetchone()["n"] == 0


def test_diagnostics(user, connected_account, meta_mock):
    meta_mock.set("get_me", {"user_id": "17840000000000001", "username": "minhaloja", "account_type": "BUSINESS"})
    data = user.get("/api/instagram/diagnostics").get_json()["data"]
    checks = {c["key"]: c["status"] for c in data["checks"]}
    assert checks["platform_config"] == "ok"
    assert checks["account_connected"] == "ok"
    assert checks["token_valid"] == "ok"
    assert checks["permissions"] == "ok"
    assert checks["webhook_subscribed"] == "ok"
    assert checks["webhook_received"] == "warning"  # nenhum evento ainda


def test_diagnostics_not_connected(user):
    data = user.get("/api/instagram/diagnostics").get_json()["data"]
    assert data["healthy"] is False
    assert {c["key"]: c["status"] for c in data["checks"]}["account_connected"] == "error"


def test_meta_not_configured(user, app):
    original = app.config["META_APP_ID"]
    app.config["META_APP_ID"] = ""
    try:
        resp = user.get("/api/instagram/connect")
        assert resp.status_code == 503
        assert resp.get_json()["error"]["code"] == "META_NOT_CONFIGURED"
    finally:
        app.config["META_APP_ID"] = original


def test_token_refresh_job(user, connected_account, meta_mock):
    meta_mock.set("refresh_long_lived", {"access_token": "IGAArefreshed", "expires_in": 5183944})
    with db.connection() as conn:
        conn.execute("update oauth_tokens set expires_at = now() + interval '5 days', "
                     "last_refreshed_at = now() - interval '50 days'")
    from app.services import instagram_service, token_service
    assert instagram_service.refresh_expiring_tokens() == 1
    assert token_service.decrypt(
        db_token()) == "IGAArefreshed"


def db_token():
    with db.connection() as conn:
        return conn.execute("select access_token_encrypted from oauth_tokens").fetchone()["access_token_encrypted"]


def _signed_request(payload: dict, secret: str = TestConfig.META_APP_SECRET) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{sig}.{body}"


def test_deauthorize_callback(client, user, connected_account):
    sr = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "17840000000000001"})
    assert client.post("/webhooks/meta/deauthorize", data={"signed_request": sr}).status_code == 200
    assert user.get("/api/instagram/status").get_json()["data"]["connected"] is False

    bad = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "1"}, secret="wrong")
    assert client.post("/webhooks/meta/deauthorize", data={"signed_request": bad}).status_code == 400


def test_data_deletion_callback(client, user, connected_account):
    sr = _signed_request({"algorithm": "HMAC-SHA256", "user_id": "17840000000000001"})
    resp = client.post("/webhooks/meta/data-deletion", data={"signed_request": sr})
    body = resp.get_json()
    assert resp.status_code == 200 and body["confirmation_code"] and body["url"].startswith("http")
    with db.connection() as conn:
        assert conn.execute("select count(*) as n from instagram_accounts").fetchone()["n"] == 0
