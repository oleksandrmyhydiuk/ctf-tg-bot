import asyncio
import html
import json
import logging
import sqlite3
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from docker.errors import NotFound

import db
import docker_manager as dm
from bot.constants import DIFF_EMOJI, FOOTER
from bot.formatting import (
    calc_reward,
    current_index,
    format_user_mention,
    load_steps,
    parse_meta,
    render_step,
)
from bot.keyboards import render_race_board
from bot.services.sessions import cleanup_group_session, drop_session, refresh_race_board
from bot.state import Sandbox, alloc_lock, group_locks, locks
from config import MAX_CONTAINERS, SESSION_TTL

log = logging.getLogger("bot")
router = Router()


async def _get_active(message: Message, state: FSMContext):
    """Returns (user, session) or (None, None) after replying to the user."""
    user = await db.get_user(message.from_user.id)
    session = await db.get_session(user["id"]) if user else None
    if not session:
        await state.clear()
        await message.answer("Активної сесії немає. Обери завдання: /tasks")
        return None, None
    return user, session


@router.message(Command("tasks"), F.chat.type == "private")
async def cmd_tasks(message: Message):
    user = await db.upsert_user(message.from_user.id, message.from_user.username)
    tasks = await db.list_tasks(user["id"])
    kb = InlineKeyboardBuilder()
    for t in tasks:
        mark = "✅ " if t["done"] else ""
        steps = len(json.loads(t["steps_json"]))
        emoji = DIFF_EMOJI.get(t["difficulty"], "⚪")
        kb.button(
            text=f"{mark}{emoji} {t['title']} · {steps} кр. · +{t['reward_points']}",
            callback_data=f"task:{t['id']}",
        )
    kb.adjust(1)
    await message.answer(
        "Оберіть завдання (🟢 легке · 🟡 середнє · 🔴 складне):", reply_markup=kb.as_markup()
    )


@router.callback_query(F.data.startswith("task:"))
async def on_task_selected(call: CallbackQuery, state: FSMContext):
    if call.message and call.message.chat.type != "private":
        await call.answer("Індивідуальні задачі запускаються в особистих повідомленнях з ботом!", show_alert=True)
        return

    await call.answer()
    tg_id = call.from_user.id

    async with locks[tg_id]:
        user = await db.upsert_user(tg_id, call.from_user.username)

        if await db.get_session(user["id"]):
            await call.message.answer(
                "У тебе вже є активна сесія. Заверши її: /check або /stop."
            )
            return

        task = await db.get_task(int(call.data.split(":", 1)[1]))
        if not task:
            await call.message.answer("Таке завдання не знайдено.")
            return

        async with alloc_lock:
            if await db.count_all_containers() >= MAX_CONTAINERS:
                await call.message.answer("🚧 Зараз усі пісочниці зайняті, спробуй за кілька хвилин.")
                return

        status = await call.message.answer("⏳ Готую середовище (сервіси можуть стартувати до кількох секунд)…")
        try:
            container_id = await dm.create_sandbox(
                task["setup_script"], task["mem_limit"], task["pids_limit"]
            )
        except Exception:
            log.exception("create_sandbox failed")
            await status.edit_text("❌ Не вдалося створити середовище. Спробуй пізніше.")
            return

        try:
            await db.create_session(user["id"], task["id"], container_id)
        except sqlite3.IntegrityError:
            await dm.destroy(container_id)
            await status.edit_text("У тебе вже є активна сесія: /stop")
            return

        await state.set_state(Sandbox.in_container)
        steps = json.loads(task["steps_json"])
        emoji = DIFF_EMOJI.get(task["difficulty"], "⚪")
        await status.edit_text(
            f"🧩 <b>{html.escape(task['title'])}</b> {emoji}\n\n"
            f"{task['description']}\n\n"
            f"{render_step(steps, 0)}\n\n"
            f"⏳ Час на задачу: {SESSION_TTL // 60} хв.\n\n{FOOTER}"
        )


