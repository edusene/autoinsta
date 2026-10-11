"""Gatilhos: novo contato, stories, link ig.me, reação e comentário em live."""
from app import db
from app.workflow.validator import normalize_graph, validate_graph
from tests.helpers import edge, node
from tests.test_webhooks_and_engine import IG_ACCOUNT, create_active, drain_jobs, post_webhook


def dm_graph(trigger: str, text: str, trigger_config: dict | None = None):
    return {"nodes": [node("t", trigger, trigger_config or {}), node("m", "action.send_message", {"text": text})],
            "edges": [edge("t", "m")]}


def messaging(item: dict, sender: str = "998877") -> dict:
    return {"object": "instagram", "entry": [{"id": IG_ACCOUNT, "time": 1, "messaging": [
        {"sender": {"id": sender}, "recipient": {"id": IG_ACCOUNT}, "timestamp": 1, **item}]}]}


def sent_texts(meta_mock):
    return [c[1][2] for c in meta_mock.named("send_text_message")]


def test_new_contact_fires_only_on_first_message(client, user, connected_account, meta_mock):
    create_active(user, dm_graph("trigger.new_contact", "Bem-vindo, {{contact.username}}!"), "Boas-vindas")
    create_active(user, dm_graph("trigger.message_received", "Recebi: {{message.text}}"), "Padrão")

    post_webhook(client, messaging({"message": {"mid": "m1", "text": "oi"}}))
    drain_jobs()
    assert sorted(sent_texts(meta_mock)) == sorted(["Bem-vindo, cliente_teste!", "Recebi: oi"])

    post_webhook(client, messaging({"message": {"mid": "m2", "text": "de novo"}}))
    drain_jobs()
    assert sent_texts(meta_mock).count("Bem-vindo, cliente_teste!") == 1  # só na 1ª vez
    assert "Recebi: de novo" in sent_texts(meta_mock)


def test_story_mention(client, user, connected_account, meta_mock):
    create_active(user, dm_graph("trigger.story_mention", "Obrigado pela menção!"))
    create_active(user, dm_graph("trigger.message_received", "não deveria"), "Padrão")
    post_webhook(client, messaging({"message": {"mid": "sm1", "attachments": [
        {"type": "story_mention", "payload": {"url": "https://cdn/story"}}]}}))
    drain_jobs()
    assert sent_texts(meta_mock) == ["Obrigado pela menção!"]


def test_story_reply_and_fallback_to_message(client, user, connected_account, meta_mock):
    reply = {"message": {"mid": "sr1", "text": "eu quero", "reply_to": {"story": {"id": "s1", "url": "u"}}}}
    wid = create_active(user, dm_graph("trigger.message_received", "Padrão: {{message.text}}"), "Padrão")
    post_webhook(client, messaging(reply))  # sem workflow de story -> cai em "Mensagem recebida"
    drain_jobs()
    assert sent_texts(meta_mock) == ["Padrão: eu quero"]

    create_active(user, dm_graph("trigger.story_reply", "Story {{story.id}}: {{message.text}}"), "Story")
    post_webhook(client, messaging({"message": {**reply["message"], "mid": "sr2"}}))
    drain_jobs()
    assert sent_texts(meta_mock)[-1] == "Story s1: eu quero"
    assert sent_texts(meta_mock).count("Padrão: eu quero") == 1  # com workflow específico, o padrão não roda
    assert wid


def test_ig_me_link_with_ref_filter(client, user, connected_account, meta_mock):
    create_active(user, dm_graph("trigger.ig_me_link", "Veio da bio", {"ref": "bio"}), "Bio")
    create_active(user, dm_graph("trigger.ig_me_link", "Veio de {{referral.ref}}"), "Qualquer")
    post_webhook(client, messaging({"referral": {"ref": "BIO", "source": "IGME_SOURCE_LINK", "type": "OPEN_THREAD"}}))
    post_webhook(client, messaging({"referral": {"ref": "anuncio", "source": "IGME_SOURCE_LINK", "type": "OPEN_THREAD"}},
                                   sender="111"))
    drain_jobs()
    assert sorted(sent_texts(meta_mock)) == sorted(["Veio da bio", "Veio de BIO", "Veio de anuncio"])


def test_first_message_from_link_uses_link_trigger(client, user, connected_account, meta_mock):
    create_active(user, dm_graph("trigger.ig_me_link", "Link: {{referral.ref}}"))
    post_webhook(client, messaging({"message": {"mid": "l1", "text": "oi", "referral": {"ref": "qr", "source": "x"}}}))
    drain_jobs()
    assert sent_texts(meta_mock) == ["Link: qr"]


def test_message_reaction_and_unreact_ignored(client, user, connected_account, meta_mock):
    create_active(user, dm_graph("trigger.message_reaction", "Valeu pelo {{reaction.emoji}}"))
    post_webhook(client, messaging({"reaction": {"mid": "x", "action": "react", "reaction": "love", "emoji": "❤️"}}))
    post_webhook(client, messaging({"reaction": {"mid": "x", "action": "unreact"}}, sender="222"))
    drain_jobs()
    assert sent_texts(meta_mock) == ["Valeu pelo ❤️"]
    with db.connection() as conn:
        reasons = [r["status_reason"] for r in conn.execute("select status_reason from webhook_events")]
    assert "Reação removida." in reasons


def test_live_comment_private_reply(client, user, connected_account, meta_mock):
    graph = {"nodes": [node("t", "trigger.live_comment"), node("p", "action.private_reply", {"text": "Oi {{contact.username}}"})],
             "edges": [edge("t", "p")]}
    create_active(user, graph)
    payload = {"object": "instagram", "entry": [{"id": IG_ACCOUNT, "time": 1, "changes": [{"field": "live_comments", "value": {
        "from": {"id": "333", "username": "fa"}, "comment_id": "lc1", "text": "oi", "media": {"id": "live1"}}}]}]}
    post_webhook(client, payload)
    post_webhook(client, payload)  # reenvio da Meta: deduplicado pelo comment_id
    drain_jobs()
    calls = meta_mock.named("send_private_reply")
    assert len(calls) == 1 and calls[0][1][1:] == ("lc1", "Oi fa")


def test_meta_rules_for_new_triggers():
    def errors(trigger, action):
        g = {"nodes": [node("t", trigger), node("a", action, {"text": "x"})], "edges": [edge("t", "a")]}
        return [e["message"] for e in validate_graph(normalize_graph(g))["errors"]]

    assert errors("trigger.story_mention", "action.send_message") == []
    assert errors("trigger.new_contact", "action.send_message") == []
    assert errors("trigger.live_comment", "action.private_reply") == []
    # Não é permitido responder publicamente comentário de live, nem resposta privada fora de comentário
    assert errors("trigger.live_comment", "action.reply_comment")
    assert errors("trigger.story_reply", "action.private_reply")
    assert errors("trigger.live_comment", "action.send_message")


def test_simulation_of_new_kinds(user, connected_account, meta_mock):
    create_active(user, dm_graph("trigger.story_mention", "menção"), "M")
    create_active(user, dm_graph("trigger.new_contact", "novo"), "N")
    for kind in ("story_mention", "new_contact", "new_contact"):
        assert user.post("/api/instagram/simulate", json={"kind": kind, "text": "oi"}).status_code == 201
    drain_jobs()
    with db.connection() as conn:
        statuses = [r["status"] for r in conn.execute("select status from workflow_executions")]
    # menção de remetente novo também dispara "Novo contato" (1ª interação) + 2 novos contatos
    assert statuses == ["success"] * 4
    assert meta_mock.named("send_text_message") == []  # simulação nunca envia
