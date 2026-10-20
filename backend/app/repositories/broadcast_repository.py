from app.db import Jsonb

STATS = """
    coalesce(r.total, 0) as total_count, coalesce(r.sent, 0) as sent_count,
    coalesce(r.skipped, 0) as skipped_count, coalesce(r.failed, 0) as failed_count,
    coalesce(r.pending, 0) as pending_count, coalesce(m.trackable, 0) as trackable_count,
    coalesce(m.clicked, 0) as clicked_count
"""
STATS_JOINS = """
    left join lateral (
        select count(*) as total,
               count(*) filter (where status = 'sent') as sent,
               count(*) filter (where status = 'skipped') as skipped,
               count(*) filter (where status = 'failed') as failed,
               count(*) filter (where status in ('pending', 'processing')) as pending
        from broadcast_recipients where broadcast_id = b.id
    ) r on true
    left join lateral (
        select count(*) filter (where trackable) as trackable,
               count(*) filter (where trackable and clicked_at is not null) as clicked
        from messages where broadcast_id = b.id and status = 'sent'
    ) m on true
"""
EDITABLE = {"name", "text", "buttons", "audience", "track_links"}


def list_for_user(conn, user_id: str) -> list[dict]:
    return conn.execute(
        f"select b.*, {STATS} from broadcasts b {STATS_JOINS} where b.user_id = %s order by b.created_at desc",
        (user_id,),
    ).fetchall()


def get(conn, user_id: str, broadcast_id: str) -> dict | None:
    return conn.execute(
        f"select b.*, {STATS} from broadcasts b {STATS_JOINS} where b.id = %s and b.user_id = %s",
        (broadcast_id, user_id),
    ).fetchone()


def get_by_id(conn, broadcast_id: str) -> dict | None:
    return conn.execute("select * from broadcasts where id = %s", (broadcast_id,)).fetchone()


def create(conn, user_id: str, fields: dict) -> dict:
    row = conn.execute(
        """insert into broadcasts (user_id, name, text, buttons, audience, track_links)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (user_id, fields["name"], fields.get("text") or "", Jsonb(fields.get("buttons") or []),
         Jsonb(fields.get("audience") or {}), fields.get("track_links", True)),
    ).fetchone()
    return get(conn, user_id, str(row["id"]))


def update(conn, user_id: str, broadcast_id: str, fields: dict) -> None:
    sets, values = [], []
    for key, value in fields.items():
        if key not in EDITABLE:
            raise ValueError(f"Campo não permitido: {key}")
        sets.append(f"{key} = %s")
        values.append(Jsonb(value) if key in ("buttons", "audience") else value)
    if sets:
        conn.execute(f"update broadcasts set {', '.join(sets)} where id = %s and user_id = %s",
                     values + [broadcast_id, user_id])


def set_status(conn, broadcast_id: str, status: str, *, scheduled_at=None, error: str | None = None) -> None:
    conn.execute(
        """
        update broadcasts set status = %s,
            scheduled_at = case when %s = 'scheduled' then %s else scheduled_at end,
            started_at = case when %s = 'sending' then coalesce(started_at, now()) else started_at end,
            finished_at = case when %s in ('done', 'cancelled', 'failed') then now() else finished_at end,
            last_error = coalesce(%s, last_error)
        where id = %s
        """,
        (status, status, scheduled_at, status, status, error, broadcast_id),
    )


def delete(conn, user_id: str, broadcast_id: str) -> bool:
    return conn.execute("delete from broadcasts where id = %s and user_id = %s",
                        (broadcast_id, user_id)).rowcount > 0


def add_recipients(conn, broadcast_id: str, contact_ids: list[str]) -> int:
    if not contact_ids:
        return 0
    return conn.execute(
        """insert into broadcast_recipients (broadcast_id, contact_id)
           select %s, unnest(%s::uuid[]) on conflict do nothing""",
        (broadcast_id, contact_ids),
    ).rowcount


def claim_pending(conn, broadcast_id: str, limit: int) -> list[dict]:
    """Reserva destinatários: 'processing' antes de enviar, para um retry nunca enviar duas vezes."""
    return conn.execute(
        """
        update broadcast_recipients r set status = 'processing'
        from contacts c
        where r.id in (select id from broadcast_recipients where broadcast_id = %s and status = 'pending'
                       order by id limit %s for update skip locked)
          and c.id = r.contact_id
        returning r.id, r.contact_id, c.ig_scoped_id, c.username, c.name, c.status as contact_status,
                  coalesce(c.last_inbound_at > now() - interval '24 hours', false) as can_message
        """,
        (broadcast_id, limit),
    ).fetchall()


def finish_recipient(conn, recipient_id: int, status: str, reason: str | None = None,
                     message_id: str | None = None) -> None:
    conn.execute(
        "update broadcast_recipients set status = %s, reason = %s, message_id = %s, processed_at = now() where id = %s",
        (status, reason, message_id, recipient_id),
    )


def skip_pending(conn, broadcast_id: str, reason: str) -> None:
    conn.execute(
        """update broadcast_recipients set status = 'skipped', reason = %s, processed_at = now()
           where broadcast_id = %s and status in ('pending', 'processing')""",
        (reason, broadcast_id),
    )


def has_recipients(conn, broadcast_id: str) -> bool:
    return conn.execute(
        "select 1 from broadcast_recipients where broadcast_id = %s limit 1", (broadcast_id,)
    ).fetchone() is not None


def has_pending(conn, broadcast_id: str) -> bool:
    return conn.execute(
        "select 1 from broadcast_recipients where broadcast_id = %s and status = 'pending' limit 1", (broadcast_id,)
    ).fetchone() is not None


def list_recipients(conn, user_id: str, broadcast_id: str, status: str | None, limit: int,
                    offset: int) -> tuple[list[dict], int]:
    where = "r.broadcast_id = %s and b.user_id = %s"
    params: list = [broadcast_id, user_id]
    if status:
        where += " and r.status = %s"
        params.append(status)
    joins = """from broadcast_recipients r
               join broadcasts b on b.id = r.broadcast_id
               join contacts c on c.id = r.contact_id
               left join messages m on m.id = r.message_id"""
    total = conn.execute(f"select count(*) as n {joins} where {where}", params).fetchone()["n"]
    rows = conn.execute(
        f"""select r.id, r.contact_id, c.username, c.name, r.status, r.reason, r.processed_at, m.clicked_at
            {joins} where {where} order by r.id limit %s offset %s""",
        params + [limit, offset],
    ).fetchall()
    return rows, total
