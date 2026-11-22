from typing import Optional

from db.core import conn


async def list_tasks(user_id: int):
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT t.*,
                   EXISTS(SELECT 1 FROM solved s
                          WHERE s.task_id = t.id AND s.user_id = ?) AS done
            FROM tasks t
            ORDER BY CASE t.difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, t.id
            """,
            (user_id,),
        )
        return await cur.fetchall()


async def list_tasks_for_picker():
    async with conn() as db:
        cur = await db.execute(
            "SELECT id, slug, title, difficulty, reward_points FROM tasks "
            "ORDER BY CASE difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id"
        )
        return await cur.fetchall()


async def get_task(task_id: int):
    async with conn() as db:
        cur = await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        return await cur.fetchone()


async def get_task_by_slug(slug: str) -> Optional[dict]:
    async with conn() as db:
        cur = await db.execute("SELECT * FROM tasks WHERE slug=?", (slug,))
        row = await cur.fetchone()
        return dict(row) if row else None
