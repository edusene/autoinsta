import hashlib
import hmac
import json

from app import db
from app.tasks import worker
from tests.conftest import TestConfig
from tests.helpers import comment_graph, dm_graph_with_condition, edge, node

IG_ACCOUNT = "17840000000000001"


def sign(body: bytes, secret: str = TestConfig.META_APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post_webhook(client, payload: dict, secret: str = TestConfig.META_APP_SECRET):
    body = json.dumps(payload).encode()
    return client.post("/webhooks/meta", data=body, content_type="application/json",
                       headers={"X-Hub-Signature-256": sign(body, secret)})


def dm_payload(text: str, mid: str = "mid.1", sender: str = "998877", echo: bool = False) -> dict:
    message = {"mid": mid, "text": text}
    if echo:
        message["is_echo"] = True
    return {"object": "instagram", "entry": [{
        "id": IG_ACCOUNT, "time": 1,
        "messaging": [{"sender": {"id": sender}, "recipient": {"id": IG_ACCOUNT}, "timestamp": 1, "message": message}],
    }]}


def comment_payload(text: str, comment_id: str = "c_1", sender: str = "554433", media_id: str = "media_1") -> dict:
    return {"object": "instagram", "entry": [{
        "id": IG_ACCOUNT, "time": 1,
        "changes": [{"field": "comments", "value": {
            "from": {"id": sender, "username": "fulano"}, "id": comment_id, "text": text,
            "media": {"id": media_id, "media_product_type": "FEED"}}}],
    }]}


def drain_jobs():
    """Executa todos os jobs prontos (como o worker faria)."""
    while worker.run_one():
        pass


def create_active(user, graph, name="W"):
    wid = user.post("/api/workflows", json={"name": name, "graph": graph}).get_json()["data"]["id"]
    resp = user.post(f"/api/workflows/{wid}/activate")
    assert resp.status_code == 200, resp.get_json()
    return wid


def last_execution(user, wid):
    items = user.get(f"/api/workflows/{wid}/executions").get_json()["data"]["items"]
    assert items, "nenhuma execução registrada"
    return user.get(f"/api/executions/{items[0]['id']}").get_json()["data"]


# --- verificação / assinatura ------------------------------------------------

def test_verify_challenge(client):
    ok = client.get("/webhooks/meta?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=1158201444")
    assert ok.status_code == 200 and ok.data == b"1158201444"
    bad = client.get("/webhooks/meta?hub.mode=subscribe&hub.verify_token=errado&hub.challenge=1")
    assert bad.status_code == 403


def test_rejects_invalid_signature(client):
    assert post_webhook(client, dm_payload("oi"), secret="wrong").status_code == 403
    resp = client.post("/webhooks/meta", json=dm_payload("oi"))  # sem header
    assert resp.status_code == 403


def test_extra_secret_accepted(client, app):
    app.config["META_WEBHOOK_EXTRA_SECRETS"] = ["fb-app-secret"]
    try:
        assert post_webhook(client, dm_payload("oi"), secret="fb-app-secret").status_code == 200
    finally:
        app.config["META_WEBHOOK_EXTRA_SECRETS"] = []


def test_ingest_is_fast_and_deduplicated(client):
    resp = post_webhook(client, dm_payload("oi"))
    assert resp.status_code == 200 and resp.get_json()["received"] == 1
    again = post_webhook(client, dm_payload("oi"))  # reenvio da Meta
    assert again.get_json() == {"success": True, "received": 0, "duplicates": 1}
    with db.connection() as conn:
        assert conn.execute("select count(*) as n from jobs where type = 'process_webhook_event'").fetchone()["n"] == 1


def test_unknown_account_is_ignored(client):
    post_webhook(client, dm_payload("oi"))
    drain_jobs()
    with db.connection() as conn:
        row = conn.execute("select status, status_reason from webhook_events").fetchone()
    assert row["status"] == "ignored"


# --- execução de ponta a ponta -----------------------------------------------

def test_dm_condition_true_branch(client, user, connected_account, meta_mock, openai_mock):
    wid = create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("Qual o PREÇO?"))
    drain_jobs()

    sent = meta_mock.named("send_text_message")
    assert len(sent) == 1
    token, recipient, text = sent[0][1]
    assert token == "IGAAtesttoken123" and recipient == "998877"
    assert text == "Oi cliente_teste, custa R$ 10."  # username obtido pela User Profile API
    assert openai_mock == []

    execution = last_execution(user, wid)
    assert execution["status"] == "success"
    assert "_sys" not in execution["context"]
    assert [log["node_id"] for log in execution["logs"]][:3] == ["t", "c", "yes"]

    contacts = user.get("/api/contacts").get_json()["data"]
    assert contacts["total"] == 1 and contacts["items"][0]["username"] == "cliente_teste"


