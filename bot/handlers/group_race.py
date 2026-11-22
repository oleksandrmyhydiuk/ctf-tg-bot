import asyncio
import html
import json
import logging
import time

from aiogram import F, Router
from aiogram.types import CallbackQuery

import db
import docker_manager as dm
from bot.constants import DIFF_EMOJI, FOOTER, MAX_RACE_PARTICIPANTS
from bot.formatting import format_user_mention, load_steps, render_step
from bot.keyboards import build_race_lobby_kb, render_race_board, render_race_lobby_text
from bot.state import alloc_lock, group_locks
from config import GROUP_SESSION_TTL, MAX_CONTAINERS

log = logging.getLogger("bot")
router = Router()


@router.callback_query(F.data.startswith("race_join:"))
async def on_race_join(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    chat_id = call.message.chat.id
    tg_id = call.from_user.id

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "race" or session["status"] != "lobby":
            await call.answer("Лобі гонки вже закрите або не існує.", show_alert=True)
            return

        participants = await db.get_group_participants(session["id"])
        if any(p["tg_id"] == tg_id for p in participants):
            await call.answer("Ти вже в списку учасників гонки! 🏎")
            return

        if len(participants) >= MAX_RACE_PARTICIPANTS:
            await call.answer(f"Досягнуто ліміт учасників гонки ({MAX_RACE_PARTICIPANTS}).", show_alert=True)
            return

        # Check whether the user has started a DM conversation with the bot
        try:
            await call.bot.send_chat_action(tg_id, "typing")
        except Exception:
            await call.answer(
                "Спочатку відкрий бота в особистих повідомленнях (DM) і натисни /start!",
                show_alert=True,
            )
            return

        user = await db.upsert_user(tg_id, call.from_user.username)
        if await db.get_session(user["id"]):
            await call.answer(
                "У тебе вже є відкрита сесія в особистих повідомленнях! Заверши її через /stop.",
                show_alert=True,
            )
            return

        await db.add_group_participant(
            session["id"], user["id"], tg_id, call.from_user.username or "", role="player"
        )
        participants = await db.get_group_participants(session["id"])
        await call.answer("Тебе зареєстровано в гонці! 🏁")
        try:
            await call.message.edit_text(
                render_race_lobby_text(session, participants),
                reply_markup=build_race_lobby_kb(session["id"]),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("race_cancel:"))
async def on_race_cancel(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    chat_id = call.message.chat.id
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "race" or session["status"] != "lobby":
            await call.answer("Лобі вже неактивне.")
            return
        await db.delete_group_session(chat_id)
        await call.answer("Гонку скасовано.")
        try:
            await call.message.edit_text("❌ Лобі швидкісної гонки скасовано.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("race_start:"))
async def on_race_start(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    chat_id = call.message.chat.id

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "race" or session["status"] != "lobby":
            await call.answer("Гонка вже стартувала або лобі закрите.", show_alert=True)
            return

        participants = await db.get_group_participants(session["id"])
        if len(participants) < 1:
            await call.answer("Для старту потрібен хоча б 1 учасник! Натисніть «🏁 Беру участь».", show_alert=True)
            return

        # Ensure none of the participants already has an active DM session
        valid_participants = []
        for p in participants:
            if await db.get_session(p["user_id"]):
                await call.answer(
                    f"Учасник {format_user_mention(p['tg_id'], p['username'])} вже має відкриту сесію в DM!",
                    show_alert=True,
                )
                return
            valid_participants.append(p)

        async with alloc_lock:
            active_count = await db.count_all_containers()
            if active_count + len(valid_participants) > MAX_CONTAINERS:
                free = max(0, MAX_CONTAINERS - active_count)
                await call.answer(
                    f"🚧 Недостатньо вільних пісочниць (потрібно {len(valid_participants)}, вільно {free}).",
                    show_alert=True,
                )
                return
            await db.update_group_session(chat_id, status="starting")

        await call.answer("Запускаємо гонку! 🏎")
        try:
            await call.message.edit_text(
                f"⏳ <b>Старт гонки «{html.escape(session['title'])}»!</b>\n"
                f"Створюємо персональні контейнери для {len(valid_participants)} учасників…"
            )
        except Exception:
            pass

        results = await asyncio.gather(
            *(
                dm.create_sandbox(session["setup_script"], session["mem_limit"], session["pids_limit"])
                for _ in valid_participants
            ),
            return_exceptions=True,
        )
        created_cids = [r for r in results if isinstance(r, str)]
        if len(created_cids) != len(valid_participants):
            log.error("Race container creation failed: %r", results)
            await asyncio.gather(*(dm.destroy(cid) for cid in created_cids), return_exceptions=True)
            await db.delete_group_session(chat_id)
            try:
                await call.message.edit_text(
                    "❌ Не вдалося створити всі контейнери для гонки. Ресурси очищено, спробуйте ще раз."
                )
            except Exception:
                pass
            return

        try:
            for p, cid in zip(valid_participants, created_cids):
                await db.create_session(p["user_id"], session["task_id"], cid)
                await db.update_group_participant(
                    session["id"], p["tg_id"], container_id=cid, step=0, role="player"
                )
            meta = {
                "started_at": time.time(),
                "board_msg_id": call.message.message_id,
            }
            await db.update_group_session(
                chat_id,
                status="active",
                expires_at=time.time() + GROUP_SESSION_TTL,
                meta_json=json.dumps(meta),
            )
        except Exception:
            log.exception("Race DB initialization failed")
            for p in valid_participants:
                await db.delete_session(p["user_id"])
            await asyncio.gather(*(dm.destroy(cid) for cid in created_cids), return_exceptions=True)
            await db.delete_group_session(chat_id)
            try:
                await call.message.edit_text("❌ Помилка запуску гонки. Усі контейнери очищено.")
            except Exception:
                pass
            return

        steps = load_steps(session)
        emoji = DIFF_EMOJI.get(session["difficulty"], "⚪")
        bonus = int(session["reward_points"] * 1.5)
        dm_text = (
            f"🏎 <b>Швидкісна гонка стартувала!</b>\n"
            f"🧩 <b>{html.escape(session['title'])}</b> {emoji} (переможцю: <b>+{bonus} балів</b>)\n\n"
            f"{session['description']}\n\n"
            f"{render_step(steps, 0)}\n\n"
            f"⏳ Час гонки: {GROUP_SESSION_TTL // 60} хв.\n\n{FOOTER}"
        )
        for p in valid_participants:
            try:
                await call.bot.send_message(p["tg_id"], dm_text)
            except Exception:
                log.warning("Failed to send race start DM to %s", p["tg_id"])

        updated_session = await db.get_group_session(chat_id)
        updated_participants = await db.get_group_participants(session["id"])
        try:
            await call.message.edit_text(render_race_board(updated_session, updated_participants))
        except Exception:
            pass
