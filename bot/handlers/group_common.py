import html
import json
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from docker.errors import NotFound

import db
import docker_manager as dm
from bot.constants import DIFF_EMOJI, GROUP_FOOTER, MODE_TITLES
from bot.formatting import (
    calc_reward,
    current_index,
    format_user_mention,
    load_steps,
    parse_meta,
    render_step,
)
from bot.keyboards import (
    build_koth_lobby_kb,
    build_race_lobby_kb,
    build_task_picker_kb,
    render_koth_lobby_text,
    render_race_board,
    render_race_lobby_text,
)
from bot.services.sessions import cleanup_group_session, resolve_group_task
from bot.state import alloc_lock, group_locks
from config import GROUP_SESSION_TTL, MAX_CONTAINERS

log = logging.getLogger("bot")
router = Router()


async def _ensure_no_active_group_session(message: Message) -> bool:
    existing = await db.get_group_session(message.chat.id)
    if existing:
        if existing["status"] == "finished":
            await cleanup_group_session(message.chat.id, existing)
            return True
        mode_name = MODE_TITLES.get(existing["mode"], existing["mode"])
        await message.answer(
            f"⚠️ У цій групі вже триває сесія: <b>{mode_name} — «{html.escape(existing['title'])}»</b>.\n"
            "Використайте /gtask для перегляду або /gstop для завершення."
        )
        return False
    return True


async def _start_group_mode(
    message: Message,
    starter_tg_id: int,
    starter_username: str | None,
    mode: str,
    arg: str | None,
    edit_msg: bool = False,
):
    chat_id = message.chat.id
    if arg and arg.strip().lower() in {"list", "tasks", "pick"}:
        kb = await build_task_picker_kb(mode)
        text = f"📋 Оберіть задачу для режиму <b>{MODE_TITLES[mode]}</b>:"
        if edit_msg:
            await message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
        return

    task = await resolve_group_task(mode, arg)
    if not task:
        kb = await build_task_picker_kb(mode)
        await message.answer(
            f"❓ Задачу <code>{html.escape(arg or '')}</code> не знайдено. Оберіть зі списку:",
            reply_markup=kb,
        )
        return

    async with group_locks[chat_id]:
        if not await _ensure_no_active_group_session(message):
            return

        user = await db.upsert_user(starter_tg_id, starter_username)

        # Mode 1: Speed Race (opens lobby)
        if mode == "race":
            session_id = await db.create_group_session(
                chat_id=chat_id,
                mode="race",
                task_id=task["id"],
                status="lobby",
                expires_at=time.time() + GROUP_SESSION_TTL,
            )
            session = await db.get_group_session(chat_id)
            participants = await db.get_group_participants(session_id)
            text = render_race_lobby_text(session, participants)
            kb = build_race_lobby_kb(session_id)
            if edit_msg:
                await message.edit_text(text, reply_markup=kb)
            else:
                await message.answer(text, reply_markup=kb)
            return

        # Mode 3: King of the Hill (opens Defender / Attacker role-selection lobby)
        if mode == "koth":
            session_id = await db.create_group_session(
                chat_id=chat_id,
                mode="koth",
                task_id=task["id"],
                status="lobby",
                expires_at=time.time() + GROUP_SESSION_TTL,
            )
            await db.add_group_participant(
                session_id, user["id"], starter_tg_id, starter_username or "", role="defender"
            )
            session = await db.get_group_session(chat_id)
            participants = await db.get_group_participants(session_id)
            text = render_koth_lobby_text(session, participants)
            kb = build_koth_lobby_kb(session_id)
            if edit_msg:
                await message.edit_text(text, reply_markup=kb)
            else:
                await message.answer(text, reply_markup=kb)
            return

        # Modes 2 & 4: Co-op and Relay (immediately create a shared container)
        async with alloc_lock:
            if await db.count_all_containers() >= MAX_CONTAINERS:
                await message.answer("🚧 Зараз усі пісочниці зайняті, спробуйте за кілька хвилин.")
                return

        status_msg = (
            await message.edit_text("⏳ Готую спільний контейнер для групи…")
            if edit_msg
            else await message.answer("⏳ Готую спільний контейнер для групи…")
        )
        try:
            container_id = await dm.create_sandbox(
                task["setup_script"], task["mem_limit"], task["pids_limit"]
            )
        except Exception:
            log.exception("create_sandbox for group %s failed", mode)
            await status_msg.edit_text("❌ Не вдалося створити груповий контейнер. Спробуйте пізніше.")
            return

        try:
            session_id = await db.create_group_session(
                chat_id=chat_id,
                mode=mode,
                task_id=task["id"],
                status="active",
                expires_at=time.time() + GROUP_SESSION_TTL,
                container_id=container_id,
                meta_json=json.dumps({"hint_mask": 0, "force_turn": False}),
            )
            await db.add_group_participant(
                session_id, user["id"], starter_tg_id, starter_username or "", role="player"
            )
        except Exception:
            log.exception("Failed to create group session in DB")
            await dm.destroy(container_id)
            await status_msg.edit_text("❌ Помилка збереження групової сесії.")
            return

        steps = json.loads(task["steps_json"])
        emoji = DIFF_EMOJI.get(task["difficulty"], "⚪")
        extra_rule = ""
        if mode == "relay":
            extra_rule = (
                "\n🏃‍♂️ <b>Правило Естафети:</b> один і той самий гравець НЕ може виконати два етапи поспіль! "
                "Після кожного успішного /gcheck паличка переходить іншому учаснику групи (для соло-тесту: /force_turn).\n"
            )

        await status_msg.edit_text(
            f"{MODE_TITLES[mode]}\n"
            f"🧩 <b>{html.escape(task['title'])}</b> {emoji} (+{task['reward_points']} балів)\n\n"
            f"{task['description']}\n"
            f"{extra_rule}\n"
            f"{render_step(steps, 0)}\n\n"
            f"⏳ Час на сесію: {GROUP_SESSION_TTL // 60} хв.\n\n"
            f"{GROUP_FOOTER}"
        )


