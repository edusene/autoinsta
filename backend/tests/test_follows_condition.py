"""Condição 'Contato segue a conta?' (campo is_user_follow_business da User Profile API)."""
from app.services.meta_client import MetaApiError
from tests.helpers import edge, node
from tests.test_webhooks_and_engine import create_active, dm_payload, drain_jobs, post_webhook


def follow_gate_graph(on_unknown="false"):
    return {
        "nodes": [
            node("t", "trigger.message_received"),
            node("f", "condition.follows", {"on_unknown": on_unknown}),
            node("sim", "action.send_message", {"text": "Aqui está o link!"}),
            node("nao", "action.send_message", {"text": "Me segue e manda de novo!"}),
        ],
        "edges": [edge("t", "f"), edge("f", "sim", "true"), edge("f", "nao", "false")],
    }


def last_text(meta_mock):
    return meta_mock.named("send_text_message")[-1][1][2]


def test_follower_gets_link(client, user, connected_account, meta_mock):
    meta_mock.set("get_user_profile",
                  lambda token, igsid, fields="name,username": {"is_user_follow_business": True, "username": "x"})
    create_active(user, follow_gate_graph())
    post_webhook(client, dm_payload("eu quero", mid="f1"))
    drain_jobs()
    assert last_text(meta_mock) == "Aqui está o link!"
    # consultou o campo certo
    assert any("is_user_follow_business" in c[1] for c in meta_mock.named("get_user_profile"))


def test_non_follower_is_asked_to_follow(client, user, connected_account, meta_mock):
    meta_mock.set("get_user_profile",
                  lambda token, igsid, fields="name,username": {"is_user_follow_business": False})
    create_active(user, follow_gate_graph())
    post_webhook(client, dm_payload("eu quero", mid="f2"))
    drain_jobs()
    assert last_text(meta_mock) == "Me segue e manda de novo!"


def test_cannot_verify_uses_configured_path(client, user, connected_account, meta_mock):
    meta_mock.set("get_user_profile", MetaApiError("User consent is required to access user profile", status=400, code=230))
    create_active(user, follow_gate_graph(on_unknown="true"))
    post_webhook(client, dm_payload("eu quero", mid="f3"))
    drain_jobs()
    assert last_text(meta_mock) == "Aqui está o link!"
    executions = user.get("/api/logs").get_json()["data"]["items"]
    detail = user.get(f"/api/executions/{executions[0]['id']}").get_json()["data"]
    assert detail["status"] == "success"
    assert any("Não foi possível verificar" in log["message"] for log in detail["logs"])


def test_simulation_treats_contact_as_follower(user, connected_account, meta_mock):
    create_active(user, follow_gate_graph())
    user.post("/api/instagram/simulate", json={"kind": "message", "text": "eu quero"})
    drain_jobs()
    executions = user.get("/api/logs").get_json()["data"]["items"]
    detail = user.get(f"/api/executions/{executions[0]['id']}").get_json()["data"]
    assert any(log["message"] == "Contato segue a conta (Sim)." for log in detail["logs"])
    assert meta_mock.named("get_user_profile") == [] and meta_mock.named("send_text_message") == []
