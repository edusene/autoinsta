"""Workflow Engine.

Percorre o grafo a partir do gatilho, executando nó a nó e registrando cada passo.
Delays salvam o estado (status "waiting") e agendam um job "resume_execution";
o worker retoma a execução no horário certo. Nenhum sleep() segura processos.

Esperas por resposta/clique ("Aguardar resposta", "Mensagem com botões") também ficam em
"waiting" no próprio nó: a resposta do contato (webhook) retoma pela saída correspondente e,
se o prazo acabar antes, o job "wait_timeout" retoma pela saída "timeout".
"""
import logging

from app import db
from app.errors import AppError
from app.repositories import execution_repository as exec_repo
from app.repositories import workflow_repository
from app.tasks import queue
from app.workflow.nodes import EXECUTORS, NODE_TYPES, SENDING_NODES, NodeError, Runtime

logger = logging.getLogger(__name__)

MAX_STEPS = 100


def _next_node_id(graph: dict, node_id: str, handle: str) -> str | None:
    for edge in graph.get("edges", []):
        if edge["source"] == node_id and (edge.get("sourceHandle") or "default") == handle:
            return edge["target"]
    return None


def _trigger_node(graph: dict) -> dict | None:
    for node in graph.get("nodes", []):
        if NODE_TYPES.get(node["type"], {}).get("category") == "trigger":
            return node
    return None


def start(
    workflow: dict,
    context: dict,
    trigger_event: dict,
    contact_id: str | None,
    webhook_event_id: str | None,
) -> str:
    """Cria a execução e roda até terminar, falhar ou pausar em um delay. Retorna o execution_id."""
    graph = workflow["graph"]
    trigger = _trigger_node(graph)
    with db.connection() as conn:
        execution = exec_repo.create(
            conn, str(workflow["user_id"]), str(workflow["id"]), workflow["trigger_type"],
            trigger_event, context, contact_id, webhook_event_id,
        )
        exec_repo.add_log(conn, execution["id"], str(workflow["user_id"]), trigger and trigger["id"],
                          trigger and trigger["type"], "info", "Gatilho disparado.", trigger_event)
        workflow_repository.touch_executed(conn, workflow["id"])
    execution_id = str(execution["id"])
    logger.info("Execução iniciada: execution=%s workflow=%s", execution_id, workflow["id"])
    first = _next_node_id(graph, trigger["id"], "default") if trigger else None
    _run(execution_id, workflow, first, context, steps=0)
    return execution_id


def _claim_and_load(execution_id: str, kinds: list[str], node_id: str | None = None,
                    steps: int | None = None) -> tuple[dict, dict] | None:
    """Retoma (atomicamente) uma execução em espera. Cancela se o workflow foi desativado."""
    with db.connection() as conn:
        execution = exec_repo.claim_waiting(conn, execution_id, kinds, node_id, steps)
        if not execution:
            logger.info("Retomada ignorada: execution=%s não está aguardando (%s).", execution_id, kinds)
            return None
        workflow = workflow_repository.get_by_id(conn, execution["workflow_id"])
        if not workflow or workflow["status"] != "active":
            exec_repo.add_log(conn, execution_id, str(execution["user_id"]), None, None, "warning",
                              "Execução cancelada: o workflow foi desativado durante a espera.")
            exec_repo.save_state(conn, execution_id, "cancelled", execution["context"],
                                 execution["current_node_id"], execution["steps_count"])
            return None
    return execution, workflow


def resume(execution_id: str) -> None:
    """Retoma uma execução pausada (chamado pelo worker após um delay)."""
    loaded = _claim_and_load(execution_id, ["delay"])
    if loaded:
        execution, workflow = loaded
        _run(execution_id, workflow, execution["current_node_id"], execution["context"], execution["steps_count"])


def resume_wait(execution_id: str, kinds: list[str], handle: str, message: str,
                updates: dict | None = None, node_id: str | None = None, steps: int | None = None) -> bool:
    """Retoma uma espera de resposta/clique pela saída `handle`. Retorna False se não estava aguardando."""
    loaded = _claim_and_load(execution_id, kinds, node_id, steps)
    if not loaded:
        return False
    execution, workflow = loaded
    ctx = execution["context"]
    for key, value in (updates or {}).items():
        ctx[key] = {**(ctx.get(key) or {}), **value} if isinstance(value, dict) else value
    waiting_node = next((n for n in workflow["graph"].get("nodes", []) if n["id"] == execution["current_node_id"]),
                        None)
    with db.connection() as conn:
        exec_repo.add_log(conn, execution_id, str(execution["user_id"]), execution["current_node_id"],
                          waiting_node and waiting_node["type"], "info", message, {"handle": handle})
    next_id = _next_node_id(workflow["graph"], execution["current_node_id"], handle) if waiting_node else None
    _run(execution_id, workflow, next_id, ctx, execution["steps_count"])
    return True


