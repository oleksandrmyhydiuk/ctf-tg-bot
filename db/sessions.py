import time

from db.core import conn


async def get_session(user_id: int):
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT s.*, t.title, t.steps_json, t.reward_points
            FROM active_sessions s JOIN tasks t ON t.id = s.task_id
            WHERE s.user_id = ?
            """,
            (user_id,),
        )
        return await cur.fetchone()


async def create_session(user_id: int, task_id: int, container_id: str) -> None:
    """Raises sqlite3.IntegrityError if a session already exists for the user."""
    async with conn() as db:
        await db.execute(
            "INSERT INTO active_sessions (user_id, task_id, container_id, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, task_id, container_id, time.time()),
        )
        await db.commit()


async def set_cwd(user_id: int, cwd: str) -> None:
    async with conn() as db:
        await db.execute("UPDATE active_sessions SET cwd=? WHERE user_id=?", (cwd, user_id))
        await db.commit()


async def advance_step(user_id: int) -> None:
    async with conn() as db:
        await db.execute("UPDATE active_sessions SET step = step + 1 WHERE user_id=?", (user_id,))
        await db.commit()


async def set_hint_mask(user_id: int, mask: int) -> None:
    async with conn() as db:
        await db.execute("UPDATE active_sessions SET hint_mask=? WHERE user_id=?", (mask, user_id))
        await db.commit()


async def delete_session(user_id: int) -> None:
    async with conn() as db:
        await db.execute("DELETE FROM active_sessions WHERE user_id=?", (user_id,))
        await db.commit()


async def count_sessions() -> int:
    async with conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM active_sessions")
        return (await cur.fetchone())[0]


async def all_sessions():
    async with conn() as db:
        cur = await db.execute(
            "SELECT s.*, u.tg_id FROM active_sessions s JOIN users u ON u.id = s.user_id"
        )
        return await cur.fetchall()


async def expired_sessions(cutoff: float):
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT s.*, u.tg_id FROM active_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.created_at < ?
            """,
            (cutoff,),
        )
        return await cur.fetchall()


async def complete_task(user_id: int, task_id: int, points: int) -> int:
    """Deletes the session and awards points (only on the first solve).
    Returns the number of points actually awarded."""
    async with conn() as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO solved (user_id, task_id, solved_at) VALUES (?, ?, ?)",
            (user_id, task_id, time.time()),
        )
        awarded = 0
        if cur.rowcount:
            await db.execute("UPDATE users SET score = score + ? WHERE id = ?", (points, user_id))
            awarded = points
        await db.execute("DELETE FROM active_sessions WHERE user_id=?", (user_id,))
        await db.commit()
        return awarded


async def award_points(user_id: int, task_id: int, points: int) -> int:
    """Awards points for a task (only on the first solve) without deleting active_sessions."""
    async with conn() as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO solved (user_id, task_id, solved_at) VALUES (?, ?, ?)",
            (user_id, task_id, time.time()),
        )
        awarded = 0
        if cur.rowcount:
            await db.execute("UPDATE users SET score = score + ? WHERE id = ?", (points, user_id))
            awarded = points
        await db.commit()
        return awarded
