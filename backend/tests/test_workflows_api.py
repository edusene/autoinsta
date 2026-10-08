from tests.helpers import dm_graph_with_condition, edge, node


def test_create_with_default_trigger_and_list(user):
    resp = user.post("/api/workflows", json={"name": "Atendimento", "description": "DMs"})
    assert resp.status_code == 201
    wf = resp.get_json()["data"]
    assert wf["status"] == "draft"
    assert wf["trigger_type"] == "trigger.message_received"
    assert len(wf["graph"]["nodes"]) == 1

    items = user.get("/api/workflows").get_json()["data"]
    assert [w["name"] for w in items] == ["Atendimento"]
    assert items[0]["executions_count"] == 0


def test_update_graph_and_validate(user):
    wid = user.post("/api/workflows", json={"name": "W"}).get_json()["data"]["id"]
    resp = user.put(f"/api/workflows/{wid}", json={"graph": dm_graph_with_condition(), "name": "W2"})
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["name"] == "W2" and len(data["graph"]["nodes"]) == 5

    result = user.post(f"/api/workflows/{wid}/validate").get_json()["data"]
    assert result["valid"] is True


def test_validate_draft_graph_endpoint(user):
    result = user.post("/api/workflows/validate", json={"graph": {"nodes": [], "edges": []}}).get_json()["data"]
    assert result["valid"] is False


def test_activate_requires_instagram(user):
    wid = user.post("/api/workflows", json={"name": "W", "graph": dm_graph_with_condition()}).get_json()["data"]["id"]
    resp = user.post(f"/api/workflows/{wid}/activate")
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "INSTAGRAM_NOT_CONNECTED"


def test_activate_rejects_invalid_graph(user, connected_account):
    wid = user.post("/api/workflows", json={"name": "W"}).get_json()["data"]["id"]  # só gatilho
    resp = user.post(f"/api/workflows/{wid}/activate")
    assert resp.status_code == 400
    body = resp.get_json()["error"]
    assert body["code"] == "WORKFLOW_INVALID"
    assert body["details"]["errors"]


def test_activate_deactivate_cycle(user, connected_account):
    wid = user.post("/api/workflows", json={"name": "W", "graph": dm_graph_with_condition()}).get_json()["data"]["id"]
    assert user.post(f"/api/workflows/{wid}/activate").get_json()["data"]["status"] == "active"

    # Workflow ativo não aceita grafo inválido
    bad = {"nodes": [node("t", "trigger.message_received")], "edges": []}
    resp = user.put(f"/api/workflows/{wid}", json={"graph": bad})
    assert resp.status_code == 400

    assert user.post(f"/api/workflows/{wid}/deactivate").get_json()["data"]["status"] == "inactive"
    assert user.put(f"/api/workflows/{wid}", json={"graph": bad}).status_code == 200


def test_duplicate_and_delete(user):
    wid = user.post("/api/workflows", json={"name": "Original", "graph": dm_graph_with_condition()}).get_json()["data"]["id"]
    copy = user.post(f"/api/workflows/{wid}/duplicate").get_json()["data"]
    assert copy["name"] == "Original (cópia)"
    assert copy["status"] == "draft"
    assert copy["id"] != wid
    assert len(copy["graph"]["nodes"]) == 5

    assert user.delete(f"/api/workflows/{wid}").status_code == 200
    assert user.get(f"/api/workflows/{wid}").status_code == 404
    assert len(user.get("/api/workflows").get_json()["data"]) == 1


def test_node_types_catalog(user):
    types = {n["type"]: n for n in user.get("/api/workflows/node-types").get_json()["data"]}
    assert {"trigger.message_received", "trigger.comment_received", "action.send_message", "action.ai",
            "condition.check", "action.delay", "action.private_reply"} <= set(types)
    assert types["condition.check"]["outputs"] == ["true", "false"]


def test_graph_is_normalized_on_save(user):
    graph = {"nodes": [{**node("t", "trigger.message_received"), "selected": True, "width": 200}],
             "edges": [], "viewport": {"x": 1}}
    graph["nodes"].append(node("e", "action.end"))
    graph["edges"].append({**edge("t", "e"), "animated": True})
    data = user.post("/api/workflows", json={"name": "N", "graph": graph}).get_json()["data"]
    assert "selected" not in data["graph"]["nodes"][0]
    assert "viewport" not in data["graph"]
    assert "animated" not in data["graph"]["edges"][0]
