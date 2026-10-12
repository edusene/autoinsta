"""Normalização e validação do grafo do workflow.

- normalize_graph(): mantém apenas os campos conhecidos (o frontend não grava lixo no banco).
- validate_graph(): devolve erros (impedem ativação) e avisos.
"""
from app.workflow.nodes import IDENTIFIER_RE, NODE_TYPES

MAX_NODES = 100
MAX_EDGES = 200


def _num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_graph(graph: dict | None) -> dict:
    graph = graph or {}
    nodes = []
    for raw in (graph.get("nodes") or [])[:MAX_NODES]:
        if not isinstance(raw, dict):
            continue
        position = raw.get("position") if isinstance(raw.get("position"), dict) else {}
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        config = data.get("config") if isinstance(data.get("config"), dict) else {}
        nodes.append({
            "id": str(raw.get("id", ""))[:64],
            "type": str(raw.get("type", ""))[:64],
            "position": {"x": _num(position.get("x")), "y": _num(position.get("y"))},
            "data": {"config": {str(k)[:64]: v for k, v in config.items()}},
        })
    edges = []
    for raw in (graph.get("edges") or [])[:MAX_EDGES]:
        if not isinstance(raw, dict):
            continue
        edges.append({
            "id": str(raw.get("id", ""))[:128],
            "source": str(raw.get("source", ""))[:64],
            "target": str(raw.get("target", ""))[:64],
            "sourceHandle": (str(raw["sourceHandle"])[:32] if raw.get("sourceHandle") else None),
        })
    return {"nodes": nodes, "edges": edges}


def trigger_type_of(graph: dict) -> str | None:
    for node in graph.get("nodes", []):
        if NODE_TYPES.get(node["type"], {}).get("category") == "trigger":
            return node["type"]
    return None


def _validate_config(node: dict, definition: dict, add_error) -> None:
    config = node["data"]["config"]
    for f in definition["fields"]:
        name, label = f["name"], f["label"]
        value = config.get(name)
        empty = value is None or (isinstance(value, str) and not value.strip())
        if empty:
            if f.get("required"):
                add_error(node["id"], f"Preencha o campo '{label}'.")
            continue
        ftype = f["type"]
        if ftype in ("text", "textarea"):
            if not isinstance(value, str):
                add_error(node["id"], f"'{label}' deve ser texto.")
                continue
            if f.get("max_length") and len(value) > f["max_length"]:
                add_error(node["id"], f"'{label}' excede {f['max_length']} caracteres.")
            if f.get("pattern") == "identifier" and not IDENTIFIER_RE.match(value):
                add_error(node["id"], f"'{label}' deve conter apenas letras, números e _ (sem espaços).")
        elif ftype == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                add_error(node["id"], f"'{label}' deve ser um número.")
                continue
            if "min" in f and value < f["min"]:
                add_error(node["id"], f"'{label}' deve ser no mínimo {f['min']}.")
            if "max" in f and value > f["max"]:
                add_error(node["id"], f"'{label}' deve ser no máximo {f['max']}.")
        elif ftype == "select":
            if value not in {o["value"] for o in f["options"]}:
                add_error(node["id"], f"Valor inválido em '{label}'.")
        elif ftype == "checkbox" and not isinstance(value, bool):
            add_error(node["id"], f"'{label}' deve ser verdadeiro ou falso.")


def validate_graph(graph: dict) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []

    def add_error(node_id, message):
        errors.append({"node_id": node_id, "message": message})

    def add_warning(node_id, message):
        warnings.append({"node_id": node_id, "message": message})

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    by_id: dict[str, dict] = {}

    for node in nodes:
        if not node["id"]:
            add_error(None, "Existe um nó sem ID.")
            continue
        if node["id"] in by_id:
            add_error(node["id"], "ID de nó duplicado.")
            continue
        by_id[node["id"]] = node
        definition = NODE_TYPES.get(node["type"])
        if not definition:
            add_error(node["id"], f"Tipo de nó desconhecido: {node['type']}.")
            continue
        _validate_config(node, definition, add_error)

    triggers = [n for n in by_id.values() if NODE_TYPES.get(n["type"], {}).get("category") == "trigger"]
    if not triggers:
        add_error(None, "Adicione um gatilho ao workflow.")
    elif len(triggers) > 1:
        add_error(None, "O workflow deve ter apenas um gatilho.")
    trigger_type = triggers[0]["type"] if len(triggers) == 1 else None

    # Compatibilidade ação x gatilho (regras oficiais da Meta)
    if trigger_type:
        for node in by_id.values():
            allowed = NODE_TYPES.get(node["type"], {}).get("allowed_triggers")
            if allowed and trigger_type not in allowed:
                label = NODE_TYPES[node["type"]]["label"]
                trigger_label = NODE_TYPES[trigger_type]["label"]
                add_error(node["id"], f"'{label}' não pode ser usado com o gatilho '{trigger_label}'.")

    # Arestas
    adjacency: dict[str, list[str]] = {nid: [] for nid in by_id}
    used_handles: set[tuple[str, str]] = set()
    for edge in edges:
        src, dst = by_id.get(edge["source"]), by_id.get(edge["target"])
        if not src or not dst:
            add_error(None, "Existe uma conexão com um nó inexistente.")
            continue
        if edge["source"] == edge["target"]:
            add_error(src["id"], "Um nó não pode se conectar a ele mesmo.")
            continue
        src_def, dst_def = NODE_TYPES.get(src["type"]), NODE_TYPES.get(dst["type"])
        if not src_def or not dst_def:
            continue
        handle = edge["sourceHandle"] or "default"
        if handle not in src_def["outputs"]:
            add_error(src["id"], f"Saída '{handle}' inválida para '{src_def['label']}'.")
            continue
        if dst_def["category"] == "trigger":
            add_error(dst["id"], "O gatilho não pode receber conexões.")
            continue
        if (src["id"], handle) in used_handles:
            add_error(src["id"], "Cada saída pode ter apenas uma conexão.")
            continue
        used_handles.add((src["id"], handle))
        adjacency[src["id"]].append(dst["id"])

    # Ciclos (DFS com cores)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in by_id}

    def has_cycle(nid: str) -> bool:
        color[nid] = GRAY
        for nxt in adjacency.get(nid, []):
            if color[nxt] == GRAY or (color[nxt] == WHITE and has_cycle(nxt)):
                return True
        color[nid] = BLACK
        return False

    if any(color[n] == WHITE and has_cycle(n) for n in list(by_id)):
        add_error(None, "O workflow possui um ciclo (loop). Remova a conexão que volta para um nó anterior.")

    # Alcance a partir do gatilho
    if len(triggers) == 1:
        trigger = triggers[0]
        if not adjacency.get(trigger["id"]):
            add_error(trigger["id"], "Conecte o gatilho a pelo menos uma ação.")
        reachable, stack = set(), [trigger["id"]]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(adjacency.get(current, []))
        for nid in by_id:
            if nid not in reachable:
                add_warning(nid, "Este nó não está conectado ao fluxo e não será executado.")

    for node in by_id.values():
        if NODE_TYPES.get(node["type"], {}).get("category") == "condition":
            missing = [h for h in ("true", "false") if (node["id"], h) not in used_handles]
            if len(missing) == 2:
                add_warning(node["id"], "A condição não tem nenhum caminho conectado.")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "trigger_type": trigger_type}
