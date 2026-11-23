"""Embedded aiohttp HTTP API and static file server for the Telegram Mini App."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

from aiohttp import web
from docker.errors import NotFound

import config
import db
from api.auth import AuthError, TelegramUser, authenticate_init_data
from bot.formatting import calc_reward, current_index, load_steps
from bot.state import alloc_lock, last_cmd_at, locks

log = logging.getLogger("webapp.api")

# Optional override for tests; imported lazily so `api.server` can be imported without Docker running.
dm: Any = None


def _get_dm():
    if dm is not None:
        return dm
    import docker_manager

    return docker_manager

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "webapp" / "dist"


def _json_error(message: str, status: int) -> web.Response:
    return web.json_response({"error": message}, status=status)


def _authenticate(request: web.Request) -> TelegramUser:
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return authenticate_init_data(init_data)


async def _get_user_rank(user) -> int | None:
    if not user or int(user["score"]) <= 0:
        return None
    async with db.conn() as conn:
        cur = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE score > ? OR (score = ? AND id < ?)",
            (user["score"], user["score"], user["id"]),
        )
        ahead = (await cur.fetchone())[0]
    return int(ahead) + 1


def _serialize_session(session, slug: str) -> dict[str, Any]:
    steps = load_steps(session)
    idx = current_index(session, steps)
    step_obj = steps[idx]
    hint_raw = step_obj.get("hint") or ""
    has_hint = bool(hint_raw)
    hint_mask = int(session["hint_mask"] or 0)
    hint_used = bool(hint_mask & (1 << idx))
    hint_text = hint_raw if (has_hint and hint_used) else None
    expires_in = max(0, int(config.SESSION_TTL - (time.time() - session["created_at"])))
    reward_points = int(session["reward_points"])
    current_reward = calc_reward(reward_points, hint_mask)
    return {
        "task_id": session["task_id"],
        "slug": slug,
        "title": session["title"],
        "step": idx,
        "total_steps": len(steps),
        "step_text": step_obj["text"],
        "has_hint": has_hint,
        "hint_used": hint_used,
        "hint_text": hint_text,
        "hint_mask": hint_mask,
        "cwd": session["cwd"],
        "expires_in": expires_in,
        "reward_points": reward_points,
        "current_reward": current_reward,
    }


@web.middleware
async def cors_middleware(request: web.Request, handler):
    origin = request.headers.get("Origin", "*")
    cors_headers = {
        "Access-Control-Allow-Origin": origin or "*",
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Init-Data",
    }
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_headers)

    try:
        response = await handler(request)
    except web.HTTPException as exc:
        exc.headers.update(cors_headers)
        raise

    response.headers.update(cors_headers)
    return response


async def handle_bootstrap(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    user = await db.upsert_user(tg_user.id, tg_user.username)
    task_rows = await db.list_tasks(user["id"])

    tasks_payload: list[dict[str, Any]] = []
    slug_by_id: dict[int, str] = {}
    solved_count = 0
    max_score = 0

    for t in task_rows:
        raw_steps = json.loads(t["steps_json"])
        done = bool(t["done"])
        if done:
            solved_count += 1
        max_score += int(t["reward_points"])
        slug_by_id[t["id"]] = t["slug"]
        tasks_payload.append(
            {
                "id": t["id"],
                "slug": t["slug"],
                "title": t["title"],
                "category": t["category"],
                "difficulty": t["difficulty"],
                "reward_points": t["reward_points"],
                "description": t["description"],
                "mem_limit": t["mem_limit"] or config.MEM_LIMIT,
                "pids_limit": t["pids_limit"] or config.PIDS_LIMIT,
                "steps_count": len(raw_steps),
                "steps": [{"text": s["text"]} for s in raw_steps],
                "done": done,
            }
        )

    session = await db.get_session(user["id"])
    active_session = None
    if session:
        slug = slug_by_id.get(session["task_id"], "")
        active_session = _serialize_session(session, slug)

    used_slots = await db.count_all_containers()
    rank = await _get_user_rank(user)
    display_name = user["username"] or tg_user.display_username or f"id{str(user['tg_id'])[-4:]}"

    return web.json_response(
        {
            "user": {
                "id": user["id"],
                "tg_id": user["tg_id"],
                "username": display_name,
                "score": user["score"],
                "rank": rank,
                "solved_count": solved_count,
                "total_tasks": len(tasks_payload),
                "max_score": max_score,
            },
            "tasks": tasks_payload,
            "active_session": active_session,
            "slots": {"used": used_slots, "max": config.MAX_CONTAINERS},
            "session_ttl": config.SESSION_TTL,
        }
    )


async def handle_leaderboard(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    user = await db.upsert_user(tg_user.id, tg_user.username)
    rows = await db.leaderboard(50)
    entries = [
        {
            "rank": idx,
            "username": r["username"] or f"id{str(r['tg_id'])[-4:]}",
            "tg_id": r["tg_id"],
            "score": r["score"],
            "is_me": r["tg_id"] == tg_user.id,
        }
        for idx, r in enumerate(rows, start=1)
    ]
    my_rank = await _get_user_rank(user)
    return web.json_response(
        {
            "entries": entries,
            "my_rank": my_rank,
            "my_score": user["score"],
        }
    )


async def handle_create_session(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    try:
        body = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", status=400)

    if not isinstance(body, dict):
        return _json_error("JSON object expected", status=400)

    task_id = body.get("task_id")
    slug = body.get("slug")
    if task_id is None and not slug:
        return _json_error("task_id or slug is required", status=400)

    async with locks[tg_user.id]:
        user = await db.upsert_user(tg_user.id, tg_user.username)
        if await db.get_session(user["id"]):
            return _json_error(
                "У тебе вже є активна сесія. Заверши її перед запуском нової.",
                status=409,
            )

        task = None
        if task_id is not None:
            try:
                task = await db.get_task(int(task_id))
            except (TypeError, ValueError):
                return _json_error("Invalid task_id", status=400)
        elif isinstance(slug, str):
            task = await db.get_task_by_slug(slug.strip())

        if not task:
            return _json_error("Таке завдання не знайдено.", status=404)

        async with alloc_lock:
            if await db.count_all_containers() >= config.MAX_CONTAINERS:
                return _json_error(
                    "Зараз усі пісочниці зайняті, спробуй за кілька хвилин.",
                    status=503,
                )

        try:
            container_id = await _get_dm().create_sandbox(
                task["setup_script"], task["mem_limit"], task["pids_limit"]
            )
        except Exception:
            log.exception("create_sandbox failed in webapp API")
            return _json_error("Не вдалося створити середовище. Спробуй пізніше.", status=500)

        try:
            await db.create_session(user["id"], task["id"], container_id)
        except sqlite3.IntegrityError:
            await _get_dm().destroy(container_id)
            return _json_error("У тебе вже є активна сесія.", status=409)

        session = await db.get_session(user["id"])
        return web.json_response({"session": _serialize_session(session, task["slug"])}, status=201)


async def handle_exec(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    try:
        body = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", status=400)

    cmd = body.get("cmd") if isinstance(body, dict) else None
    if not isinstance(cmd, str) or not cmd.strip():
        return _json_error("Команда не може бути порожньою.", status=400)

    if len(cmd) > config.MAX_CMD_LEN:
        return _json_error(
            f"Команда задовга (максимум {config.MAX_CMD_LEN} символів).",
            status=400,
        )

    now = time.monotonic()
    if now - last_cmd_at.get(tg_user.id, 0) < config.MIN_CMD_INTERVAL:
        return _json_error("Не так швидко 🙂", status=429)
    last_cmd_at[tg_user.id] = now

    async with locks[tg_user.id]:
        user = await db.get_user(tg_user.id)
        session = await db.get_session(user["id"]) if user else None
        if not session:
            return _json_error("Активної сесії немає.", status=404)

        log.info("WEBAPP CMD tg=%s task=%s: %r", tg_user.id, session["task_id"], cmd)
        try:
            output, timed_out, new_cwd = await _get_dm().run_command(
                session["container_id"], cmd, session["cwd"]
            )
        except NotFound:
            await db.delete_session(user["id"])
            return _json_error("Контейнер більше не існує, сесію завершено.", status=410)
        except Exception:
            log.exception("webapp run_command failed")
            return _json_error("Не вдалося виконати команду.", status=500)

        if new_cwd != session["cwd"]:
            await db.set_cwd(user["id"], new_cwd)

    return web.json_response(
        {
            "output": output,
            "timed_out": timed_out,
            "cwd": new_cwd,
        }
    )


async def handle_hint(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    async with locks[tg_user.id]:
        user = await db.get_user(tg_user.id)
        session = await db.get_session(user["id"]) if user else None
        if not session:
            return _json_error("Активної сесії немає.", status=404)

        steps = load_steps(session)
        idx = current_index(session, steps)
        hint = steps[idx].get("hint") or ""
        if not hint:
            return _json_error("Для цього кроку підказки немає.", status=404)

        bit = 1 << idx
        mask = int(session["hint_mask"] or 0)
        already_used = bool(mask & bit)
        new_mask = mask | bit
        if not already_used:
            await db.set_hint_mask(user["id"], new_mask)

        current_reward = calc_reward(int(session["reward_points"]), new_mask)

    return web.json_response(
        {
            "hint": hint,
            "hint_mask": new_mask,
            "current_reward": current_reward,
            "already_used": already_used,
        }
    )


async def handle_check(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    async with locks[tg_user.id]:
        user = await db.get_user(tg_user.id)
        session = await db.get_session(user["id"]) if user else None
        if not session:
            return _json_error("Активної сесії немає.", status=404)

        steps = load_steps(session)
        idx = current_index(session, steps)

        try:
            ok = await _get_dm().run_check(session["container_id"], steps[idx]["check"])
        except NotFound:
            await db.delete_session(user["id"])
            return _json_error("Контейнер більше не існує, сесію завершено.", status=410)
        except Exception:
            log.exception("webapp run_check failed")
            return _json_error("Помилка під час перевірки, спробуй ще раз.", status=500)

        if not ok:
            return web.json_response(
                {
                    "passed": False,
                    "message": "Крок ще не виконано, спробуй ще.",
                }
            )

        if idx + 1 < len(steps):
            await db.advance_step(user["id"])
            updated = await db.get_session(user["id"])
            task = await db.get_task(updated["task_id"])
            slug = task["slug"] if task else ""
            return web.json_response(
                {
                    "passed": True,
                    "completed": False,
                    "session": _serialize_session(updated, slug),
                }
            )

        max_points = int(session["reward_points"])
        points = calc_reward(max_points, int(session["hint_mask"] or 0))
        try:
            await _get_dm().destroy(session["container_id"])
        except Exception:
            log.exception("destroy after webapp solve failed")

        awarded = await db.complete_task(user["id"], session["task_id"], points)
        updated_user = await db.get_user(tg_user.id)
        time_spent = max(1, int(time.time() - session["created_at"]))

    return web.json_response(
        {
            "passed": True,
            "completed": True,
            "awarded_points": awarded,
            "max_points": max_points,
            "already_solved": awarded == 0,
            "total_score": updated_user["score"] if updated_user else user["score"],
            "time_spent": time_spent,
        }
    )


async def handle_delete_session(request: web.Request) -> web.Response:
    try:
        tg_user = _authenticate(request)
    except AuthError as exc:
        return _json_error(str(exc), status=401)

    async with locks[tg_user.id]:
        user = await db.get_user(tg_user.id)
        session = await db.get_session(user["id"]) if user else None
        if session:
            if dm is not None:
                try:
                    await dm.destroy(session["container_id"])
                except Exception:
                    log.exception("Failed to destroy container %s", session["container_id"])
                await db.delete_session(user["id"])
            else:
                from bot.services.sessions import drop_session

                await drop_session(user["id"], session["container_id"])

    return web.json_response({"stopped": True})


async def handle_static(request: web.Request) -> web.StreamResponse:
    index_file = DIST_DIR / "index.html"
    if not index_file.is_file():
        return _json_error("Mini App frontend is not built (webapp/dist/index.html missing)", status=404)

    rel_path = request.match_info.get("tail", "").lstrip("/")
    if rel_path:
        try:
            dist_root = DIST_DIR.resolve()
            candidate = (dist_root / rel_path).resolve()
            if candidate.is_relative_to(dist_root) and candidate.is_file():
                return web.FileResponse(candidate)
        except Exception:
            pass

    return web.FileResponse(index_file)


def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/api/bootstrap", handle_bootstrap)
    app.router.add_get("/api/leaderboard", handle_leaderboard)
    app.router.add_post("/api/sessions", handle_create_session)
    app.router.add_post("/api/sessions/exec", handle_exec)
    app.router.add_post("/api/sessions/hint", handle_hint)
    app.router.add_post("/api/sessions/check", handle_check)
    app.router.add_delete("/api/sessions", handle_delete_session)
    app.router.add_get("/{tail:.*}", handle_static)
    return app


async def start_webapp_server(
    host: str | None = None,
    port: int | None = None,
) -> web.AppRunner:
    bind_host = host or config.WEBAPP_HOST
    bind_port = port if port is not None else config.WEBAPP_PORT
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, bind_host, bind_port)
    await site.start()
    log.info("Mini App API server listening on http://%s:%s", bind_host, bind_port)
    return runner
