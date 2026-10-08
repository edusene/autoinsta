def upsert(conn, user_id: str, email: str | None) -> dict:
    return conn.execute(
        """
        insert into profiles (id, email) values (%s, %s)
        on conflict (id) do update set email = coalesce(excluded.email, profiles.email)
        where profiles.email is distinct from excluded.email
        returning *
        """,
        (user_id, email),
    ).fetchone() or get(conn, user_id)


def get(conn, user_id: str) -> dict | None:
    return conn.execute("select * from profiles where id = %s", (user_id,)).fetchone()