@router.message(Command("task"), F.chat.type == "private")
async def cmd_task(message: Message, state: FSMContext):
    async with locks[message.from_user.id]:
        user, session = await _get_active(message, state)
        if not session:
            return
        steps = load_steps(session)
        await message.answer(
            f"🧩 <b>{html.escape(session['title'])}</b>\n\n"
            f"{render_step(steps, current_index(session, steps))}"
        )


@router.message(Command("hint"), F.chat.type == "private")
async def cmd_hint(message: Message, state: FSMContext):
    async with locks[message.from_user.id]:
        user, session = await _get_active(message, state)
        if not session:
            return
        steps = load_steps(session)
        idx = current_index(session, steps)
        hint = steps[idx].get("hint")
        if not hint:
            await message.answer("Для цього кроку підказки немає.")
            return
        bit = 1 << idx
        mask = session["hint_mask"]
        note = ""
        if not mask & bit:
            await db.set_hint_mask(user["id"], mask | bit)
            note = "\n\n<i>Нагорода за задачу трохи зменшена.</i>"
        await message.answer(f"💡 {hint}{note}")


@router.message(Command("stop"), F.chat.type == "private")
async def cmd_stop(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    race_info = await db.get_active_race_for_user(tg_id)

    if race_info:
        chat_id = race_info["chat_id"]
        async with locks[tg_id]:
            user = await db.get_user(tg_id)
            session = await db.get_session(user["id"]) if user else None
            await state.clear()
            if session:
                await drop_session(user["id"], session["container_id"])

        async with group_locks[chat_id]:
            await db.update_group_participant(
                race_info["session_id"], tg_id, role="forfeited", container_id=None
            )
            participants = await db.get_group_participants(race_info["session_id"])
            remaining = [p for p in participants if p.get("container_id") and p["role"] != "forfeited"]
            if not remaining:
                gs = await db.get_group_session(chat_id)
                await cleanup_group_session(chat_id, gs)
                try:
                    await message.bot.send_message(
                        chat_id, "🛑 Усі учасники зійшли з дистанції. Гонку завершено без переможця."
                    )
                except Exception:
                    pass
            else:
                await refresh_race_board(message.bot, chat_id)

        await message.answer("🏳️ Ти зійшов з дистанції в гонці. Твій контейнер зупинено. /tasks")
        return

    async with locks[tg_id]:
        user = await db.get_user(tg_id)
        session = await db.get_session(user["id"]) if user else None
        await state.clear()
        if not session:
            await message.answer("Активної сесії немає. /tasks")
            return
        await drop_session(user["id"], session["container_id"])
    await message.answer("🛑 Сесію завершено без нарахування балів. /tasks")


@router.message(Command("check"), F.chat.type == "private")
async def cmd_check(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    async with locks[tg_id]:
        user, session = await _get_active(message, state)
        if not session:
            return

        steps = load_steps(session)
        idx = current_index(session, steps)

        try:
            ok = await dm.run_check(session["container_id"], steps[idx]["check"])
        except NotFound:
            await db.delete_session(user["id"])
            await state.clear()
            await message.answer("Контейнер більше не існує, сесію завершено. /tasks")
            return
        except Exception:
            log.exception("check failed")
            await message.answer("⚠️ Помилка під час перевірки, спробуй ще раз.")
            return

        if not ok:
            await message.answer("Крок ще не виконано, спробуй ще. (/hint — підказка)")
            return

        race_info = await db.get_active_race_for_user(tg_id)

        if idx + 1 < len(steps):
            await db.advance_step(user["id"])
            if race_info:
                await db.update_group_participant(race_info["session_id"], tg_id, step=idx + 1)
                await refresh_race_board(message.bot, race_info["chat_id"])
            await message.answer(
                f"✅ Крок {idx + 1}/{len(steps)} виконано!\n\n{render_step(steps, idx + 1)}"
            )
            return

        # If the user is in an active Speed Race, handle race finish under group_locks[chat_id]
        if race_info:
            chat_id = race_info["chat_id"]
            async with group_locks[chat_id]:
                gs = await db.get_group_session(chat_id)
                if gs and gs["mode"] == "race" and gs["status"] == "active":
                    await db.update_group_session(chat_id, status="finished")
                    await db.update_group_participant(race_info["session_id"], tg_id, step=len(steps))

                    base_bonus = int(session["reward_points"] * 1.5)
                    points = calc_reward(base_bonus, session["hint_mask"])
                    try:
                        await dm.destroy(session["container_id"])
                    except Exception:
                        log.exception("destroy winner container failed")
                    awarded = await db.complete_task(user["id"], session["task_id"], points)
                    await state.clear()

                    participants = await db.get_group_participants(gs["id"])
                    other_cids = []
                    other_racers = []
                    for p in participants:
                        if p["tg_id"] != tg_id and p.get("container_id") and p["role"] != "forfeited":
                            other_cids.append(p["container_id"])
                            other_racers.append(p)
                            await db.delete_session(p["user_id"])

                    if other_cids:
                        await asyncio.gather(*(dm.destroy(cid) for cid in other_cids), return_exceptions=True)

                    winner_name = format_user_mention(tg_id, message.from_user.username)
                    meta = parse_meta(gs)
                    elapsed = int(time.time() - meta.get("started_at", gs["created_at"]))
                    mins, secs = divmod(max(1, elapsed), 60)

                    # Update the scoreboard in the group
                    board_msg_id = meta.get("board_msg_id")
                    if board_msg_id:
                        try:
                            await message.bot.edit_message_text(
                                text=render_race_board(gs, participants, winner_tg_id=tg_id),
                                chat_id=chat_id,
                                message_id=board_msg_id,
                            )
                        except Exception:
                            pass

                    await db.delete_group_session(chat_id)

                    # Notify other racers in DM
                    for p in other_racers:
                        try:
                            await message.bot.send_message(
                                p["tg_id"],
                                f"🏁 Гонку <b>«{html.escape(gs['title'])}»</b> завершено! "
                                f"Переміг {winner_name}. Твій контейнер зупинено.",
                            )
                        except Exception:
                            pass

                    # Celebratory announcement in the group
                    pts_note = f"+{awarded} балів (1.5x бонус гонки!)" if awarded else f"(вже розв'язано раніше, рекорд: {mins} хв {secs} с)"
                    try:
                        await message.bot.send_message(
                            chat_id,
                            f"🏆 <b>Перемога в Швидкісній гонці!</b>\n\n"
                            f"🥇 Переможець: <b>{winner_name}</b>\n"
                            f"🧩 Задача: <b>{html.escape(gs['title'])}</b>\n"
                            f"⏱ Час проходження: <b>{mins} хв {secs} с</b>\n"
                            f"🎁 Нагорода: <b>{pts_note}</b>",
                        )
                    except Exception:
                        pass

                    await message.answer(
                        f"🏆 <b>Ти переміг у гонці «{html.escape(gs['title'])}»!</b> "
                        f"{f'+{awarded} балів!' if awarded else 'Задача зарахована!'}"
                    )
                    return

        # Standard solo task completion
        points = calc_reward(session["reward_points"], session["hint_mask"])
        try:
            await dm.destroy(session["container_id"])
        except Exception:
            log.exception("destroy after solve failed")
        awarded = await db.complete_task(user["id"], session["task_id"], points)
        await state.clear()

    if awarded:
        extra = ""
        if awarded < session["reward_points"]:
            extra = f" (з урахуванням підказок, максимум {session['reward_points']})"
        await message.answer(f"🎉 Задачу розв'язано! +{awarded} балів{extra}. /tasks — наступна.")
    else:
        await message.answer("✅ Задачу розв'язано! Бали за неї вже були нараховані раніше. /tasks")
