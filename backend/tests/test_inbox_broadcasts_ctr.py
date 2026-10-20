"""Caixa de entrada, contatos (tags/pausa), CTR, botões, follow-up e disparos em massa."""
import re

from app import db
from tests.helpers import edge, node
from tests.test_webhooks_and_engine import IG_ACCOUNT, create_active, dm_payload, drain_jobs, last_execution, post_webhook


def postback_payload(payload: str, title: str, sender: str = "998877", mid: str = "pb.1") -> dict:
    return {"object": "instagram", "entry": [{
        "id": IG_ACCOUNT, "time": 1,
        "messaging": [{"sender": {"id": sender}, "recipient": {"id": IG_ACCOUNT}, "timestamp": 1,
                       "postback": {"mid": mid, "title": title, "payload": payload}}],
    }]}


def contact_id_for(sender: str = "998877") -> str:
    with db.connection() as conn:
        return str(conn.execute("select id from contacts where ig_scoped_id = %s", (sender,)).fetchone()["id"])


def expire_waits():
    """Faz os prazos de espera (jobs agendados) vencerem agora."""
    with db.connection() as conn:
        conn.execute("update jobs set run_at = now() where status = 'queued'")
    drain_jobs()


def outbound_messages():
    with db.connection() as conn:
        return conn.execute("select * from messages where direction = 'out' order by created_at").fetchall()


# --- caixa de entrada -----------------------------------------------------------

def test_inbound_dm_goes_to_inbox_and_reply_from_panel(user, connected_account, meta_mock):
    post_webhook(user.client, dm_payload("Oi, tudo bem?", mid="mid.in1"))
    drain_jobs()

    convs = user.get("/api/inbox/conversations").get_json()["data"]
    assert convs["total"] == 1 and convs["unread_conversations"] == 1
    conv = convs["items"][0]
    assert conv["last_message_preview"] == "Oi, tudo bem?" and conv["unread_count"] == 1 and conv["can_message"]

    detail = user.get(f"/api/inbox/conversations/{conv['id']}").get_json()["data"]
    assert [m["text"] for m in detail["messages"]] == ["Oi, tudo bem?"]

    resp = user.post(f"/api/inbox/conversations/{conv['id']}/messages", json={"text": "Olá! Como posso ajudar?"})
    assert resp.status_code == 201, resp.get_json()
    messages = resp.get_json()["data"]["messages"]
    assert [(m["direction"], m["source"], m["status"]) for m in messages] == [
        ("in", "contact", "received"), ("out", "inbox", "sent")]
    assert meta_mock.named("send_text_message")[-1][1][1:] == ("998877", "Olá! Como posso ajudar?")
    assert user.get("/api/inbox/unread-count").get_json()["data"]["unread_conversations"] == 0

    # Mensagem enviada pelo app do Instagram (eco) entra na conversa; o eco da nossa própria não duplica
    ours = outbound_messages()[0]["mid"]
    echo = dm_payload("Respondi pelo celular", mid="mid.echo1", sender=IG_ACCOUNT, echo=True)
    echo["entry"][0]["messaging"][0]["recipient"] = {"id": "998877"}
    own_echo = dm_payload("Olá! Como posso ajudar?", mid=ours, sender=IG_ACCOUNT, echo=True)
    own_echo["entry"][0]["messaging"][0]["recipient"] = {"id": "998877"}
    post_webhook(user.client, echo)
    post_webhook(user.client, own_echo)
    drain_jobs()
    texts = [m["text"] for m in user.get(f"/api/inbox/conversations/{conv['id']}").get_json()["data"]["messages"]]
    assert texts == ["Oi, tudo bem?", "Olá! Como posso ajudar?", "Respondi pelo celular"]


def test_inbox_reply_blocked_outside_24h_window(user, connected_account, meta_mock):
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()
    cid = contact_id_for()
    with db.connection() as conn:
        conn.execute("update contacts set last_inbound_at = now() - interval '25 hours' where id = %s", (cid,))
    resp = user.post(f"/api/inbox/conversations/{cid}/messages", json={"text": "oi"})
    assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "OUTSIDE_WINDOW"
    assert not meta_mock.named("send_text_message")


def test_other_user_cannot_read_conversation(user, other_user, connected_account, meta_mock):
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()
    cid = contact_id_for()
    assert other_user.get(f"/api/inbox/conversations/{cid}").status_code == 404
    assert other_user.post(f"/api/inbox/conversations/{cid}/messages", json={"text": "x"}).status_code == 404