def wait_timeout(execution_id: str, node_id: str, steps: int) -> None:
    """Prazo da espera acabou sem resposta/clique: segue pela saída "timeout"."""
    resume_wait(execution_id, ["reply", "button"], "timeout",
                "Prazo encerrado sem resposta do contato. Seguindo por \"Sem resposta\".",
                node_id=node_id, steps=steps)


def _run(execution_id: str, workflow: dict, node_id: str | None, ctx: dict, steps: int) -> None:
    user_id = str(workflow["user_id"])
    graph = workflow["graph"]
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    runtime = Runtime(user_id=user_id, account_id=ctx.get("_sys", {}).get("account_id", ""),
                      execution_id=execution_id, workflow_id=str(workflow["id"]),
                      dry_run=bool(ctx.get("_sys", {}).get("dry_run")))

    def log(node, level, message, data=None):
        with db.connection() as conn:
            exec_repo.add_log(conn, execution_id, user_id, node and node["id"], node and node["type"],
                              level, message, data)

    def finish(status, current, error=None):
        with db.connection() as conn:
            exec_repo.save_state(conn, execution_id, status, ctx, current, steps, error)
        log_fn = logger.info if status == "success" else logger.warning
        log_fn("Execução %s: execution=%s workflow=%s%s", status, execution_id, workflow["id"],
               f" erro={error}" if error else "")

    while True:
        if node_id is None:
            log(None, "info", "Fim do fluxo.")
            return finish("success", None)
        if steps >= MAX_STEPS:
            msg = f"Limite de {MAX_STEPS} passos atingido."
            log(None, "error", msg)
            return finish("error", node_id, msg)

        node = nodes_by_id.get(node_id)
        if not node:
            msg = "Um nó do fluxo não existe mais (o workflow foi editado durante a execução)."
            log(None, "error", msg)
            return finish("error", node_id, msg)

        executor = EXECUTORS.get(node["type"])
        if not executor:
            msg = f"Tipo de nó sem executor: {node['type']}."
            log(node, "error", msg)
            return finish("error", node_id, msg)

        steps += 1
        runtime.node_id = node["id"]
        try:
            result = executor(node["data"]["config"], ctx, runtime)
        except NodeError as exc:
            log(node, "error", str(exc))
            return finish("error", node_id, str(exc))
        except AppError as exc:
            log(node, "error", exc.message)
            return finish("error", node_id, exc.message)
        except Exception as exc:  # noqa: BLE001 - registrar e encerrar a execução com segurança
            logger.exception("Erro inesperado no nó %s (execution=%s)", node["id"], execution_id)
            msg = f"Erro inesperado ao executar o nó ({type(exc).__name__})."
            log(node, "error", msg)
            return finish("error", node_id, msg)

        message = result.message
        if runtime.dry_run and node["type"] in SENDING_NODES:
            message += " (simulação: nada foi enviado ao Instagram)"
        log(node, "info", message, result.output)
        if result.stop:
            return finish("success", None)

        if result.wait_for:
            # Fica parado neste nó; a resposta/clique (ou o prazo) escolhe a saída
            with db.connection() as conn:
                exec_repo.save_state(conn, execution_id, "waiting", ctx, node["id"], steps,
                                     waiting_for=result.wait_for, wait_seconds=result.wait_seconds)
                queue.enqueue(conn, "wait_timeout",
                              {"execution_id": execution_id, "node_id": node["id"], "steps": steps},
                              delay_seconds=result.wait_seconds or 0)
            logger.info("Execução aguardando %s por %ss: execution=%s", result.wait_for, result.wait_seconds,
                        execution_id)
            return

        next_id = _next_node_id(graph, node["id"], result.handle)
        if result.delay_seconds:
            if next_id is None:
                log(None, "info", "Fim do fluxo.")
                return finish("success", None)
            with db.connection() as conn:
                exec_repo.save_state(conn, execution_id, "waiting", ctx, next_id, steps, waiting_for="delay",
                                     wait_seconds=result.delay_seconds)
                queue.enqueue(conn, "resume_execution", {"execution_id": execution_id},
                              delay_seconds=result.delay_seconds)
            logger.info("Execução aguardando %ss: execution=%s", result.delay_seconds, execution_id)
            return
        node_id = next_id
