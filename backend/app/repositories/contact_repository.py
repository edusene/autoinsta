from app.db import Jsonb

# A Meta só permite enviar DM até 24h depois da última mensagem do contato
WINDOW_OPEN = "coalesce(last_inbound_at > now() - interval '24 hours', false)"
EDITABLE_FIELDS = {"name", "notes", "status", "tags", "automation_paused"}


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
        returning *, (xmax = 0) as inserted
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


def list_for_user(
    conn, user_id: str, search: str | None, limit: int, offset: int, tag: str | None = None,
) -> tuple[list[dict], int]:
    where = "user_id = %s"
    params: list = [user_id]
    if search:
        where += " and (username ilike %s or name ilike %s)"
        like = f"%{search.replace('%', '').replace('_', '')}%"
        params += [like, like]
    if tag:
        where += " and %s = any(tags)"
        params.append(tag)
    total = conn.execute(f"select count(*) as n from contacts where {where}", params).fetchone()["n"]
    rows = conn.execute(
        f"""select *, {WINDOW_OPEN} as can_message from contacts where {where}
            order by last_interaction_at desc nulls last limit %s offset %s""",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def get(conn, user_id: str, contact_id: str) -> dict | None:
    return conn.execute(
        f"select *, {WINDOW_OPEN} as can_message, last_inbound_at + interval '24 hours' as window_expires_at "
        "from contacts where id = %s and user_id = %s",
        (contact_id, user_id),
    ).fetchone()


def list_events(conn, user_id: str, contact_id: str, limit: int = 50) -> list[dict]:
    return conn.execute(
        """select id, event_type, summary, data, created_at from contact_events
           where contact_id = %s and user_id = %s order by created_at desc limit %s""",
        (contact_id, user_id, limit),
    ).fetchall()


def count_for_user(conn, user_id: str) -> int:
    return conn.execute("select count(*) as n from contacts where user_id = %s", (user_id,)).fetchone()["n"]


def get_by_ig_id(conn, account_id: str, ig_scoped_id: str) -> dict | None:
    return conn.execute(
        "select * from contacts where instagram_account_id = %s and ig_scoped_id = %s", (account_id, ig_scoped_id)
    ).fetchone()


def update_fields(conn, user_id: str, contact_id: str, fields: dict) -> dict | None:
    sets, values = [], []
    for key, value in fields.items():
        if key not in EDITABLE_FIELDS:
            raise ValueError(f"Campo não permitido: {key}")
        sets.append(f"{key} = %s")
        values.append(value)
    if not sets:
        return get(conn, user_id, contact_id)
    conn.execute(f"update contacts set {', '.join(sets)} where id = %s and user_id = %s",
                 values + [contact_id, user_id])
    return get(conn, user_id, contact_id)


def add_tag(conn, contact_id: str, tag: str) -> None:
    conn.execute(
        "update contacts set tags = array_append(tags, %s) where id = %s and not (%s = any(tags))",
        (tag, contact_id, tag),
    )


def remove_tag(conn, contact_id: str, tag: str) -> None:
    conn.execute("update contacts set tags = array_remove(tags, %s) where id = %s", (tag, contact_id))


def get_tags(conn, contact_id: str) -> list[str]:
    row = conn.execute("select tags from contacts where id = %s", (contact_id,)).fetchone()
    return list(row["tags"]) if row else []


def tag_counts(conn, user_id: str) -> list[dict]:
    return conn.execute(
        """select t.tag, count(*) as count from contacts, unnest(tags) as t(tag)
           where user_id = %s group by t.tag order by count desc, t.tag""",
        (user_id,),
    ).fetchall()


# --- caixa de entrada -------------------------------------------------------------

def touch_inbound(conn, contact_id: str, preview: str) -> None:
    conn.execute(
        """update contacts set last_inbound_at = now(), last_message_at = now(), last_message_preview = %s,
               unread_count = unread_count + 1 where id = %s""",
        (preview[:200], contact_id),
    )


def touch_outbound(conn, contact_id: str, preview: str) -> None:
    conn.execute(
        "update contacts set last_message_at = now(), last_message_preview = %s where id = %s",
        (preview[:200], contact_id),
    )


def mark_read(conn, user_id: str, contact_id: str) -> None:
    conn.execute("update contacts set unread_count = 0 where id = %s and user_id = %s", (contact_id, user_id))


def list_conversations(
    conn, user_id: str, search: str | None, unread_only: bool, limit: int, offset: int,
) -> tuple[list[dict], int]:
    where = "user_id = %s and last_message_at is not null"
    params: list = [user_id]
    if search:
        where += " and (username ilike %s or name ilike %s)"
        like = f"%{search.replace('%', '').replace('_', '')}%"
        params += [like, like]
    if unread_only:
        where += " and unread_count > 0"
    total = conn.execute(f"select count(*) as n from contacts where {where}", params).fetchone()["n"]
    rows = conn.execute(
        f"""select id, username, name, tags, status, automation_paused, last_message_at, last_message_preview,
                   unread_count, last_inbound_at, {WINDOW_OPEN} as can_message
            from contacts where {where} order by last_message_at desc limit %s offset %s""",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def unread_total(conn, user_id: str) -> int:
    return conn.execute(
        "select count(*) as n from contacts where user_id = %s and unread_count > 0", (user_id,)
    ).fetchone()["n"]


# --- público de disparos ----------------------------------------------------------

def _audience_where(tags: list[str]) -> tuple[str, list]:
    where = "user_id = %s and instagram_account_id = %s and status = 'active'"
    if tags:
        return where + " and tags && %s", [tags]
    return where, []


def audience_counts(conn, user_id: str, account_id: str, tags: list[str]) -> dict:
    where, extra = _audience_where(tags)
    return conn.execute(
        f"select count(*) as total, count(*) filter (where {WINDOW_OPEN}) as eligible from contacts where {where}",
        [user_id, account_id, *extra],
    ).fetchone()


def audience_ids(conn, user_id: str, account_id: str, tags: list[str]) -> list[str]:
    where, extra = _audience_where(tags)
    rows = conn.execute(f"select id from contacts where {where}", [user_id, account_id, *extra]).fetchall()
    return [str(r["id"]) for r in rows]