# --- contatos: tags, notas e pausa -------------------------------------------------

def test_contact_tags_notes_and_pause(user, connected_account, meta_mock):
    wid = create_active(user, {"nodes": [node("t", "trigger.message_received"),
                                         node("s", "action.send_message", {"text": "auto"})],
                               "edges": [edge("t", "s")]})
    post_webhook(user.client, dm_payload("oi", mid="m1"))
    drain_jobs()
    cid = contact_id_for()

    resp = user.put(f"/api/contacts/{cid}", json={"tags": ["Cliente", "vip", "cliente"], "notes": "Prefere WhatsApp",
                                                 "automation_paused": True})
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()["data"]
    assert data["tags"] == ["cliente", "vip"] and data["notes"] == "Prefere WhatsApp" and data["automation_paused"]
    assert user.put(f"/api/contacts/{cid}", json={"tags": ["inválida!"]}).status_code == 400

    assert user.get("/api/contacts?tag=vip").get_json()["data"]["total"] == 1
    assert user.get("/api/contacts?tag=outra").get_json()["data"]["total"] == 0
    assert {t["tag"]: t["count"] for t in user.get("/api/contacts/tags").get_json()["data"]} == {"cliente": 1, "vip": 1}

    # Pausado (atendimento humano): a mensagem entra na caixa de entrada, mas nenhum workflow roda
    sends_before = len(meta_mock.named("send_text_message"))
    post_webhook(user.client, dm_payload("quero falar com alguém", mid="m2"))
    drain_jobs()
    assert len(meta_mock.named("send_text_message")) == sends_before
    assert len(user.get(f"/api/workflows/{wid}/executions").get_json()["data"]["items"]) == 1
    assert user.get(f"/api/inbox/conversations/{cid}").get_json()["data"]["contact"]["unread_count"] == 2


def test_tag_nodes_and_has_tag_condition(user, connected_account, meta_mock):
    graph = {"nodes": [
        node("t", "trigger.message_received"),
        node("has", "condition.has_tag", {"tag": "lead"}),
        node("again", "action.send_message", {"text": "De novo por aqui!"}),
        node("add", "action.add_tag", {"tag": "Lead"}),
        node("first", "action.send_message", {"text": "Primeira vez!"}),
    ], "edges": [edge("t", "has"), edge("has", "again", "true"), edge("has", "add", "false"), edge("add", "first")]}
    create_active(user, graph)
    post_webhook(user.client, dm_payload("oi", mid="m1"))
    drain_jobs()
    post_webhook(user.client, dm_payload("oi de novo", mid="m2"))
    drain_jobs()
    assert [c[1][2] for c in meta_mock.named("send_text_message")] == ["Primeira vez!", "De novo por aqui!"]
    assert user.get(f"/api/contacts/{contact_id_for()}").get_json()["data"]["tags"] == ["lead"]


# --- CTR: links rastreados ------------------------------------------------------------

def test_tracked_links_count_clicks_and_ctr(user, connected_account, meta_mock, client):
    wid = create_active(user, {"nodes": [
        node("t", "trigger.message_received"),
        node("s", "action.send_message", {"text": "Veja: https://loja.com/promo?x=1.", "track_links": True}),
    ], "edges": [edge("t", "s")]})
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()

    sent_text = meta_mock.named("send_text_message")[0][1][2]
    match = re.search(r"https://app\.example\.com/r/([A-Za-z0-9_-]+)\.$", sent_text)
    assert match, sent_text
    code = match.group(1)
    # Na caixa de entrada aparece o texto original
    assert outbound_messages()[0]["text"] == "Veja: https://loja.com/promo?x=1."

    # Prévia de link (robô) não conta; clique de pessoa conta e redireciona
    bot = client.get(f"/r/{code}", headers={"User-Agent": "facebookexternalhit/1.1"})
    assert bot.status_code == 302 and bot.headers["Location"] == "https://loja.com/promo?x=1"
    assert user.get(f"/api/workflows/{wid}/stats").get_json()["data"]["s"] == {"sent": 1, "trackable": 1, "clicked": 0}
    human = client.get(f"/r/{code}", headers={"User-Agent": "Mozilla/5.0 (iPhone)"})
    assert human.status_code == 302
    client.get(f"/r/{code}", headers={"User-Agent": "Mozilla/5.0 (iPhone)"})

    assert user.get(f"/api/workflows/{wid}/stats").get_json()["data"]["s"] == {"sent": 1, "trackable": 1, "clicked": 1}
    dash = user.get("/api/dashboard").get_json()["data"]
    assert dash["ctr_7d"] == {"sent": 1, "trackable": 1, "clicked": 1}
    assert dash["top_links"][0]["url"] == "https://loja.com/promo?x=1" and dash["top_links"][0]["clicks"] == 2
    wf = next(w for w in user.get("/api/workflows").get_json()["data"] if w["id"] == wid)
    assert (wf["trackable_count"], wf["clicked_count"]) == (1, 1)
    assert client.get("/r/naoexiste").status_code == 404


