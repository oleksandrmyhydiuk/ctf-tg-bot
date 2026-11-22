import time
from typing import Optional

from db.core import conn

_ALLOWED_GROUP_SESSION_FIELDS = {
    "mode",
    "task_id",
    "container_id",
    "status",
    "step",
    "cwd",
    "last_actor_tg_id",
    "meta_json",
    "expires_at",
}

_ALLOWED_PARTICIPANT_FIELDS = {
    "role",
    "container_id",
    "step",
    "username",
}


async def create_group_session(
    chat_id: int,
    mode: str,
    task_id: int,
    status: str,
    expires_at: float,
    container_id: Optional[str] = None,
    meta_json: str = "{}",
) -> int:
    async with conn() as db:
        cur = await db.execute(
            """
            INSERT INTO group_sessions
                (chat_id, mode, task_id, container_id, status, meta_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (chat_id, mode, task_id, container_id, status, meta_json, time.time(), expires_at),
        )
        await db.commit()
        return int(cur.lastrowid)


async def get_group_session(chat_id: int) -> Optional[dict]:
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT gs.*,
                   t.slug, t.title, t.description, t.setup_script,
                   t.steps_json, t.reward_points, t.category,
                   t.difficulty, t.mem_limit, t.pids_limit
            FROM group_sessions gs
            JOIN tasks t ON t.id = gs.task_id
            WHERE gs.chat_id = ?
            """,
            (chat_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_group_session_by_id(session_id: int) -> Optional[dict]:
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT gs.*,
                   t.slug, t.title, t.description, t.setup_script,
                   t.steps_json, t.reward_points, t.category,
                   t.difficulty, t.mem_limit, t.pids_limit
            FROM group_sessions gs
            JOIN tasks t ON t.id = gs.task_id
            WHERE gs.id = ?
            """,
            (session_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_group_session(chat_id: int, **fields) -> None:
    valid = {k: v for k, v in fields.items() if k in _ALLOWED_GROUP_SESSION_FIELDS}
    if not valid:
        return
    cols = ", ".join(f"{k}=?" for k in valid)
    vals = list(valid.values()) + [chat_id]
    async with conn() as db:
        await db.execute(f"UPDATE group_sessions SET {cols} WHERE chat_id=?", vals)
        await db.commit()


async def delete_group_session(chat_id: int) -> None:
    async with conn() as db:
        await db.execute(
            "DELETE FROM group_participants WHERE session_id IN "
            "(SELECT id FROM group_sessions WHERE chat_id=?)",
            (chat_id,),
        )
        await db.execute("DELETE FROM group_sessions WHERE chat_id=?", (chat_id,))
        await db.commit()


async def add_group_participant(
    session_id: int,
    user_id: int,
    tg_id: int,
    username: str,
    role: str = "player",
    container_id: Optional[str] = None,
) -> None:
    async with conn() as db:
        await db.execute(
            """
            INSERT INTO group_participants (session_id, user_id, tg_id, username, role, container_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, user_id) DO UPDATE SET
                tg_id=excluded.tg_id,
                username=excluded.username,
                role=excluded.role,
                container_id=COALESCE(excluded.container_id, group_participants.container_id)
            """,
            (session_id, user_id, tg_id, username, role, container_id),
        )
        await db.commit()


async def get_group_participants(session_id: int) -> list[dict]:
    async with conn() as db:
        cur = await db.execute(
            "SELECT * FROM group_participants WHERE session_id=? ORDER BY rowid ASC",
            (session_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def update_group_participant(session_id: int, tg_id: int, **fields) -> None:
    valid = {k: v for k, v in fields.items() if k in _ALLOWED_PARTICIPANT_FIELDS}
    if not valid:
        return
    cols = ", ".join(f"{k}=?" for k in valid)
    vals = list(valid.values()) + [session_id, tg_id]
    async with conn() as db:
        await db.execute(
            f"UPDATE group_participants SET {cols} WHERE session_id=? AND tg_id=?",
            vals,
        )
        await db.commit()


async def get_active_race_for_user(tg_id: int) -> Optional[dict]:
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT gp.session_id, gp.user_id, gp.tg_id, gp.username, gp.role,
                   gp.container_id, gp.step,
                   gs.chat_id, gs.mode, gs.task_id, gs.status, gs.meta_json,
                   gs.created_at, gs.expires_at, gs.step AS session_step
            FROM group_participants gp
            JOIN group_sessions gs ON gs.id = gp.session_id
            WHERE gs.mode = 'race'
              AND gs.status = 'active'
              AND gp.tg_id = ?
              AND gp.container_id IS NOT NULL
              AND gp.role != 'forfeited'
            """,
            (tg_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def find_active_koth_defender_session(tg_id: int) -> Optional[dict]:
    """Checks whether the user is a defender in an active Phase 1 (/koth) of any group."""
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT gs.*
            FROM group_participants gp
            JOIN group_sessions gs ON gs.id = gp.session_id
            WHERE gs.mode = 'koth'
              AND gs.status = 'phase1_defend'
              AND gp.tg_id = ?
              AND gp.role = 'defender'
            ORDER BY gs.id DESC LIMIT 1
            """,
            (tg_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def count_all_containers() -> int:
    async with conn() as db:
        cur = await db.execute(
            """
            SELECT COUNT(DISTINCT container_id) FROM (
                SELECT container_id FROM active_sessions
                WHERE container_id IS NOT NULL AND container_id != ''
                UNION
                SELECT container_id FROM group_sessions
                WHERE container_id IS NOT NULL AND container_id != ''
                UNION
                SELECT container_id FROM group_participants
                WHERE container_id IS NOT NULL AND container_id != ''
            )
            """
        )
        return int((await cur.fetchone())[0])


async def all_tracked_containers() -> list[dict]:
    async with conn() as db:
        results: list[dict] = []
        seen: set[str] = set()

        cur = await db.execute(
            "SELECT s.*, u.tg_id FROM active_sessions s JOIN users u ON u.id = s.user_id"
        )
        for r in await cur.fetchall():
            cid = r["container_id"]
            if cid:
                seen.add(cid)
                results.append(
                    {
                        "source": "solo",
                        "container_id": cid,
                        "user_id": r["user_id"],
                        "tg_id": r["tg_id"],
                        "chat_id": None,
                        "session_id": r["id"],
                    }
                )

        cur = await db.execute(
            "SELECT * FROM group_sessions WHERE container_id IS NOT NULL AND container_id != ''"
        )
        for r in await cur.fetchall():
            cid = r["container_id"]
            if cid and cid not in seen:
                seen.add(cid)
                results.append(
                    {
                        "source": "group",
                        "container_id": cid,
                        "user_id": None,
                        "tg_id": None,
                        "chat_id": r["chat_id"],
                        "session_id": r["id"],
                        "mode": r["mode"],
                    }
                )

        cur = await db.execute(
            """
            SELECT gp.*, gs.chat_id, gs.mode
            FROM group_participants gp
            JOIN group_sessions gs ON gs.id = gp.session_id
            WHERE gp.container_id IS NOT NULL AND gp.container_id != ''
            """
        )
        for r in await cur.fetchall():
            cid = r["container_id"]
            if cid and cid not in seen:
                seen.add(cid)
                results.append(
                    {
                        "source": "participant",
                        "container_id": cid,
                        "user_id": r["user_id"],
                        "tg_id": r["tg_id"],
                        "chat_id": r["chat_id"],
                        "session_id": r["session_id"],
                        "mode": r["mode"],
                    }
                )

        return results


async def expired_group_sessions(ttl_now: float) -> list[dict]:
    async with conn() as db:
        cur = await db.execute(
            "SELECT * FROM group_sessions WHERE expires_at < ?",
            (ttl_now,),
        )
        return [dict(r) for r in await cur.fetchall()]
