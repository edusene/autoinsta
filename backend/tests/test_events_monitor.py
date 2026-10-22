"""Monitor de eventos, registro de recusas e simulação (dry run)."""
import json

from app import db
from app.services import webhook_service
from tests.helpers import dm_graph_with_condition
from tests.test_webhooks_and_engine import IG_ACCOUNT, create_active, dm_payload, drain_jobs, post_webhook


def test_events_list_shows_received_dm(client, user, connected_account, meta_mock):
    post_webhook(client, dm_payload("Qual o preço?", mid="m-1"))
    drain_jobs()
    data = user.get("/api/instagram/events").get_json()["data"]
    assert data["account"]["username"] == "minhaloja"
    event = data["events"][0]
    assert event["field"] == "messages" and event["text"] == "Qual o preço?"
    assert event["status"] == "processed" and event["simulated"] is False
    assert "payload" not in event


def test_rejected_signature_is_recorded_and_flagged_in_diagnostics(client, user, connected_account, meta_mock):
    body = json.dumps(dm_payload("oi")).encode()
    resp = client.post("/webhooks/meta", data=body, content_type="application/json",
                       headers={"X-Hub-Signature-256": "sha256=errada"})
    assert resp.status_code == 403
    rejections = user.get("/api/instagram/events").get_json()["data"]["rejections"]
    assert len(rejections) == 1
    assert "não confere" in rejections[0]["reason"] and rejections[0]["fields"] == ["messages"]
    assert "ig_account_ids" not in rejections[0]

    meta_mock.set("get_me", {"user_id": IG_ACCOUNT, "username": "minhaloja", "account_type": "BUSINESS"})
    checks = {c["key"]: c for c in user.get("/api/instagram/diagnostics").get_json()["data"]["checks"]}
    assert checks["webhook_signature"]["status"] == "error"
    assert "META_WEBHOOK_EXTRA_SECRETS" in checks["webhook_signature"]["detail"]


def test_rejection_flood_is_capped_but_still_refused(client):
    body = json.dumps(dm_payload("spam")).encode()
    for _ in range(webhook_service.MAX_REJECTIONS_PER_MINUTE + 10):
        resp = client.post("/webhooks/meta", data=body, content_type="application/json",
                           headers={"X-Hub-Signature-256": "sha256=errada"})
        assert resp.status_code == 403
    with db.connection() as conn:
        stored = conn.execute("select count(*) as n from webhook_rejections").fetchone()["n"]
    assert stored == webhook_service.MAX_REJECTIONS_PER_MINUTE


def test_rejections_of_other_accounts_are_hidden(client, user, other_user, connected_account):
    with db.connection() as conn:
        conn.execute("insert into profiles (id, email) values (%s, %s) on conflict do nothing",
                     (other_user.id, other_user.email))
        conn.execute("""insert into instagram_accounts (user_id, ig_user_id, username, status)
                        values (%s, 'OUTRA', 'outra', 'connected')""", (other_user.id,))
    payload = dm_payload("x")
    payload["entry"][0]["id"] = "OUTRA"
    client.post("/webhooks/meta", data=json.dumps(payload).encode(), content_type="application/json",
                headers={"X-Hub-Signature-256": "sha256=errada"})
    assert user.get("/api/instagram/events").get_json()["data"]["rejections"] == []


def test_simulated_dm_runs_workflow_without_sending(client, user, connected_account, meta_mock, openai_mock):
    wid = create_active(user, dm_graph_with_condition())
    resp = user.post("/api/instagram/simulate", json={"kind": "message", "text": "quanto custa? preço"})
    assert resp.status_code == 201
    drain_jobs()

    assert meta_mock.named("send_text_message") == []  # nada enviado à Meta
    assert meta_mock.named("get_user_profile") == []
    event = user.get("/api/instagram/events").get_json()["data"]["events"][0]
    assert event["simulated"] is True and event["executions"] == 1

    executions = user.get(f"/api/workflows/{wid}/executions").get_json()["data"]["items"]
    detail = user.get(f"/api/executions/{executions[0]['id']}").get_json()["data"]
    assert detail["status"] == "success"
    assert any("simulação" in log["message"] for log in detail["logs"])


def test_simulated_comment(client, user, connected_account, meta_mock):
    from tests.helpers import comment_graph

    create_active(user, comment_graph())
    user.post("/api/instagram/simulate", json={"kind": "comment", "text": "EU QUERO"})
    drain_jobs()
    assert meta_mock.named("send_private_reply") == [] and meta_mock.named("reply_to_comment") == []
    with db.connection() as conn:
        assert conn.execute("select status from workflow_executions").fetchone()["status"] == "success"


def test_simulation_requires_connection_and_valid_body(user):
    assert user.post("/api/instagram/simulate", json={"text": "oi"}).status_code == 409
    assert user.post("/api/instagram/simulate", json={"kind": "x", "text": "oi"}).status_code == 422


def test_external_payload_cannot_trigger_dry_run(client, user, connected_account, meta_mock):
    """Um evento real nunca vira simulação, mesmo que o payload tente imitar."""
    create_active(user, dm_graph_with_condition())
    payload = dm_payload("preço", mid="sim:abc")
    post_webhook(client, payload)
    drain_jobs()
    assert len(meta_mock.named("send_text_message")) == 1
