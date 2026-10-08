def get(conn, user_id: str) -> dict | None:
    return conn.execute("select * from user_settings where user_id = %s", (user_id,)).fetchone()


def upsert(conn, user_id: str, ai_default_model: str | None) -> dict:
    return conn.execute(
        """
        insert into user_settings (user_id, ai_default_model) values (%s, %s)
        on conflict (user_id) do update set ai_default_model = excluded.ai_default_model
        returning *
        """,
        (user_id, ai_default_model),
    ).fetchone()