def test_links_not_tracked_when_disabled(user, connected_account, meta_mock):
    create_active(user, {"nodes": [node("t", "trigger.message_received"),
                                   node("s", "action.send_message", {"text": "https://loja.com"})],
                         "edges": [edge("t", "s")]})
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()
    assert meta_mock.named("send_text_message")[0][1][2] == "https://loja.com"
    assert not outbound_messages()[0]["trackable"]


# --- botões -----------------------------------------------------------------------------

def buttons_graph(style="buttons"):
    buttons = [{"id": "sim", "title": "Quero", "type": "reply"}, {"id": "nao", "title": "Agora não", "type": "reply"}]
    if style == "buttons":
        buttons.append({"id": "site", "title": "Ver site", "type": "url", "url": "https://loja.com"})
    return {"nodes": [
        node("t", "trigger.message_received"),
        node("b", "action.send_buttons", {"text": "Quer o cupom?", "style": style, "buttons": buttons,
                                          "timeout_minutes": 30, "track_links": True}),
        node("yes", "action.send_message", {"text": "Cupom: {{button.title}} = OK10"}),
        node("no", "action.send_message", {"text": "Tudo bem!"}),
        node("late", "action.send_message", {"text": "Ainda quer o cupom?"}),
    ], "edges": [edge("t", "b"), edge("b", "yes", "sim"), edge("b", "no", "nao"), edge("b", "late", "timeout")]}


def test_button_template_click_follows_button_path(user, connected_account, meta_mock):
    wid = create_active(user, buttons_graph())
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()

    call = meta_mock.named("send_button_template")[0]
    _token, igsid, text, buttons = call[1]
    assert (igsid, text) == ("998877", "Quer o cupom?")
    assert [b["type"] for b in buttons] == ["postback", "postback", "web_url"]
    assert buttons[2]["url"].startswith("https://app.example.com/r/")
    assert last_execution(user, wid)["status"] == "waiting"

    # Clique no botão "Quero" (postback): segue pela saída do botão e não dispara outros workflows
    post_webhook(user.client, postback_payload(buttons[0]["payload"], "Quero"))
    drain_jobs()
    execution = last_execution(user, wid)
    assert execution["status"] == "success"
    assert [c[1][2] for c in meta_mock.named("send_text_message")] == ["Cupom: Quero = OK10"]
    assert any('clicou em "Quero"' in log["message"] for log in execution["logs"])
    assert len(user.get(f"/api/workflows/{wid}/executions").get_json()["data"]["items"]) == 1
    assert user.get(f"/api/workflows/{wid}/stats").get_json()["data"]["b"]["clicked"] == 1

    # O prazo antigo, ao vencer, não faz nada
    expire_waits()
    assert len(meta_mock.named("send_text_message")) == 1


def test_quick_reply_click_and_timeout(user, connected_account, meta_mock):
    wid = create_active(user, buttons_graph("quick_replies"))
    post_webhook(user.client, dm_payload("oi", mid="m1"))
    drain_jobs()
    replies = meta_mock.named("send_quick_replies")[0][1][3]
    assert [r["title"] for r in replies] == ["Quero", "Agora não"]

    quick = dm_payload("Agora não", mid="m2")
    quick["entry"][0]["messaging"][0]["message"]["quick_reply"] = {"payload": replies[1]["payload"]}
    post_webhook(user.client, quick)
    drain_jobs()
    assert [c[1][2] for c in meta_mock.named("send_text_message")] == ["Tudo bem!"]

    # Nova conversa sem clique: o prazo vence e segue por "Sem clique"
    post_webhook(user.client, dm_payload("oi de novo", mid="m3"))
    drain_jobs()
    expire_waits()
    assert [c[1][2] for c in meta_mock.named("send_text_message")] == ["Tudo bem!", "Ainda quer o cupom?"]
    assert last_execution(user, wid)["status"] == "success"


