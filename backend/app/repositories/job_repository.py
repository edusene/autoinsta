from app.db import Jsonb


def enqueue(conn, job_type: str, payload: dict, delay_seconds: float = 0, max_attempts: int = 3) -> int:
    row = conn.execute(
        """insert into jobs (type, payload, run_at, max_attempts)
           values (%s, %s, now() + make_interval(secs => %s), %s) returning id""",
        (job_type, Jsonb(payload), delay_seconds, max_attempts),
    ).fetchone()
    return row["id"]


def claim_next(conn) -> dict | None:
    """Reserva atomicamente o próximo job pronto (seguro com vários workers)."""
    return conn.execute(
        """
        update jobs set status = 'running', locked_at = now(), attempts = attempts + 1
        where id = (
            select id from jobs
            where status = 'queued' and run_at <= now()
            order by run_at
            limit 1
            for update skip locked
        )
        returning *
        """
    ).fetchone()


def mark_done(conn, job_id: int) -> None:
    conn.execute("update jobs set status = 'done', locked_at = null where id = %s", (job_id,))


def mark_failed(conn, job: dict, error: str, retry_delay_seconds: float) -> None:
    if job["attempts"] < job["max_attempts"]:
        conn.execute(
            """update jobs set status = 'queued', locked_at = null, last_error = %s,
                   run_at = now() + make_interval(secs => %s) where id = %s""",
            (error[:2000], retry_delay_seconds, job["id"]),
        )
    else:
        conn.execute(
            "update jobs set status = 'failed', locked_at = null, last_error = %s where id = %s",
            (error[:2000], job["id"]),
        )


def requeue_stale(conn, older_than_seconds: int = 600) -> int:
    """Jobs presos em 'running' (worker morreu) voltam para a fila."""
    cur = conn.execute(
        """update jobs set status = 'queued', locked_at = null
           where status = 'running' and locked_at < now() - make_interval(secs => %s)""",
        (older_than_seconds,),
    )
    return cur.rowcount


def exists_pending(conn, job_type: str) -> bool:
    return (
        conn.execute(
            "select 1 from jobs where type = %s and status in ('queued', 'running') limit 1", (job_type,)
        ).fetchone()
        is not None
    )


def purge_old(conn, days: int = 14) -> int:
    cur = conn.execute(
        "delete from jobs where status = 'done' and updated_at < now() - make_interval(days => %s)", (days,)
    )
    return cur.rowcount
