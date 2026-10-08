from app.db import Jsonb


def upsert_from_event(
    conn, user_id: str, account_id: str, ig_scoped_id: str, username: str | None, event_type: str
) -> dict:
    return conn.execute(
        """
        insert into contacts (user_id, instagram_account_id, ig_scoped_id, username, last_interaction_at, last_event_type)
        values (%s, %s, %s, %s, now(), %s)
        on conflict (instagram_account_id, ig_scoped_id) do update set
            username = coalesce(excluded.username, contacts.username),
            last_interaction_at = now(),
            last_event_type = excluded.last_event_type
        returning *
        """,
        (user_id, account_id, ig_scoped_id, username, event_type),
    ).fetchone()


def update_profile(conn, contact_id: str, username: str | None, name: str | None, metadata: dict) -> None:
    conn.execute(
        """
        update contacts set
            username = coalesce(%s, username),
            name = coalesce(%s, name),
            metadata = metadata || %s
        where id = %s
        """,
        (username, name, Jsonb(metadata), contact_id),
    )


def add_event(conn, user_id: str, contact_id: str, event_type: str, summary: str | None, data: dict) -> None:
    conn.execute(
        "insert into contact_events (user_id, contact_id, event_type, summary, data) values (%s, %s, %s, %s, %s)",
        (user_id, contact_id, event_type, summary, Jsonb(data)),
    )


def list_for_user(conn, user_id: str, search: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
    where = "user_id = %s"
    params: list = [user_id]
    if search:
        where += " and (username ilike %s or name ilike %s)"
        like = f"%{search.replace('%', '').replace('_', '')}%"
        params += [like, like]
    total = conn.execute(f"select count(*) as n from contacts where {where}", params).fetchone()["n"]
    rows = conn.execute(
        f"""select * from contacts where {where}
            order by last_interaction_at desc nulls last limit %s offset %s""",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def get(conn, user_id: str, contact_id: str) -> dict | None:
    return conn.execute("select * from contacts where id = %s and user_id = %s", (contact_id, user_id)).fetchone()


def list_events(conn, user_id: str, contact_id: str, limit: int = 50) -> list[dict]:
    return conn.execute(
        """select id, event_type, summary, data, created_at from contact_events
           where contact_id = %s and user_id = %s order by created_at desc limit %s""",
        (contact_id, user_id, limit),
    ).fetchall()


def count_for_user(conn, user_id: str) -> int:
    return conn.execute("select count(*) as n from contacts where user_id = %s", (user_id,)).fetchone()["n"]