def test_forged_button_payload_from_other_contact_is_ignored(user, connected_account, meta_mock):
    create_active(user, buttons_graph())
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()
    payload = meta_mock.named("send_button_template")[0][1][3][0]["payload"]
    post_webhook(user.client, postback_payload(payload, "Quero", sender="intruso"))
    drain_jobs()
    assert not meta_mock.named("send_text_message")


# --- follow-up (aguardar resposta) -----------------------------------------------------

def followup_graph():
    return {"nodes": [
        node("t", "trigger.message_received"),
        node("ask", "action.send_message", {"text": "Qual seu tamanho?"}),
        node("wait", "action.wait_reply", {"timeout_minutes": 60}),
        node("thanks", "action.send_message", {"text": "Anotado: {{reply.text}}"}),
        node("follow", "action.send_message", {"text": "Oi! Ainda tem interesse?"}),
    ], "edges": [edge("t", "ask"), edge("ask", "wait"), edge("wait", "thanks", "replied"),
                 edge("wait", "follow", "timeout")]}


def test_wait_reply_resumes_on_reply_and_consumes_message(user, connected_account, meta_mock):
    wid = create_active(user, followup_graph())
    post_webhook(user.client, dm_payload("quero a camiseta", mid="m1"))
    drain_jobs()
    assert last_execution(user, wid)["status"] == "waiting"

    post_webhook(user.client, dm_payload("M", mid="m2"))
    drain_jobs()
    assert [c[1][2] for c in meta_mock.named("send_text_message")] == ["Qual seu tamanho?", "Anotado: M"]
    # A resposta foi usada pelo fluxo em espera: não iniciou uma nova execução
    assert len(user.get(f"/api/workflows/{wid}/executions").get_json()["data"]["items"]) == 1
    assert last_execution(user, wid)["status"] == "success"


def test_wait_reply_timeout_sends_follow_up(user, connected_account, meta_mock):
    wid = create_active(user, followup_graph())
    post_webhook(user.client, dm_payload("quero a camiseta"))
    drain_jobs()
    expire_waits()
    assert [c[1][2] for c in meta_mock.named("send_text_message")] == ["Qual seu tamanho?", "Oi! Ainda tem interesse?"]
    execution = last_execution(user, wid)
    assert execution["status"] == "success"
    assert any("Sem resposta" in log["message"] for log in execution["logs"])


def test_wait_cancelled_when_workflow_deactivated(user, connected_account, meta_mock):
    wid = create_active(user, followup_graph())
    post_webhook(user.client, dm_payload("oi"))
    drain_jobs()
    user.post(f"/api/workflows/{wid}/deactivate")
    expire_waits()
    assert last_execution(user, wid)["status"] == "cancelled"
    assert len(meta_mock.named("send_text_message")) == 1


# --- validação ----------------------------------------------------------------------------

def test_validator_buttons_and_dynamic_outputs(user):
    graph = buttons_graph()
    assert user.post("/api/workflows/validate", json={"graph": graph}).get_json()["data"]["valid"]

    bad = buttons_graph()
    bad["nodes"][1]["data"]["config"]["buttons"] += [{"id": "x", "title": "Um texto longo demais aqui", "type": "reply"}]
    errors = [e["message"] for e in user.post("/api/workflows/validate", json={"graph": bad}).get_json()["data"]["errors"]]
    assert any("no máximo 3" in e for e in errors) and any("até 20 caracteres" in e for e in errors)

    wrong_handle = buttons_graph()
    wrong_handle["edges"].append(edge("b", "late", "inexistente"))
    errors = [e["message"] for e in
              user.post("/api/workflows/validate", json={"graph": wrong_handle}).get_json()["data"]["errors"]]
    assert any("Saída 'inexistente' inválida" in e for e in errors)

    url_in_quick = buttons_graph("quick_replies")
    url_in_quick["nodes"][1]["data"]["config"]["buttons"].append(
        {"id": "u", "title": "Site", "type": "url", "url": "https://x.com"})
    errors = [e["message"] for e in
              user.post("/api/workflows/validate", json={"graph": url_in_quick}).get_json()["data"]["errors"]]
    assert any("não aceitam link" in e for e in errors)