def test_dm_condition_false_branch_uses_ai(client, user, connected_account, meta_mock, openai_mock):
    wid = create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("Qual o horário?"))
    drain_jobs()

    assert len(openai_mock) == 1
    assert openai_mock[0]["input_text"] == "Qual o horário?"  # só o necessário vai para a OpenAI
    assert openai_mock[0]["model"] == TestConfig.OPENAI_DEFAULT_MODEL
    assert meta_mock.named("send_text_message")[0][1][2] == "Olá! Nosso horário é das 9h às 18h."
    execution = last_execution(user, wid)
    assert execution["status"] == "success"
    assert execution["context"]["vars"]["resposta"] == "Olá! Nosso horário é das 9h às 18h."


def test_user_default_ai_model_is_used(client, user, connected_account, meta_mock, openai_mock):
    user.put("/api/settings", json={"ai_default_model": "meu-modelo"})
    create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("olá"))
    drain_jobs()
    assert openai_mock[0]["model"] == "meu-modelo"


def test_echo_and_own_messages_do_not_trigger(client, user, connected_account, meta_mock):
    create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("preço", mid="e1", echo=True))
    post_webhook(client, dm_payload("preço", mid="e2", sender=IG_ACCOUNT))
    drain_jobs()
    assert meta_mock.named("send_text_message") == []
    with db.connection() as conn:
        assert conn.execute("select count(*) as n from workflow_executions").fetchone()["n"] == 0


def test_inactive_workflow_does_not_run(client, user, connected_account, meta_mock):
    wid = create_active(user, dm_graph_with_condition())
    user.post(f"/api/workflows/{wid}/deactivate")
    post_webhook(client, dm_payload("preço"))
    drain_jobs()
    assert meta_mock.named("send_text_message") == []


def test_other_users_workflows_are_not_triggered(client, user, other_user, connected_account, meta_mock):
    other_user.post("/api/workflows", json={"name": "Do Bob", "graph": dm_graph_with_condition()})
    post_webhook(client, dm_payload("preço"))
    drain_jobs()
    assert meta_mock.named("send_text_message") == []


def test_comment_private_and_public_reply(client, user, connected_account, meta_mock):
    wid = create_active(user, comment_graph())
    post_webhook(client, comment_payload("EU QUERO!!", comment_id="c_42"))
    drain_jobs()

    private = meta_mock.named("send_private_reply")
    assert len(private) == 1 and private[0][1][1] == "c_42"
    assert private[0][1][2] == "Oi @fulano! Aqui está o link."
    public = meta_mock.named("reply_to_comment")
    assert len(public) == 1 and public[0][1][1:] == ("c_42", "Te enviei por DM!")
    assert last_execution(user, wid)["status"] == "success"


def test_comment_from_own_account_is_ignored(client, user, connected_account, meta_mock):
    create_active(user, comment_graph())
    post_webhook(client, comment_payload("eu quero", sender=IG_ACCOUNT))
    drain_jobs()
    assert meta_mock.named("send_private_reply") == []


def test_comment_trigger_media_filter(client, user, connected_account, meta_mock):
    graph = comment_graph()
    graph["nodes"][0]["data"]["config"]["media_id"] = "media_certa"
    create_active(user, graph)
    post_webhook(client, comment_payload("eu quero", comment_id="c1", media_id="outra"))
    drain_jobs()
    assert meta_mock.named("send_private_reply") == []
    post_webhook(client, comment_payload("eu quero", comment_id="c2", media_id="media_certa"))
    drain_jobs()
    assert len(meta_mock.named("send_private_reply")) == 1


