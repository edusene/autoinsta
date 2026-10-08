from app.workflow.validator import normalize_graph, validate_graph
from tests.helpers import comment_graph, dm_graph_with_condition, edge, node


def check(graph):
    return validate_graph(normalize_graph(graph))


def messages(result):
    return " | ".join(e["message"] for e in result["errors"])


def test_valid_dm_workflow():
    result = check(dm_graph_with_condition())
    assert result["valid"], result
    assert result["trigger_type"] == "trigger.message_received"


def test_valid_comment_workflow():
    assert check(comment_graph())["valid"]


def test_requires_exactly_one_trigger():
    assert "Adicione um gatilho" in messages(check({"nodes": [node("a", "action.end")], "edges": []}))
    two = {"nodes": [node("a", "trigger.message_received"), node("b", "trigger.comment_received")], "edges": []}
    assert "apenas um gatilho" in messages(check(two))


def test_trigger_must_be_connected():
    assert "Conecte o gatilho" in messages(check({"nodes": [node("t", "trigger.message_received")], "edges": []}))


def test_unknown_node_type():
    graph = {"nodes": [node("t", "trigger.message_received"), node("x", "action.hack")], "edges": [edge("t", "x")]}
    assert "desconhecido" in messages(check(graph))


def test_required_fields_and_limits():
    graph = {
        "nodes": [
            node("t", "trigger.message_received"),
            node("m", "action.send_message", {"text": ""}),
            node("d", "action.delay", {"seconds": 999999}),
        ],
        "edges": [edge("t", "m"), edge("m", "d")],
    }
    msg = messages(check(graph))
    assert "Preencha o campo 'Mensagem'" in msg
    assert "no máximo" in msg


def test_invalid_variable_name():
    graph = {
        "nodes": [node("t", "trigger.message_received"),
                  node("v", "action.set_variable", {"name": "meu nome", "mode": "set"})],
        "edges": [edge("t", "v")],
    }
    assert "apenas letras" in messages(check(graph))


def test_cycle_detection():
    graph = {
        "nodes": [node("t", "trigger.message_received"),
                  node("a", "action.set_variable", {"name": "a", "mode": "set"}),
                  node("b", "action.set_variable", {"name": "b", "mode": "set"})],
        "edges": [edge("t", "a"), edge("a", "b"), edge("b", "a")],
    }
    assert "ciclo" in messages(check(graph))


def test_edge_into_trigger_and_invalid_handle():
    graph = {
        "nodes": [node("t", "trigger.message_received"), node("e", "action.end"),
                  node("c", "condition.check", {"left": "x", "operator": "contains"})],
        "edges": [edge("t", "c"), edge("c", "t", "true"), edge("c", "e", "maybe")],
    }
    msg = messages(check(graph))
    assert "não pode receber conexões" in msg
    assert "Saída 'maybe' inválida" in msg


def test_one_connection_per_output():
    graph = {
        "nodes": [node("t", "trigger.message_received"), node("a", "action.end"), node("b", "action.end")],
        "edges": [edge("t", "a"), edge("t", "b")],
    }
    assert "apenas uma conexão" in messages(check(graph))


def test_meta_rules_actions_vs_trigger():
    # Não é possível iniciar DM a partir de comentário: a API oficial exige resposta privada.
    graph = {
        "nodes": [node("t", "trigger.comment_received"), node("m", "action.send_message", {"text": "oi"})],
        "edges": [edge("t", "m")],
    }
    assert "não pode ser usado com o gatilho" in messages(check(graph))
    graph = {
        "nodes": [node("t", "trigger.message_received"), node("p", "action.private_reply", {"text": "oi"})],
        "edges": [edge("t", "p")],
    }
    assert "não pode ser usado com o gatilho" in messages(check(graph))


def test_unreachable_node_is_warning_only():
    graph = dm_graph_with_condition()
    graph["nodes"].append(node("solto", "action.end"))
    result = check(graph)
    assert result["valid"]
    assert any(w["node_id"] == "solto" for w in result["warnings"])


def test_normalize_strips_unknown_fields():
    raw = {"nodes": [{"id": "t", "type": "trigger.message_received", "position": {"x": "10", "y": 5},
                      "data": {"config": {}, "label": "x", "evil": "<script>"}, "selected": True}],
           "edges": [], "viewport": {"zoom": 2}}
    normalized = normalize_graph(raw)
    assert normalized == {"nodes": [{"id": "t", "type": "trigger.message_received",
                                     "position": {"x": 10.0, "y": 5.0}, "data": {"config": {}}}], "edges": []}
