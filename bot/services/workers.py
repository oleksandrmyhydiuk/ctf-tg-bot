import asyncio
import logging
import time

from aiogram import Bot
from docker.errors import NotFound

import db
import docker_manager as dm
from bot.services.koth import finish_koth_defenders_win
from bot.services.sessions import cleanup_group_session, drop_session, refresh_race_board
from bot.state import group_locks, locks
from config import MAX_DISK_BYTES, SESSION_TTL, TTL_CHECK_INTERVAL, WATCHDOG_INTERVAL

log = logging.getLogger("bot")


async def ttl_worker(bot: Bot) -> None:
    while True:
        try:
            now = time.time()
            cutoff = now - SESSION_TTL
            for s in await db.expired_sessions(cutoff):
                # If the session belongs to a participant in an active race, its lifecycle is managed by the group session.
                if await db.get_active_race_for_user(s["tg_id"]):
                    continue
                async with locks[s["tg_id"]]:
                    current = await db.get_session(s["user_id"])
                    if not current or current["container_id"] != s["container_id"]:
                        continue
                    await drop_session(s["user_id"], s["container_id"])
                try:
                    await bot.send_message(
                        s["tg_id"], "⌛ Час виконання вийшов. Сесію завершено. /tasks"
                    )
                except Exception:
                    log.warning("Cannot notify user %s", s["tg_id"])

            # Check expired group sessions
            for gs in await db.expired_group_sessions(now):
                chat_id = gs["chat_id"]
                if gs["mode"] == "koth" and gs["status"] == "active":
                    await finish_koth_defenders_win(bot, chat_id)
                    continue

                async with group_locks[chat_id]:
                    current_gs = await db.get_group_session(chat_id)
                    if not current_gs or current_gs["id"] != gs["id"]:
                        continue
                    participants = await db.get_group_participants(gs["id"])
                    await cleanup_group_session(chat_id, current_gs)

                if gs["mode"] == "race" and gs["status"] == "active":
                    for p in participants:
                        if p.get("container_id") and p["role"] != "forfeited":
                            try:
                                await bot.send_message(
                                    p["tg_id"], "⌛ Час гонки вийшов. Сесію завершено. /tasks"
                                )
                            except Exception:
                                pass

                try:
                    await bot.send_message(
                        chat_id, "⌛ Час групової сесії вийшов. Сесію завершено."
                    )
                except Exception:
                    log.warning("Cannot notify group %s", chat_id)
        except Exception:
            log.exception("ttl_worker iteration failed")
        await asyncio.sleep(TTL_CHECK_INTERVAL)


async def disk_watchdog(bot: Bot) -> None:
    """Kills sessions (solo and group) whose container writable layer exceeds the disk limit."""
    while True:
        try:
            for item in await db.all_tracked_containers():
                cid = item["container_id"]
                try:
                    used = await dm.disk_usage(cid)
                except NotFound:
                    continue
                if used <= MAX_DISK_BYTES:
                    continue

                if item["source"] == "solo":
                    tg_id = item["tg_id"]
                    race_info = await db.get_active_race_for_user(tg_id)
                    if race_info:
                        chat_id = race_info["chat_id"]
                        async with locks[tg_id]:
                            await drop_session(item["user_id"], cid)
                        async with group_locks[chat_id]:
                            await db.update_group_participant(
                                race_info["session_id"], tg_id, role="forfeited", container_id=None
                            )
                            await refresh_race_board(bot, chat_id)
                    else:
                        async with locks[tg_id]:
                            current = await db.get_session(item["user_id"])
                            if not current or current["container_id"] != cid:
                                continue
                            log.warning("Disk limit exceeded: tg=%s used=%s", tg_id, used)
                            await drop_session(item["user_id"], cid)
                    try:
                        await bot.send_message(
                            tg_id, "💾 Перевищено ліміт диска. Сесію завершено. /tasks"
                        )
                    except Exception:
                        log.warning("Cannot notify user %s", tg_id)

                elif item["source"] == "group":
                    chat_id = item["chat_id"]
                    async with group_locks[chat_id]:
                        current_gs = await db.get_group_session(chat_id)
                        if not current_gs or current_gs.get("container_id") != cid:
                            continue
                        log.warning("Group disk limit exceeded: chat=%s used=%s", chat_id, used)
                        await cleanup_group_session(chat_id, current_gs)
                    try:
                        await bot.send_message(
                            chat_id, "💾 Перевищено ліміт диска в груповому контейнері. Сесію завершено."
                        )
                    except Exception:
                        log.warning("Cannot notify group %s", chat_id)

                elif item["source"] == "participant":
                    chat_id = item["chat_id"]
                    tg_id = item["tg_id"]
                    async with group_locks[chat_id]:
                        await dm.destroy(cid)
                        if item.get("user_id"):
                            await db.delete_session(item["user_id"])
                        await db.update_group_participant(
                            item["session_id"], tg_id, role="forfeited", container_id=None
                        )
                        await refresh_race_board(bot, chat_id)
        except Exception:
            log.exception("disk_watchdog iteration failed")
        await asyncio.sleep(WATCHDOG_INTERVAL)


async def reconcile() -> None:
    """On startup: remove containers without a DB record and DB records without a container."""
    tracked = await db.all_tracked_containers()
    known = {t["container_id"] for t in tracked if t.get("container_id")}
    live = set(await dm.list_sandbox_ids())

    for cid in live - known:
        log.info("Removing orphan container %s", cid[:12])
        await dm.destroy(cid)

    for t in tracked:
        cid = t["container_id"]
        if cid not in live:
            if t["source"] == "solo":
                log.info("Removing stale solo session for user_id=%s", t["user_id"])
                await db.delete_session(t["user_id"])
            elif t["source"] == "group":
                log.info("Removing stale group session for chat_id=%s", t["chat_id"])
                await db.delete_group_session(t["chat_id"])
            elif t["source"] == "participant":
                log.info("Removing stale race participant container for tg_id=%s", t["tg_id"])
                await db.update_group_participant(
                    t["session_id"], t["tg_id"], container_id=None, role="forfeited"
                )