def test_meta_failure_is_logged_as_error(client, user, connected_account, meta_mock):
    from app.services.meta_client import MetaApiError

    meta_mock.set("send_text_message", MetaApiError("(#10) Outside of allowed window", status=400, code=10))
    wid = create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("preço"))
    drain_jobs()
    execution = last_execution(user, wid)
    assert execution["status"] == "error"
    assert "Falha ao enviar para a Meta" in execution["error"]
    assert execution["logs"][-1]["level"] == "error"
    dash = user.get("/api/dashboard").get_json()["data"]
    assert dash["executions_24h"]["errors"] == 1 and len(dash["recent_errors"]) == 1


def test_meta_token_error_marks_account_expired(client, user, connected_account, meta_mock):
    from app.services.meta_client import MetaApiError

    meta_mock.set("send_text_message", MetaApiError("Error validating access token", status=401, code=190))
    create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("preço"))
    drain_jobs()
    status = user.get("/api/instagram/status").get_json()["data"]
    assert status["status"] == "token_expired" and status["connected"] is False


def test_delay_pauses_and_resumes(client, user, connected_account, meta_mock):
    graph = {
        "nodes": [node("t", "trigger.message_received"), node("d", "action.delay", {"seconds": 30}),
                  node("m", "action.send_message", {"text": "Depois de 30s"})],
        "edges": [edge("t", "d"), edge("d", "m")],
    }
    wid = create_active(user, graph)
    post_webhook(client, dm_payload("oi"))
    drain_jobs()

    execution = last_execution(user, wid)
    assert execution["status"] == "waiting" and execution["current_node_id"] == "m"
    assert meta_mock.named("send_text_message") == []
    with db.connection() as conn:
        job = conn.execute("select * from jobs where type = 'resume_execution'").fetchone()
        assert job["status"] == "queued"
        # simula a passagem do tempo
        conn.execute("update jobs set run_at = now() where id = %s", (job["id"],))
    drain_jobs()
    assert last_execution(user, wid)["status"] == "success"
    assert meta_mock.named("send_text_message")[0][1][2] == "Depois de 30s"


def test_delay_cancelled_if_workflow_deactivated(client, user, connected_account, meta_mock):
    graph = {
        "nodes": [node("t", "trigger.message_received"), node("d", "action.delay", {"seconds": 30}),
                  node("m", "action.send_message", {"text": "x"})],
        "edges": [edge("t", "d"), edge("d", "m")],
    }
    wid = create_active(user, graph)
    post_webhook(client, dm_payload("oi"))
    drain_jobs()
    user.post(f"/api/workflows/{wid}/deactivate")
    with db.connection() as conn:
        conn.execute("update jobs set run_at = now() where type = 'resume_execution'")
    drain_jobs()
    assert last_execution(user, wid)["status"] == "cancelled"
    assert meta_mock.named("send_text_message") == []


def test_set_variable_and_end(client, user, connected_account, meta_mock):
    graph = {
        "nodes": [node("t", "trigger.message_received"),
                  node("v", "action.set_variable", {"name": "saud", "value": "Olá", "mode": "set"}),
                  node("v2", "action.set_variable", {"name": "saud", "value": ", {{contact.name}}", "mode": "append"}),
                  node("m", "action.send_message", {"text": "{{vars.saud}}!"}),
                  node("e", "action.end")],
        "edges": [edge("t", "v"), edge("v", "v2"), edge("v2", "m"), edge("m", "e")],
    }
    create_active(user, graph)
    post_webhook(client, dm_payload("oi"))
    drain_jobs()
    assert meta_mock.named("send_text_message")[0][1][2] == "Olá, Cliente Teste!"


def test_logs_endpoint_filters(client, user, connected_account, meta_mock):
    create_active(user, dm_graph_with_condition())
    post_webhook(client, dm_payload("preço"))
    drain_jobs()
    assert user.get("/api/logs?status=success").get_json()["data"]["total"] == 1
    assert user.get("/api/logs?status=error").get_json()["data"]["total"] == 0
    assert user.get("/api/logs?status=bogus").status_code == 400
