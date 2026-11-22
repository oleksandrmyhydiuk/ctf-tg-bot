import asyncio
import logging

from aiogram import Bot

import db
import docker_manager as dm
from bot.constants import DEFAULT_GROUP_SLUGS
from bot.formatting import parse_meta
from bot.keyboards import render_race_board

log = logging.getLogger("bot")


async def drop_session(user_id: int, container_id: str) -> None:
    try:
        await dm.destroy(container_id)
    except Exception:
        log.exception("Failed to destroy container %s", container_id)
    await db.delete_session(user_id)


async def cleanup_group_session(chat_id: int, session: dict | None = None) -> None:
    """Completely cleans up a group session, its containers, and personal race containers."""
    if not session:
        session = await db.get_group_session(chat_id)
    if not session:
        return

    cids: set[str] = set()
    if session.get("container_id"):
        cids.add(session["container_id"])

    participants = await db.get_group_participants(session["id"])
    for p in participants:
        if p.get("container_id"):
            cids.add(p["container_id"])
        if session["mode"] == "race":
            await db.delete_session(p["user_id"])

    if cids:
        await asyncio.gather(*(dm.destroy(cid) for cid in cids), return_exceptions=True)

    await db.delete_group_session(chat_id)


async def resolve_group_task(mode: str, arg: str | None) -> dict | None:
    slug = (arg or "").strip() or DEFAULT_GROUP_SLUGS[mode]
    task = await db.get_task_by_slug(slug)
    if task:
        return task
    # If a numeric task ID was passed
    if slug.isdigit():
        row = await db.get_task(int(slug))
        return dict(row) if row else None
    return None


async def refresh_race_board(bot: Bot, chat_id: int) -> None:
    session = await db.get_group_session(chat_id)
    if not session or session["mode"] != "race":
        return
    meta = parse_meta(session)
    msg_id = meta.get("board_msg_id")
    if not msg_id:
        return
    participants = await db.get_group_participants(session["id"])
    text = render_race_board(session, participants)
    try:
        await bot.edit_message_text(text=text, chat_id=chat_id, message_id=msg_id)
    except Exception:
        pass
