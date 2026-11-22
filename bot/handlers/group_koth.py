import asyncio
import html
import json
import logging
import secrets
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import db
import docker_manager as dm
from bot.formatting import format_user_mention, parse_meta
from bot.keyboards import (
    build_koth_lobby_kb,
    build_koth_phase1_kb,
    render_koth_lobby_text,
)
from bot.services.koth import (
    finish_koth_defenders_win,
    koth_phase1_timer,
    transition_koth_to_phase2,
)
from bot.services.sessions import cleanup_group_session
from bot.state import alloc_lock, group_locks
from config import KOTH_ATTACK_SECONDS, KOTH_DEFEND_SECONDS, MAX_CONTAINERS

log = logging.getLogger("bot")
router = Router()


@router.callback_query(F.data.startswith("koth_role:"))
async def on_koth_role(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer()
        return
    _, _, role = parts
    chat_id = call.message.chat.id
    tg_id = call.from_user.id

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "koth" or session["status"] != "lobby":
            await call.answer("Лобі битви вже закрите.", show_alert=True)
            return

        user = await db.upsert_user(tg_id, call.from_user.username)
        await db.add_group_participant(
            session["id"], user["id"], tg_id, call.from_user.username or "", role=role
        )
        participants = await db.get_group_participants(session["id"])
        role_label = "🛡 Захисники" if role == "defender" else "⚔️ Атакуючі"
        await call.answer(f"Твоя роль: {role_label}")
        try:
            await call.message.edit_text(
                render_koth_lobby_text(session, participants),
                reply_markup=build_koth_lobby_kb(session["id"]),
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("koth_cancel:"))
async def on_koth_cancel(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    chat_id = call.message.chat.id
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "koth" or session["status"] != "lobby":
            await call.answer("Лобі вже неактивне.")
            return
        await db.delete_group_session(chat_id)
        await call.answer("Битву скасовано.")
        try:
            await call.message.edit_text("❌ Лобі Attack-Defense скасовано.")
        except Exception:
            pass


@router.callback_query(F.data.startswith("koth_start:"))
async def on_koth_start(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    chat_id = call.message.chat.id

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "koth" or session["status"] != "lobby":
            await call.answer("Битва вже стартувала або лобі закрите.", show_alert=True)
            return

        participants = await db.get_group_participants(session["id"])
        if not participants:
            user = await db.upsert_user(call.from_user.id, call.from_user.username)
            await db.add_group_participant(
                session["id"], user["id"], call.from_user.id, call.from_user.username or "", role="defender"
            )
            participants = await db.get_group_participants(session["id"])

        async with alloc_lock:
            if await db.count_all_containers() >= MAX_CONTAINERS:
                await call.answer("🚧 Зараз усі пісочниці зайняті, спробуйте пізніше.", show_alert=True)
                return
            await db.update_group_session(chat_id, status="starting")

        await call.answer("Запускаємо битву King of the Hill! 🏰")
        try:
            await call.message.edit_text("⏳ Готуємо фортецю (піднімаємо контейнер та генеруємо динамічний прапор)…")
        except Exception:
            pass

        flag = f"CTF{{koth_{secrets.token_hex(6)}}}"
        trap_flag = f"CTF{{trap_{secrets.token_hex(4)}}}"

        try:
            container_id = await dm.create_sandbox(
                session["setup_script"], session["mem_limit"], session["pids_limit"]
            )
            # Write dynamic flag and decoy trap into the container
            init_flag_script = (
                f"mkdir -p /var/www/portal && "
                f"printf '%s\\n' '{flag}' > /var/www/flag.txt && "
                f"chown www-data:www-data /var/www/flag.txt && "
                f"chmod 0644 /var/www/flag.txt && "
                f"printf '%s\\n' '{trap_flag}' > /var/www/portal/flag_backup_decoy.txt && "
                f"chown www-data:www-data /var/www/portal/flag_backup_decoy.txt && "
                f"chmod 0644 /var/www/portal/flag_backup_decoy.txt"
            )
            await dm.run_check(container_id, init_flag_script)
        except Exception:
            log.exception("KOTH container creation failed")
            await db.delete_group_session(chat_id)
            try:
                await call.message.edit_text("❌ Не вдалося запустити контейнер для Attack-Defense.")
            except Exception:
                pass
            return

        now = time.time()
        phase1_end = now + KOTH_DEFEND_SECONDS
        meta = {
            "flag": flag,
            "trap_flag": trap_flag,
            "phase1_ends_at": phase1_end,
            "hint_mask": 0,
        }
        await db.update_group_session(
            chat_id,
            container_id=container_id,
            status="phase1_defend",
            cwd="/var/www/portal",
            expires_at=now + KOTH_DEFEND_SECONDS + KOTH_ATTACK_SECONDS + 60,
            meta_json=json.dumps(meta),
        )

        defenders = [p for p in participants if p["role"] == "defender"]
        def_mentions = ", ".join(format_user_mention(p["tg_id"], p["username"]) for p in defenders) or "Захисники"

        for d in defenders:
            try:
                await call.bot.send_message(
                    d["tg_id"],
                    f"🛡 <b>Ти Захисник у битві «{html.escape(session['title'])}»!</b>\n\n"
                    f"• Справжній прапор у <code>/var/www/flag.txt</code> (має залишатися читабельним для <code>www-data</code>!).\n"
                    f"• Приклад прапора-пастки (honeypot): <code>{trap_flag}</code> (будь-який прапор виду <code>CTF{{trap_...}}</code> зніме з атакуючих 60 сек при спробі здачі!).\n"
                    f"• Можеш вводити команди через <code>$ cmd</code> прямо тут у DM або в груповому чаті.\n"
                    f"• Коли завершиш налаштування захисту, натисни кнопку в групі або надішли /ready.",
                )
            except Exception:
                pass

        await call.message.edit_text(
            f"🛡 <b>Фаза 1: Захист ({KOTH_DEFEND_SECONDS // 60} хв)!</b>\n\n"
            f"Захисники ({def_mentions}) мають <b>root/sudo</b> доступ (<code>user=student</code>).\n"
            f"• Захистіть <code>/var/www/flag.txt</code> (закрийте доступ для <code>others</code>, але збережіть читання для <code>www-data</code> та роботу порталу на порту <code>8080</code>!).\n"
            f"• Усуньте вразливості в <code>/var/www/portal</code> та <code>/usr/local/bin/status_check</code>.\n"
            f"• Розкладіть фейкові прапори-пастки <code>CTF{{trap_...}}</code> (напр. <code>{trap_flag}</code>).\n\n"
            "💻 Вводьте команди через <code>$ команда</code> (у групі або в DM бота).\n"
            "Завершити фазу захисту достроково: /ready або кнопка нижче.",
            reply_markup=build_koth_phase1_kb(session["id"]),
        )

        asyncio.create_task(koth_phase1_timer(call.bot, chat_id, session["id"], KOTH_DEFEND_SECONDS))


@router.callback_query(F.data.startswith("koth_ready:"))
async def on_koth_ready_cb(call: CallbackQuery):
    if not call.message:
        await call.answer()
        return
    chat_id = call.message.chat.id
    session = await db.get_group_session(chat_id)
    if not session or session["mode"] != "koth" or session["status"] != "phase1_defend":
        await call.answer("Фаза 1 вже завершена.", show_alert=True)
        return

    participants = await db.get_group_participants(session["id"])
    defenders = [p["tg_id"] for p in participants if p["role"] == "defender"]
    if defenders and call.from_user.id not in defenders:
        await call.answer("Лише Захисники можуть завершити Фазу 1 достроково!", show_alert=True)
        return

    await call.answer("Переходимо до Фази 2 (Атака)! ⚔️")
    await transition_koth_to_phase2(call.bot, chat_id)


@router.message(Command("ready"))
async def cmd_ready(message: Message):
    if message.chat.type == "private":
        koth_session = await db.find_active_koth_defender_session(message.from_user.id)
        if not koth_session:
            await message.answer("Ти зараз не в активній Фазі 1 (Захист) режиму /koth.")
            return
        await message.answer("✅ Завершуємо Фазу 1 та переходимо до Фази 2 у груповому чаті!")
        await transition_koth_to_phase2(message.bot, koth_session["chat_id"])
        return

    chat_id = message.chat.id
    session = await db.get_group_session(chat_id)
    if not session or session["mode"] != "koth" or session["status"] != "phase1_defend":
        await message.answer("Команда /ready використовується Захисниками у Фазі 1 режиму /koth.")
        return

    participants = await db.get_group_participants(session["id"])
    defenders = [p["tg_id"] for p in participants if p["role"] == "defender"]
    if defenders and message.from_user.id not in defenders:
        await message.answer("🛡 Лише Захисники можуть достроково завершити Фазу 1!")
        return

    await transition_koth_to_phase2(message.bot, chat_id)


@router.message(Command("capture"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_capture(message: Message):
    chat_id = message.chat.id
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Використання: <code>/capture CTF{...}</code>")
        return

    submitted = parts[1].strip()
    tg_id = message.from_user.id

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "koth":
            await message.answer("Зараз немає активної битви /koth.")
            return
        if session["status"] != "active":
            await message.answer("⏳ Здавати прапор можна лише у Фазі 2 (Атака)!")
            return

        participants = await db.get_group_participants(session["id"])
        defenders = {p["tg_id"] for p in participants if p["role"] == "defender"}
        attackers = [p for p in participants if p["role"] == "attacker"]
        if attackers and tg_id in defenders:
            await message.answer("🛡 Захисники не можуть здавати прапор у Фазі 2!")
            return

        user = await db.upsert_user(tg_id, message.from_user.username)
        if tg_id not in defenders:
            await db.add_group_participant(
                session["id"], user["id"], tg_id, message.from_user.username or "", role="attacker"
            )
            participants = await db.get_group_participants(session["id"])
            attackers = [p for p in participants if p["role"] == "attacker"]

        meta = parse_meta(session)
        real_flag = meta.get("flag", "")
        trap_flag = meta.get("trap_flag", "")

        # Check for decoy flag (honeypot)
        if submitted == trap_flag or (submitted.startswith("CTF{trap_") and submitted.endswith("}")):
            new_expires = session["expires_at"] - 60
            await db.update_group_session(chat_id, expires_at=new_expires)
            rem = max(0, int(new_expires - time.time()))
            mins, secs = divmod(rem, 60)
            await message.answer(
                f"🪤 <b>Пастка! Атакуючі здали фейковий прапор захисників! -60 сек</b>\n"
                f"⏱ Залишилось часу на атаку: <b>{mins:02d}:{secs:02d}</b>"
            )
            if rem <= 0:
                # Trigger finish after exiting the current lock block
                asyncio.create_task(finish_koth_defenders_win(message.bot, chat_id))
            return

        if submitted != real_flag:
            await message.answer("❌ Невірний прапор! Шукайте далі.")
            return

        # Real flag found — Attackers win!
        points = session["reward_points"]
        winners = attackers if attackers else [p for p in participants if p["tg_id"] == tg_id]
        awarded_list = []
        for w in winners:
            pts = await db.award_points(w["user_id"], session["task_id"], points)
            name = format_user_mention(w["tg_id"], w["username"])
            awarded_list.append(f"{name} (+{pts})" if pts else f"{name} (вже зараховано)")

        await cleanup_group_session(chat_id, session)

        capturer = format_user_mention(tg_id, message.from_user.username)
        await message.answer(
            f"⚔️🏆 <b>Фортецю взято! Атакуючі перемогли у «{html.escape(session['title'])}»!</b>\n\n"
            f"🎯 Прапор захопив: <b>{capturer}</b>\n"
            f"🎁 Нагорода атакуючим: {', '.join(awarded_list)}"
        )
