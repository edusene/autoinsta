import uuid

from app import db
from tests.conftest import make_token


def test_missing_token_returns_401(client):
    resp = client.get("/api/workflows")
    assert resp.status_code == 401
    assert resp.get_json() == {"success": False,
                               "error": {"code": "UNAUTHORIZED", "message": "Autenticação necessária."}}


def test_invalid_and_tampered_tokens(client):
    assert client.get("/api/workflows", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    forged = make_token(str(uuid.uuid4())) + "x"
    assert client.get("/api/workflows", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token(client):
    token = make_token(str(uuid.uuid4()), expires_in=-10)
    resp = client.get("/api/workflows", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expirada" in resp.get_json()["error"]["message"]


def test_wrong_audience_or_role_rejected(client):
    uid = str(uuid.uuid4())
    for token in (make_token(uid, aud="other"), make_token(uid, role="anon"), make_token(uid, iss="https://evil/auth/v1")):
        assert client.get("/api/workflows", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_me_creates_profile(user):
    resp = user.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["email"] == "alice@example.com"
    with db.connection() as conn:
        assert conn.execute("select count(*) as n from profiles where id = %s", (user.id,)).fetchone()["n"] == 1


def test_users_cannot_access_each_others_data(user, other_user):
    created = user.post("/api/workflows", json={"name": "Privado"}).get_json()["data"]
    wid = created["id"]
    other_user.get("/api/auth/me")
    assert other_user.get(f"/api/workflows/{wid}").status_code == 404
    assert other_user.put(f"/api/workflows/{wid}", json={"name": "hack"}).status_code == 404
    assert other_user.delete(f"/api/workflows/{wid}").status_code == 404
    assert other_user.post(f"/api/workflows/{wid}/activate").status_code == 404
    assert other_user.get(f"/api/workflows/{wid}/executions").status_code == 404
    assert other_user.get("/api/workflows").get_json()["data"] == []
    assert user.get(f"/api/workflows/{wid}").status_code == 200


def test_not_found_and_validation_error_format(user):
    resp = user.get(f"/api/workflows/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "NOT_FOUND"

    resp = user.post("/api/workflows", json={"name": ""})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "name"

    resp = user.client.post("/api/workflows", headers=user.headers, data="not json", content_type="text/plain")
    assert resp.get_json()["error"]["code"] == "INVALID_JSON"


def test_invalid_uuid_in_path_is_404(user):
    assert user.get("/api/workflows/not-a-uuid").status_code == 404


def test_internal_errors_hide_details(user, monkeypatch):
    from app.services import workflow_service

    def boom(*_):
        raise RuntimeError("password=supersecret db exploded")

    monkeypatch.setattr(workflow_service, "list_workflows", boom)
    resp = user.get("/api/workflows")
    assert resp.status_code == 500
    assert resp.get_json() == {"success": False,
                               "error": {"code": "INTERNAL_ERROR", "message": "Erro interno. Tente novamente."}}


def test_log_redaction():
    from app.utils.logging_setup import redact

    text = redact("GET /x?access_token=IGAAabc123&client_secret=s3cr3t Authorization: Bearer eyJabc.def sk-abcdefghijk123")
    assert "IGAAabc123" not in text and "s3cr3t" not in text and "eyJabc" not in text and "sk-abcdefghijk123" not in text
    assert redact("/callback?code=AQBsecret&state=x") == "/callback?code=***&state=x"
    # códigos de erro da Meta precisam continuar legíveis para diagnóstico
    assert redact("Meta API erro (status=400, code=190, subcode=463)") == "Meta API erro (status=400, code=190, subcode=463)"


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok", "database": "ok"}
