from app.db import Jsonb

LIST_COLUMNS = """
    e.id, e.workflow_id, w.name as workflow_name, e.contact_id, e.trigger_type, e.status,
    e.error, e.steps_count, e.started_at, e.finished_at,
    extract(epoch from (coalesce(e.finished_at, now()) - e.started_at)) * 1000 as duration_ms
"""


def create(
    conn,
    user_id: str,
    workflow_id: str,
    trigger_type: str,
    trigger_event: dict,
    context: dict,
    contact_id: str | None,
    webhook_event_id: str | None,
) -> dict:
    return conn.execute(
        """
        insert into workflow_executions
            (user_id, workflow_id, trigger_type, trigger_event, context, contact_id, webhook_event_id)
        values (%s, %s, %s, %s, %s, %s, %s) returning *
        """,
        (user_id, workflow_id, trigger_type, Jsonb(trigger_event), Jsonb(context), contact_id, webhook_event_id),
    ).fetchone()


def get_by_id(conn, execution_id: str) -> dict | None:
    return conn.execute("select * from workflow_executions where id = %s", (execution_id,)).fetchone()


def get_for_user(conn, user_id: str, execution_id: str) -> dict | None:
    return conn.execute(
        f"""select {LIST_COLUMNS}, e.trigger_event, e.context, e.current_node_id
            from workflow_executions e join workflows w on w.id = e.workflow_id
            where e.id = %s and e.user_id = %s""",
        (execution_id, user_id),
    ).fetchone()


def save_state(
    conn,
    execution_id: str,
    status: str,
    context: dict,
    current_node_id: str | None,
    steps_count: int,
    error: str | None = None,
) -> None:
    finished = status in ("success", "error", "cancelled")
    conn.execute(
        """
        update workflow_executions set status = %s, context = %s, current_node_id = %s,
            steps_count = %s, error = %s,
            finished_at = case when %s then now() else null end
        where id = %s
        """,
        (status, Jsonb(context), current_node_id, steps_count, error, finished, execution_id),
    )


def add_log(
    conn,
    execution_id: str,
    user_id: str,
    node_id: str | None,
    node_type: str | None,
    level: str,
    message: str,
    data: dict | None = None,
) -> None:
    conn.execute(
        """insert into workflow_execution_logs (execution_id, user_id, node_id, node_type, level, message, data)
           values (%s, %s, %s, %s, %s, %s, %s)""",
        (execution_id, user_id, node_id, node_type, level, message, Jsonb(data or {})),
    )


def list_for_user(
    conn, user_id: str, workflow_id: str | None, status: str | None, limit: int, offset: int
) -> tuple[list[dict], int]:
    where = "e.user_id = %s"
    params: list = [user_id]
    if workflow_id:
        where += " and e.workflow_id = %s"
        params.append(workflow_id)
    if status:
        where += " and e.status = %s"
        params.append(status)
    total = conn.execute(f"select count(*) as n from workflow_executions e where {where}", params).fetchone()["n"]
    rows = conn.execute(
        f"""select {LIST_COLUMNS} from workflow_executions e join workflows w on w.id = e.workflow_id
            where {where} order by e.started_at desc limit %s offset %s""",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def list_logs(conn, user_id: str, execution_id: str) -> list[dict]:
    return conn.execute(
        """select id, node_id, node_type, level, message, data, created_at from workflow_execution_logs
           where execution_id = %s and user_id = %s order by id""",
        (execution_id, user_id),
    ).fetchall()


def stats_for_user(conn, user_id: str, hours: int = 24) -> dict:
    return conn.execute(
        """
        select count(*) as total,
               count(*) filter (where status = 'success') as success,
               count(*) filter (where status = 'error') as errors,
               count(*) filter (where status in ('running', 'waiting')) as in_progress
        from workflow_executions where user_id = %s and started_at > now() - make_interval(hours => %s)
        """,
        (user_id, hours),
    ).fetchone()
