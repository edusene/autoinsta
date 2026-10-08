# Colunas seguras para retornar ao frontend (sem nada relacionado a token).
PUBLIC_COLUMNS = """
    id, user_id, ig_user_id, username, name, account_type, profile_picture_url, status,
    permissions, webhook_subscribed, last_webhook_at, last_error, connected_at,
    disconnected_at, connection_method, created_at, updated_at
"""


def get_for_user(conn, user_id: str) -> dict | None:
    """Conta mais recente do usuário (MVP: uma conta por usuário)."""
    return conn.execute(
        f"select {PUBLIC_COLUMNS} from instagram_accounts where user_id = %s order by updated_at desc limit 1",
        (user_id,),
    ).fetchone()


def get_connected_for_user(conn, user_id: str) -> dict | None:
    return conn.execute(
        f"""select {PUBLIC_COLUMNS} from instagram_accounts
            where user_id = %s and status = 'connected' order by updated_at desc limit 1""",
        (user_id,),
    ).fetchone()


def get_by_id(conn, account_id: str) -> dict | None:
    return conn.execute(f"select {PUBLIC_COLUMNS} from instagram_accounts where id = %s", (account_id,)).fetchone()


def get_by_ig_user_id(conn, ig_user_id: str) -> dict | None:
    return conn.execute(
        f"select {PUBLIC_COLUMNS} from instagram_accounts where ig_user_id = %s", (ig_user_id,)
    ).fetchone()


def upsert_connected(
    conn, user_id: str, profile: dict, permissions: list[str], connection_method: str = "oauth"
) -> dict:
    return conn.execute(
        f"""
        insert into instagram_accounts
            (user_id, ig_user_id, username, name, account_type, profile_picture_url,
             status, permissions, last_error, connected_at, disconnected_at, connection_method)
        values (%s, %s, %s, %s, %s, %s, 'connected', %s, null, now(), null, %s)
        on conflict (ig_user_id) do update set
            user_id = excluded.user_id,
            username = excluded.username,
            name = excluded.name,
            account_type = excluded.account_type,
            profile_picture_url = excluded.profile_picture_url,
            status = 'connected',
            permissions = excluded.permissions,
            last_error = null,
            connected_at = now(),
            disconnected_at = null,
            connection_method = excluded.connection_method
        returning {PUBLIC_COLUMNS}
        """,
        (
            user_id,
            profile["user_id"],
            profile.get("username"),
            profile.get("name"),
            profile.get("account_type"),
            profile.get("profile_picture_url"),
            permissions,
            connection_method,
        ),
    ).fetchone()


def set_status(conn, account_id: str, status: str, last_error: str | None = None) -> None:
    conn.execute(
        """
        update instagram_accounts set
            status = %s,
            last_error = %s,
            disconnected_at = case when %s = 'disconnected' then now() else disconnected_at end,
            webhook_subscribed = case when %s = 'disconnected' then false else webhook_subscribed end
        where id = %s
        """,
        (status, last_error, status, status, account_id),
    )


def set_webhook_subscribed(conn, account_id: str, subscribed: bool, last_error: str | None = None) -> None:
    conn.execute(
        "update instagram_accounts set webhook_subscribed = %s, last_error = %s where id = %s",
        (subscribed, last_error, account_id),
    )


def mark_webhook_received(conn, account_id: str) -> None:
    conn.execute("update instagram_accounts set last_webhook_at = now() where id = %s", (account_id,))


def delete_by_ig_user_id(conn, ig_user_id: str) -> None:
    conn.execute("delete from instagram_accounts where ig_user_id = %s", (ig_user_id,))


# --- tokens -----------------------------------------------------------------

def save_token(conn, account_id: str, user_id: str, encrypted: str, expires_at) -> None:
    conn.execute(
        """
        insert into oauth_tokens (instagram_account_id, user_id, access_token_encrypted, expires_at, last_refreshed_at)
        values (%s, %s, %s, %s, now())
        on conflict (instagram_account_id) do update set
            user_id = excluded.user_id,
            access_token_encrypted = excluded.access_token_encrypted,
            expires_at = excluded.expires_at,
            last_refreshed_at = now()
        """,
        (account_id, user_id, encrypted, expires_at),
    )


def get_token(conn, account_id: str) -> dict | None:
    return conn.execute(
        "select access_token_encrypted, expires_at, last_refreshed_at from oauth_tokens where instagram_account_id = %s",
        (account_id,),
    ).fetchone()


def delete_token(conn, account_id: str) -> None:
    conn.execute("delete from oauth_tokens where instagram_account_id = %s", (account_id,))


def list_tokens_to_refresh(conn, within_days: int) -> list[dict]:
    """Tokens que vencem em breve e já têm mais de 24h (regra oficial de refresh)."""
    return conn.execute(
        """
        select t.instagram_account_id, t.access_token_encrypted, t.expires_at
        from oauth_tokens t
        join instagram_accounts a on a.id = t.instagram_account_id
        where a.status = 'connected'
          and t.expires_at is not null
          and t.expires_at > now()
          and t.expires_at < now() + make_interval(days => %s)
          and t.last_refreshed_at < now() - interval '24 hours'
        """,
        (within_days,),
    ).fetchall()