@router.callback_query(F.data.startswith("gpick:"))
async def on_group_task_picked(call: CallbackQuery):
    if not call.message or call.message.chat.type not in {"group", "supergroup"}:
        await call.answer()
        return
    parts = call.data.split(":", 2)
    if len(parts) != 3:
        await call.answer()
        return
    _, mode, slug = parts
    await call.answer()
    await _start_group_mode(call.message, call.from_user.id, call.from_user.username, mode, slug, edit_msg=True)


@router.message(Command("race"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_race(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1] if len(parts) > 1 else None
    await _start_group_mode(message, message.from_user.id, message.from_user.username, "race", arg)


@router.message(Command("coop"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_coop(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1] if len(parts) > 1 else None
    await _start_group_mode(message, message.from_user.id, message.from_user.username, "coop", arg)


@router.message(Command("koth"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_koth(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1] if len(parts) > 1 else None
    await _start_group_mode(message, message.from_user.id, message.from_user.username, "koth", arg)


@router.message(Command("relay"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_relay(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1] if len(parts) > 1 else None
    await _start_group_mode(message, message.from_user.id, message.from_user.username, "relay", arg)


@router.message(Command("force_turn"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_force_turn(message: Message):
    chat_id = message.chat.id
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "relay" or session["status"] != "active":
            await message.answer("Команда /force_turn доступна лише в активному режимі Естафети (/relay).")
            return
        meta = parse_meta(session)
        meta["force_turn"] = True
        await db.update_group_session(chat_id, last_actor_tg_id=None, meta_json=json.dumps(meta))
        await message.answer(
            "🔓 <b>Обмеження ходу Естафети знято на поточний етап</b> (режим соло-тестування). "
            "Будь-який учасник може виконувати команди та /gcheck."
        )


@router.message(Command("gtask"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_gtask(message: Message):
    chat_id = message.chat.id
    session = await db.get_group_session(chat_id)
    if not session:
        await message.answer("Активної групової сесії немає. Запустіть: /race, /coop, /koth або /relay")
        return

    mode_title = MODE_TITLES.get(session["mode"], session["mode"])
    participants = await db.get_group_participants(session["id"])

    if session["mode"] == "race":
        if session["status"] == "lobby":
            await message.answer(
                render_race_lobby_text(session, participants),
                reply_markup=build_race_lobby_kb(session["id"]),
            )
        else:
            await message.answer(render_race_board(session, participants))
        return

    if session["mode"] == "koth":
        if session["status"] == "lobby":
            await message.answer(
                render_koth_lobby_text(session, participants),
                reply_markup=build_koth_lobby_kb(session["id"]),
            )
            return
        rem = max(0, int(session["expires_at"] - time.time()))
        mins, secs = divmod(rem, 60)
        phase_str = "🛡 Фаза 1: Захист" if session["status"] == "phase1_defend" else "⚔️ Фаза 2: Атака"
        await message.answer(
            f"{mode_title}\n"
            f"🧩 <b>{html.escape(session['title'])}</b>\n"
            f"Статус: <b>{phase_str}</b> (⏱ залишилось ~{mins:02d}:{secs:02d})\n\n"
            f"{session['description']}"
        )
        return

    steps = load_steps(session)
    idx = current_index(session, steps)
    extra = ""
    if session["mode"] == "relay" and session.get("last_actor_tg_id"):
        last_p = next((p for p in participants if p["tg_id"] == session["last_actor_tg_id"]), None)
        last_name = format_user_mention(
            session["last_actor_tg_id"], last_p["username"] if last_p else None
        )
        extra = f"\n🏃‍♂️ <i>Попередній етап закрив {last_name} — зараз черга іншого учасника!</i>\n"

    await message.answer(
        f"{mode_title}\n"
        f"🧩 <b>{html.escape(session['title'])}</b>\n"
        f"{extra}\n"
        f"{render_step(steps, idx)}"
    )


@router.message(Command("ghint"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_ghint(message: Message):
    chat_id = message.chat.id
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["status"] != "active":
            await message.answer("Активної групової сесії немає.")
            return
        if session["mode"] == "race":
            await message.answer("У режимі гонки (/race) використовуй /hint в особистих повідомленнях з ботом!")
            return

        steps = load_steps(session)
        idx = current_index(session, steps)
        hint = steps[idx].get("hint")
        if not hint:
            await message.answer("Для цього етапу підказки немає.")
            return

        meta = parse_meta(session)
        mask = int(meta.get("hint_mask", 0))
        bit = 1 << idx
        note = ""
        if not (mask & bit):
            meta["hint_mask"] = mask | bit
            await db.update_group_session(chat_id, meta_json=json.dumps(meta))
            note = "\n\n<i>Нагорода за задачу трохи зменшена.</i>"
        await message.answer(f"💡 {hint}{note}")


@router.message(Command("gstop"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_gstop(message: Message):
    chat_id = message.chat.id
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session:
            await message.answer("Активної групової сесії немає.")
            return
        mode_title = MODE_TITLES.get(session["mode"], session["mode"])
        await cleanup_group_session(chat_id, session)
    await message.answer(f"🛑 Групову сесію ({mode_title}) зупинено, контейнери очищено.")


@router.message(Command("gcheck"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_gcheck(message: Message):
    chat_id = message.chat.id
    tg_id = message.from_user.id

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session:
            await message.answer("Активної групової сесії немає. Запустіть: /coop, /relay, /race або /koth")
            return

        if session["mode"] == "race":
            await message.answer("🏎 У режимі Швидкісної гонки перевіряй кроки командою /check в особистих повідомленнях з ботом!")
            return

        if session["mode"] == "koth":
            await message.answer(
                "🏰 У режимі Attack-Defense (/koth) для здачі знайденого прапора у Фазі 2 використовуйте:\n"
                "<code>/capture CTF{...}</code>"
            )
            return

        if session["status"] != "active" or not session.get("container_id"):
            await message.answer("Групова сесія ще не активна.")
            return

        meta = parse_meta(session)

        # Check relay baton handoff in Relay mode
        if session["mode"] == "relay":
            if session.get("last_actor_tg_id") == tg_id and not meta.get("force_turn"):
                await message.answer(
                    "🏃‍♂️ <b>Естафета!</b> Ти щойно закрив попередній етап. "
                    "Тепер команди та /gcheck має виконати інший учасник групи! "
                    "<i>(Для соло-тестування: /force_turn)</i>"
                )
                return

        user = await db.upsert_user(tg_id, message.from_user.username)
        await db.add_group_participant(
            session["id"], user["id"], tg_id, message.from_user.username or "", role="player"
        )

        steps = load_steps(session)
        idx = current_index(session, steps)

        try:
            ok = await dm.run_check(session["container_id"], steps[idx]["check"])
        except NotFound:
            await db.delete_group_session(chat_id)
            await message.answer("Контейнер більше не існує, групову сесію завершено.")
            return
        except Exception:
            log.exception("gcheck failed")
            await message.answer("⚠️ Помилка під час перевірки, спробуйте ще раз.")
            return

        if not ok:
            await message.answer("Крок ще не виконано, спробуйте ще. (/ghint — підказка)")
            return

        actor_name = format_user_mention(tg_id, message.from_user.username)

        if idx + 1 < len(steps):
            meta["force_turn"] = False
            await db.update_group_session(
                chat_id,
                step=idx + 1,
                last_actor_tg_id=tg_id,
                meta_json=json.dumps(meta),
            )
            relay_note = ""
            if session["mode"] == "relay":
                relay_note = (
                    f"\n🏃‍♂️ Етап закрив <b>{actor_name}</b>! "
                    "Естафетна паличка передається — наступний етап виконує <b>інший учасник групи</b>!\n"
                )
            await message.answer(
                f"✅ Крок {idx + 1}/{len(steps)} виконано ({actor_name})!\n"
                f"{relay_note}\n"
                f"{render_step(steps, idx + 1)}"
            )
            return

        # Final step of the group session completed!
        hint_mask = int(meta.get("hint_mask", 0))
        points = calc_reward(session["reward_points"], hint_mask)
        participants = await db.get_group_participants(session["id"])

        awarded_summary = []
        for p in participants:
            if p["role"] == "forfeited":
                continue
            pts = await db.award_points(p["user_id"], session["task_id"], points)
            p_name = format_user_mention(p["tg_id"], p["username"])
            awarded_summary.append(f"{p_name} (+{pts})" if pts else f"{p_name} (вже зараховано)")

        await cleanup_group_session(chat_id, session)

        await message.answer(
            f"🎉 <b>Групову задачу «{html.escape(session['title'])}» успішно розв'язано!</b>\n"
            f"Фінальний крок закрив: <b>{actor_name}</b>\n\n"
            f"🏆 <b>Учасники та бали:</b> {', '.join(awarded_summary)}"
        )
