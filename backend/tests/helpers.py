def node(node_id, node_type, config=None, x=0, y=0):
    return {"id": node_id, "type": node_type, "position": {"x": x, "y": y}, "data": {"config": config or {}}}


def edge(source, target, handle=None):
    e = {"id": f"{source}-{handle or 'default'}-{target}", "source": source, "target": target}
    if handle:
        e["sourceHandle"] = handle
    return e


def dm_graph_with_condition():
    """Mensagem -> Condição (contém 'preço') -> Sim: envia preço / Não: IA -> envia resposta da IA."""
    return {
        "nodes": [
            node("t", "trigger.message_received"),
            node("c", "condition.check", {"left": "{{message.text}}", "operator": "contains", "value": "preço"}),
            node("yes", "action.send_message", {"text": "Oi {{contact.username}}, custa R$ 10."}),
            node("ai", "action.ai", {"instructions": "Seja breve.", "input": "{{message.text}}",
                                     "save_as": "resposta"}),
            node("no", "action.send_message", {"text": "{{ai.response}}"}),
        ],
        "edges": [
            edge("t", "c"),
            edge("c", "yes", "true"),
            edge("c", "ai", "false"),
            edge("ai", "no"),
        ],
    }


def comment_graph():
    return {
        "nodes": [
            node("t", "trigger.comment_received"),
            node("c", "condition.check", {"left": "{{comment.text}}", "operator": "contains_any",
                                          "value": "eu quero, link"}),
            node("pr", "action.private_reply", {"text": "Oi @{{contact.username}}! Aqui está o link."}),
            node("rc", "action.reply_comment", {"text": "Te enviei por DM!"}),
        ],
        "edges": [edge("t", "c"), edge("c", "pr", "true"), edge("pr", "rc")],
    }
