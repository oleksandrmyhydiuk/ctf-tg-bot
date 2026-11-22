from db.core import conn


async def upsert_user(tg_id: int, username: str | None):
    async with conn() as db:
        await db.execute(
            """
            INSERT INTO users (tg_id, username) VALUES (?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username
            """,
            (tg_id, username),
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        return await cur.fetchone()


async def get_user(tg_id: int):
    async with conn() as db:
        cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        return await cur.fetchone()


async def leaderboard(limit: int = 10):
    async with conn() as db:
        cur = await db.execute(
            "SELECT username, tg_id, score FROM users WHERE score > 0 "
            "ORDER BY score DESC, id ASC LIMIT ?",
            (limit,),
        )
        return await cur.fetchall()
