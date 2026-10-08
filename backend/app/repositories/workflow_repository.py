from app.db import Jsonb

LIST_COLUMNS = "id, user_id, name, description, status, trigger_type, last_executed_at, created_at, updated_at"


def list_for_user(conn, user_id: str) -> list[dict]:
    return conn.execute(
        f"""
        select {', '.join('w.' + c.strip() for c in LIST_COLUMNS.split(','))},
               coalesce(e.total, 0) as executions_count,
               coalesce(e.errors, 0) as errors_count
        from workflows w
        left join lateral (
            select count(*) as total, count(*) filter (where status = 'error') as errors
            from workflow_executions where workflow_id = w.id
        ) e on true
        where w.user_id = %s
        order by w.updated_at desc
        """,
        (user_id,),
    ).fetchall()


def get(conn, user_id: str, workflow_id: str) -> dict | None:
    return conn.execute(
        "select * from workflows where id = %s and user_id = %s", (workflow_id, user_id)
    ).fetchone()


def get_by_id(conn, workflow_id: str) -> dict | None:
    """Uso interno (engine). Rotas devem usar get() com user_id."""
    return conn.execute("select * from workflows where id = %s", (workflow_id,)).fetchone()


def create(conn, user_id: str, name: str, description: str | None, graph: dict, trigger_type: str | None) -> dict:
    return conn.execute(
        """
        insert into workflows (user_id, name, description, graph, trigger_type)
        values (%s, %s, %s, %s, %s) returning *
        """,
        (user_id, name, description, Jsonb(graph), trigger_type),
    ).fetchone()


def update(conn, user_id: str, workflow_id: str, fields: dict) -> dict | None:
    allowed = {"name", "description", "graph", "trigger_type", "status"}
    sets, values = [], []
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"Campo não permitido: {key}")
        sets.append(f"{key} = %s")
        values.append(Jsonb(value) if key == "graph" else value)
    if not sets:
        return get(conn, user_id, workflow_id)
    values += [workflow_id, user_id]
    return conn.execute(
        f"update workflows set {', '.join(sets)}, updated_at = now() where id = %s and user_id = %s returning *",
        values,
    ).fetchone()


def delete(conn, user_id: str, workflow_id: str) -> bool:
    cur = conn.execute("delete from workflows where id = %s and user_id = %s", (workflow_id, user_id))
    return cur.rowcount > 0


def list_active_by_trigger(conn, user_id: str, trigger_type: str) -> list[dict]:
    return conn.execute(
        "select * from workflows where user_id = %s and trigger_type = %s and status = 'active' order by created_at",
        (user_id, trigger_type),
    ).fetchall()


def touch_executed(conn, workflow_id: str) -> None:
    conn.execute("update workflows set last_executed_at = now() where id = %s", (workflow_id,))


def counts_for_user(conn, user_id: str) -> dict:
    return conn.execute(
        """
        select count(*) as total, count(*) filter (where status = 'active') as active
        from workflows where user_id = %s
        """,
        (user_id,),
    ).fetchone()
