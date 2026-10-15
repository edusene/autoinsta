"""Modo estrito da IA: regras fixas + resposta conferida pelo código + resposta fixa."""
import json

import pytest

from app.services import openai_service
from tests.helpers import edge, node
from tests.test_webhooks_and_engine import create_active, dm_payload, drain_jobs, post_webhook

FALLBACK = "Vou chamar alguém da equipe!"
KNOWLEDGE = "Horário: 9h às 18h.\nCatálogo: https://loja.com/catalogo"


def ai_graph(mode="strict"):
    config = {"mode": mode, "instructions": "Seja simpático.", "knowledge": KNOWLEDGE,
              "fallback_text": FALLBACK, "input": "{{message.text}}", "save_as": "r"}
    return {"nodes": [node("t", "trigger.message_received"), node("ai", "action.ai", config),
                      node("m", "action.send_message", {"text": "{{ai.response}}"})],
            "edges": [edge("t", "ai"), edge("ai", "m")]}


@pytest.fixture
def ai_reply(monkeypatch):
    """Configura o que a 'OpenAI' devolve e registra as chamadas."""
    calls = []

    def set_reply(text=None, error=None):
        def fake(**kwargs):
            calls.append(kwargs)
            if error:
                raise openai_service.OpenAIServiceError(error)
            return {"text": text, "model": "m", "usage": {}}
        monkeypatch.setattr(openai_service, "generate_text", fake)
    set_reply.calls = calls
    return set_reply


def run(client, user, meta_mock, text="qual o horário?", mid="x1"):
    post_webhook(client, dm_payload(text, mid=mid))
    drain_jobs()
    return meta_mock.named("send_text_message")[-1][1][2]


def test_confident_answer_is_sent(client, user, connected_account, meta_mock, ai_reply):
    ai_reply(json.dumps({"resposta": "Atendemos das 9h às 18h.", "tem_certeza": True}))
    create_active(user, ai_graph())
    assert run(client, user, meta_mock) == "Atendemos das 9h às 18h."
    call = ai_reply.calls[0]
    # regras fixas + base de conhecimento no prompt, formato estrito e temperatura mínima
    assert "REGRAS OBRIGATÓRIAS" in call["instructions"] and KNOWLEDGE in call["instructions"]
    assert call["json_schema"]["required"] == ["resposta", "tem_certeza"]
    assert call["temperature"] == 0
    assert call["input_text"] == "qual o horário?"  # só a mensagem do cliente vai como entrada


def test_unsure_answer_uses_fallback(client, user, connected_account, meta_mock, ai_reply):
    ai_reply(json.dumps({"resposta": "Custa R$ 49,90", "tem_certeza": False}))
    create_active(user, ai_graph())
    assert run(client, user, meta_mock, "quanto custa?") == FALLBACK


def test_invented_link_uses_fallback(client, user, connected_account, meta_mock, ai_reply):
    ai_reply(json.dumps({"resposta": "Compre em https://site-falso.com/promo", "tem_certeza": True}))
    create_active(user, ai_graph())
    assert run(client, user, meta_mock) == FALLBACK


def test_known_link_is_allowed(client, user, connected_account, meta_mock, ai_reply):
    ai_reply(json.dumps({"resposta": "Veja: https://loja.com/catalogo.", "tem_certeza": True}))
    create_active(user, ai_graph())
    assert run(client, user, meta_mock) == "Veja: https://loja.com/catalogo."


def test_invalid_json_and_api_failure_use_fallback(client, user, connected_account, meta_mock, ai_reply):
    create_active(user, ai_graph())
    ai_reply("isso não é json")
    assert run(client, user, meta_mock, mid="a") == FALLBACK
    ai_reply(error="timeout")
    assert run(client, user, meta_mock, mid="b") == FALLBACK  # no estrito, falha da OpenAI não deixa sem resposta


def test_fallback_is_logged(client, user, connected_account, meta_mock, ai_reply):
    ai_reply(json.dumps({"resposta": "", "tem_certeza": False}))
    wid = create_active(user, ai_graph())
    run(client, user, meta_mock)
    items = user.get(f"/api/workflows/{wid}/executions").get_json()["data"]["items"]
    logs = user.get(f"/api/executions/{items[0]['id']}").get_json()["data"]["logs"]
    ai_log = next(log for log in logs if log["node_type"] == "action.ai")
    assert ai_log["message"].startswith("Resposta fixa usada") and ai_log["data"]["used_fallback"] is True


def test_free_mode_and_legacy_nodes_keep_old_behavior(client, user, connected_account, meta_mock, ai_reply):
    ai_reply("Texto criativo livre")
    graph = ai_graph(mode="free")
    create_active(user, graph)
    assert run(client, user, meta_mock) == "Texto criativo livre"
    assert "json_schema" not in ai_reply.calls[0] or ai_reply.calls[0]["json_schema"] is None
    assert "REGRAS OBRIGATÓRIAS" not in ai_reply.calls[0]["instructions"]
