import json
from contextlib import asynccontextmanager

import aiosqlite

from config import DB_PATH
from tasks import TASKS

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
