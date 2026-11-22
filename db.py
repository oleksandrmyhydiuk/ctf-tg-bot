import json
import time
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

from config import DB_PATH
from tasks_data import TASKS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    score INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,            -- task intro (HTML)
    setup_script TEXT NOT NULL,
    check_script TEXT NOT NULL DEFAULT '', -- deprecated: checks are now in steps_json
    reward_points INTEGER NOT NULL DEFAULT 10
);

-- UNIQUE(user_id): at most one active session per user (race-condition protection)
CREATE TABLE IF NOT EXISTS active_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    container_id TEXT NOT NULL,
    cwd TEXT NOT NULL DEFAULT '/home/student',
    created_at REAL NOT NULL
);

-- Points are awarded only on the first solve of a task
CREATE TABLE IF NOT EXISTS solved (
    user_id INTEGER NOT NULL REFERENCES users(id),
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    solved_at REAL NOT NULL,
    PRIMARY KEY (user_id, task_id)
);

CREATE TABLE IF NOT EXISTS group_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL UNIQUE,
    mode TEXT NOT NULL,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    container_id TEXT,
    status TEXT NOT NULL,
    step INTEGER NOT NULL DEFAULT 0,
    cwd TEXT NOT NULL DEFAULT '/home/student',
    last_actor_tg_id INTEGER,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS group_participants (
    session_id INTEGER NOT NULL REFERENCES group_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    tg_id INTEGER NOT NULL,
    username TEXT,
    role TEXT NOT NULL DEFAULT 'player',
    container_id TEXT,
    step INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, user_id)
);
"""

# Columns added later: applied to existing DBs via ALTER TABLE.
MIGRATIONS = {
    "tasks": [
        ("steps_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("category", "TEXT NOT NULL DEFAULT ''"),
        ("difficulty", "TEXT NOT NULL DEFAULT 'easy'"),
        ("mem_limit", "TEXT"),
        ("pids_limit", "INTEGER"),
    ],
    "active_sessions": [
        ("step", "INTEGER NOT NULL DEFAULT 0"),
        ("hint_mask", "INTEGER NOT NULL DEFAULT 0"),  # bitmask of steps where a hint was used
    ],
}


@asynccontextmanager
async def conn():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


async def _migrate(db) -> bool:
    changed = False
    for table, cols in MIGRATIONS.items():
        cur = await db.execute(f"PRAGMA table_info({table})")
        have = {r["name"] for r in await cur.fetchall()}
        for name, ddl in cols:
            if name not in have:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                changed = True
    return changed


async def init_db() -> None:
    async with conn() as db:
        await db.executescript(SCHEMA)
        if await _migrate(db):
            # Schema changed: old sessions are incompatible with the new task format.
            # Their containers will be cleaned up as orphans on startup (reconcile).
            await db.execute("DELETE FROM active_sessions")
        for t in TASKS:
            await db.execute(
                """
                INSERT INTO tasks (slug, title, description, setup_script, check_script,
                                   reward_points, steps_json, category, difficulty,
                                   mem_limit, pids_limit)
                VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    description=excluded.description,
                    setup_script=excluded.setup_script,
                    reward_points=excluded.reward_points,
                    steps_json=excluded.steps_json,
                    category=excluded.category,
                    difficulty=excluded.difficulty,
                    mem_limit=excluded.mem_limit,
                    pids_limit=excluded.pids_limit
                """,
                (
                    t["slug"],
                    t["title"],
                    t["intro"],
                    t["setup_script"],
                    t["reward_points"],
                    json.dumps(t["steps"], ensure_ascii=False),
                    t.get("category", ""),
                    t.get("difficulty", "easy"),
                    t.get("mem_limit"),
                    t.get("pids_limit"),
                ),
            )
        await db.commit()


# ---------- users ----------

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


# ---------- tasks ----------

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


async def get_task(task_id: int):
    async with conn() as db:
        cur = await db.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
        return await cur.fetchone()


async def get_task_by_slug(slug: str) -> Optional[dict]:
    async with conn() as db:
        cur = await db.execute("SELECT * FROM tasks WHERE slug=?", (slug,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ---------- sessions ----------

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


# ---------- group sessions & participants ----------

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
