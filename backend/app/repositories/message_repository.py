from app.db import Jsonb

CTR_COLUMNS = """
    count(*) filter (where m.status = 'sent') as sent,
    count(*) filter (where m.status = 'sent' and m.trackable) as trackable,
    count(*) filter (where m.status = 'sent' and m.trackable and m.clicked_at is not null) as clicked
"""


def insert_outbound(
    conn, *, message_id: str, user_id: str, account_id: str, contact_id: str, source: str, kind: str,
    text: str, buttons: list, trackable: bool, workflow_id: str | None = None, node_id: str | None = None,
    execution_id: str | None = None, broadcast_id: str | None = None,
) -> None:
    conn.execute(
        """
        insert into messages (id, user_id, instagram_account_id, contact_id, direction, source, kind, text, buttons,
                              status, trackable, workflow_id, node_id, execution_id, broadcast_id)
        values (%s, %s, %s, %s, 'out', %s, %s, %s, %s, 'sending', %s, %s, %s, %s, %s)
        """,
        (message_id, user_id, account_id, contact_id, source, kind, text, Jsonb(buttons), trackable,
         workflow_id, node_id, execution_id, broadcast_id),
    )


def mark_sent(conn, message_id: str, account_id: str, mid: str | None) -> None:
    if mid:
        # O eco do webhook pode ter chegado antes da resposta da Meta: fica só a nossa linha
        conn.execute(
            "delete from messages where instagram_account_id = %s and mid = %s and id <> %s and source = 'instagram_app'",
            (account_id, mid, message_id),
        )
    conn.execute("update messages set status = 'sent', mid = %s where id = %s", (mid, message_id))


def mark_failed(conn, message_id: str, error: str) -> None:
    conn.execute("update messages set status = 'failed', error = %s where id = %s", (error[:500], message_id))


def insert_inbound_if_new(
    conn, *, user_id: str, account_id: str, contact_id: str, kind: str, text: str, mid: str | None,
) -> bool:
    row = conn.execute(
        """
        insert into messages (user_id, instagram_account_id, contact_id, direction, source, kind, text, mid, status)
        values (%s, %s, %s, 'in', 'contact', %s, %s, %s, 'received')
        on conflict (instagram_account_id, mid) where mid is not null do nothing
        returning id
        """,
        (user_id, account_id, contact_id, kind, text, mid),
    ).fetchone()
    return row is not None


def insert_echo_if_new(conn, *, user_id: str, account_id: str, contact_id: str, text: str, mid: str | None) -> bool:
    """Mensagem enviada pelo app do Instagram (eco). As enviadas pela plataforma já existem (mesmo mid)."""
    row = conn.execute(
        """
        insert into messages (user_id, instagram_account_id, contact_id, direction, source, kind, text, mid, status)
        values (%s, %s, %s, 'out', 'instagram_app', 'text', %s, %s, 'sent')
        on conflict (instagram_account_id, mid) where mid is not null do nothing
        returning id
        """,
        (user_id, account_id, contact_id, text, mid),
    ).fetchone()
    return row is not None


def get(conn, message_id: str) -> dict | None:
    return conn.execute("select * from messages where id = %s", (message_id,)).fetchone()


def mark_clicked(conn, message_id: str) -> None:
    conn.execute("update messages set clicked_at = coalesce(clicked_at, now()) where id = %s", (message_id,))


def list_for_contact(conn, user_id: str, contact_id: str, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        """
        select id, direction, source, kind, text, buttons, status, error, workflow_id, broadcast_id,
               trackable, clicked_at, created_at
        from messages where user_id = %s and contact_id = %s
        order by created_at desc limit %s
        """,
        (user_id, contact_id, limit),
    ).fetchall()
    return list(reversed(rows))


# --- links rastreados -----------------------------------------------------------

def add_link(conn, user_id: str, message_id: str, code: str, url: str) -> None:
    conn.execute(
        "insert into tracked_links (code, user_id, message_id, url) values (%s, %s, %s, %s)",
        (code, user_id, message_id, url),
    )


def get_link(conn, code: str) -> dict | None:
    return conn.execute("select * from tracked_links where code = %s", (code,)).fetchone()


def register_click(conn, link_id: int, message_id: str) -> None:
    conn.execute(
        """update tracked_links set clicks = clicks + 1, first_clicked_at = coalesce(first_clicked_at, now()),
               last_clicked_at = now() where id = %s""",
        (link_id,),
    )
    mark_clicked(conn, message_id)


# --- métricas -------------------------------------------------------------------

def ctr_for_user(conn, user_id: str, days: int) -> dict:
    return conn.execute(
        f"""select {CTR_COLUMNS} from messages m
            where m.user_id = %s and m.direction = 'out' and m.created_at > now() - make_interval(days => %s)""",
        (user_id, days),
    ).fetchone()


def ctr_by_node(conn, user_id: str, workflow_id: str) -> list[dict]:
    return conn.execute(
        f"""select m.node_id, {CTR_COLUMNS} from messages m
            where m.user_id = %s and m.workflow_id = %s and m.direction = 'out'
            group by m.node_id""",
        (user_id, workflow_id),
    ).fetchall()


def top_links(conn, user_id: str, days: int, limit: int = 5) -> list[dict]:
    return conn.execute(
        """
        select l.url, count(*) as sent, count(*) filter (where l.clicks > 0) as clicked, sum(l.clicks) as clicks
        from tracked_links l join messages m on m.id = l.message_id
        where l.user_id = %s and m.status = 'sent' and l.created_at > now() - make_interval(days => %s)
        group by l.url order by clicked desc, sent desc limit %s
        """,
        (user_id, days, limit),
    ).fetchall()