# --- disparos em massa -----------------------------------------------------------------------

def _two_contacts(user):
    post_webhook(user.client, dm_payload("oi", mid="a1", sender="111"))
    post_webhook(user.client, dm_payload("oi", mid="b1", sender="222"))
    drain_jobs()
    a, b = contact_id_for("111"), contact_id_for("222")
    user.put(f"/api/contacts/{a}", json={"tags": ["vip"]})
    user.put(f"/api/contacts/{b}", json={"tags": ["vip"]})
    return a, b


def test_broadcast_sends_to_window_and_skips_others(user, connected_account, meta_mock):
    a, b = _two_contacts(user)
    with db.connection() as conn:
        conn.execute("update contacts set last_inbound_at = now() - interval '2 days' where id = %s", (b,))

    preview = user.post("/api/broadcasts/audience-preview", json={"tags": ["vip"]}).get_json()["data"]
    assert preview == {"total": 2, "eligible": 1}

    created = user.post("/api/broadcasts", json={
        "name": "Promo", "text": "Promoção hoje!", "audience": {"tags": ["VIP"]},
        "buttons": [{"title": "Ver ofertas", "url": "https://loja.com/ofertas"}],
    })
    assert created.status_code == 201, created.get_json()
    bid = created.get_json()["data"]["id"]
    assert created.get_json()["data"]["audience"] == {"tags": ["vip"]}

    sent = user.post(f"/api/broadcasts/{bid}/send", json={})
    assert sent.status_code == 200, sent.get_json()
    assert sent.get_json()["data"]["status"] == "sending"
    drain_jobs()

    data = user.get(f"/api/broadcasts/{bid}").get_json()["data"]
    assert data["status"] == "done"
    assert (data["total_count"], data["sent_count"], data["skipped_count"], data["failed_count"]) == (2, 1, 1, 0)
    call = meta_mock.named("send_button_template")[0][1]
    assert call[1] == "111" and call[3][0]["url"].startswith("https://app.example.com/r/")

    recipients = user.get(f"/api/broadcasts/{bid}/recipients?status=skipped").get_json()["data"]["items"]
    assert len(recipients) == 1 and "24h" in recipients[0]["reason"]
    assert user.put(f"/api/broadcasts/{bid}", json={"text": "x"}).status_code == 409


def test_broadcast_schedule_cancel_and_validation(user, connected_account, meta_mock):
    _two_contacts(user)
    bid = user.post("/api/broadcasts", json={"name": "Vazio"}).get_json()["data"]["id"]
    assert user.post(f"/api/broadcasts/{bid}/send", json={}).status_code == 400  # sem texto

    user.put(f"/api/broadcasts/{bid}", json={"text": "Amanhã tem novidade"})
    scheduled = user.post(f"/api/broadcasts/{bid}/send", json={"scheduled_at": "2099-01-01T12:00:00Z"})
    assert scheduled.get_json()["data"]["status"] == "scheduled"
    drain_jobs()
    assert not meta_mock.named("send_text_message")

    # Cancelar o agendamento volta para rascunho; o job antigo não envia nada
    assert user.post(f"/api/broadcasts/{bid}/cancel").get_json()["data"]["status"] == "draft"
    expire_waits()
    assert not meta_mock.named("send_text_message")

    assert user.post(f"/api/broadcasts/{bid}/send", json={}).status_code == 200
    drain_jobs()
    data = user.get(f"/api/broadcasts/{bid}").get_json()["data"]
    assert data["status"] == "done" and data["sent_count"] == 2
    assert len(meta_mock.named("send_text_message")) == 2
    assert len(user.get(f"/api/inbox/conversations/{contact_id_for('111')}").get_json()["data"]["messages"]) == 2


def test_broadcasts_are_private(user, other_user, connected_account):
    bid = user.post("/api/broadcasts", json={"name": "Meu"}).get_json()["data"]["id"]
    assert other_user.get(f"/api/broadcasts/{bid}").status_code == 404
    assert other_user.post(f"/api/broadcasts/{bid}/send", json={}).status_code == 404
    assert other_user.get("/api/broadcasts").get_json()["data"] == []
