from app.db import Jsonb


def insert_if_new(conn, dedupe_key: str, obj: str, field: str, ig_account_id: str, payload: dict) -> dict | None:
    """Retorna None quando o evento já foi recebido (reenvio da Meta)."""
    return conn.execute(
        """
        insert into webhook_events (dedupe_key, object, field, ig_account_id, payload)
        values (%s, %s, %s, %s, %s)
        on conflict (dedupe_key) do nothing
        returning id
        """,
        (dedupe_key, obj, field, ig_account_id, Jsonb(payload)),
    ).fetchone()


def list_for_account(conn, account_id: str, ig_user_id: str, limit: int) -> list[dict]:
    return conn.execute(
        """
        select w.id, w.dedupe_key, w.field, w.status, w.status_reason, w.payload, w.received_at, w.processed_at,
               (select count(*) from workflow_executions e where e.webhook_event_id = w.id) as executions
        from webhook_events w
        where w.instagram_account_id = %s or w.ig_account_id = %s
        order by w.received_at desc
        limit %s
        """,
        (account_id, ig_user_id, limit),
    ).fetchall()


def get(conn, event_id: str) -> dict | None:
    return conn.execute("select * from webhook_events where id = %s", (event_id,)).fetchone()


def set_status(
    conn,
    event_id: str,
    status: str,
    reason: str | None = None,
    account_id: str | None = None,
    user_id: str | None = None,
) -> None:
    conn.execute(
        """
        update webhook_events set status = %s, status_reason = %s, processed_at = now(),
            instagram_account_id = coalesce(%s, instagram_account_id),
            user_id = coalesce(%s, user_id)
        where id = %s
        """,
        (status, reason, account_id, user_id, event_id),
    )


def count_recent_for_account(conn, account_id: str, hours: int = 24) -> int:
    return conn.execute(
        """select count(*) as n from webhook_events
           where instagram_account_id = %s and received_at > now() - make_interval(hours => %s)""",
        (account_id, hours),
    ).fetchone()["n"]
