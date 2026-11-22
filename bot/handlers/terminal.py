import html
import logging
import time

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from docker.errors import NotFound

import db
import docker_manager as dm
from bot.constants import BOT_COMMANDS_RE, GROUP_CMD_RE
from bot.formatting import format_output, format_user_mention, parse_meta
from bot.state import Sandbox, group_locks, last_cmd_at, locks
from config import MAX_CMD_LEN, MIN_CMD_INTERVAL

log = logging.getLogger("bot")
router = Router()


@router.message(
    F.chat.type.in_({"group", "supergroup"}),
    F.text.regexp(GROUP_CMD_RE),
)
async def on_group_terminal_cmd(message: Message):
    chat_id = message.chat.id
    tg_id = message.from_user.id
    match = GROUP_CMD_RE.match(message.text or "")
    if not match:
        return
    cmd = match.group(1).strip()
    if not cmd:
        return

    if len(cmd) > MAX_CMD_LEN:
        await message.answer(f"Команда задовга (максимум {MAX_CMD_LEN} символів).")
        return

    now = time.monotonic()
    if now - last_cmd_at.get(tg_id, 0) < MIN_CMD_INTERVAL:
        await message.answer("Не так швидко 🙂")
        return
    last_cmd_at[tg_id] = now

    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session:
            return

        if session["mode"] == "race":
            await message.answer("🏎 У режимі гонки (/race) виконуй команди у своєму контейнері в DM бота!")
            return

        if not session.get("container_id") or session["status"] not in {"active", "phase1_defend"}:
            await message.answer("⏳ Груповий контейнер ще не запущено.")
            return

        participants = await db.get_group_participants(session["id"])
        meta = parse_meta(session)
        exec_user = "student"

        # Check permissions and roles in Attack-Defense (/koth) mode
        if session["mode"] == "koth":
            defenders = {p["tg_id"] for p in participants if p["role"] == "defender"}
            attackers = {p["tg_id"] for p in participants if p["role"] == "attacker"}
            if session["status"] == "phase1_defend":
                if defenders and tg_id not in defenders:
                    await message.answer("🛡 Зараз Фаза 1 (Захист)! Атакуючі отримають доступ до терміналу у Фазі 2.")
                    return
                exec_user = "student"
            else:
                if attackers and tg_id in defenders:
                    await message.answer(
                        "👀 Фаза 1 завершена! У Фазі 2 захисники лише спостерігають, а команди виконують Атакуючі."
                    )
                    return
                exec_user = "attacker"

        # Check turn order in Relay mode (/relay)
        if session["mode"] == "relay":
            if session.get("last_actor_tg_id") == tg_id and not meta.get("force_turn"):
                await message.answer(
                    "🏃‍♂️ <b>Естафета!</b> Ти щойно закрив попередній етап. "
                    "Тепер команди та /gcheck має виконати інший учасник групи! "
                    "<i>(Для соло-тестування: /force_turn)</i>"
                )
                return

        user = await db.upsert_user(tg_id, message.from_user.username)
        default_role = (
            "defender"
            if (session["mode"] == "koth" and session["status"] == "phase1_defend")
            else ("attacker" if session["mode"] == "koth" else "player")
        )
        await db.add_group_participant(
            session["id"], user["id"], tg_id, message.from_user.username or "", role=default_role
        )

        log.info("GCMD chat=%s tg=%s mode=%s user=%s: %r", chat_id, tg_id, session["mode"], exec_user, cmd)
        await message.bot.send_chat_action(chat_id, "typing")

        try:
            output, timed_out, new_cwd = await dm.run_command(
                session["container_id"], cmd, session["cwd"], user=exec_user
            )
        except NotFound:
            await db.delete_group_session(chat_id)
            await message.answer("Контейнер більше не існує, групову сесію завершено.")
            return
        except Exception:
            log.exception("group run_command failed")
            await message.answer("⚠️ Не вдалося виконати команду в груповому контейнері.")
            return

        if new_cwd != session["cwd"]:
            await db.update_group_session(chat_id, cwd=new_cwd)

    actor = format_user_mention(tg_id, message.from_user.username)
    prefix_char = "!" if (message.text or "").startswith("!") else "$"
    header = f"👤 <b>{actor}</b> <code>{prefix_char} {html.escape(cmd)}</code>\n"
    await message.answer(header + format_output(output, timed_out, new_cwd))


async def process_terminal_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    text = message.text or ""

    # If the user is an active Defender in Phase 1 (/koth) and writes `$ <cmd>` in DM (with no solo session)
    user = await db.get_user(tg_id)
    solo_session = await db.get_session(user["id"]) if user else None
    if not solo_session:
        koth_session = await db.find_active_koth_defender_session(tg_id)
        if koth_session:
            m = GROUP_CMD_RE.match(text)
            cmd = m.group(1).strip() if m else text.strip()
            if len(cmd) > MAX_CMD_LEN:
                await message.answer(f"Команда задовга (максимум {MAX_CMD_LEN} символів).")
                return
            now = time.monotonic()
            if now - last_cmd_at.get(tg_id, 0) < MIN_CMD_INTERVAL:
                await message.answer("Не так швидко 🙂")
                return
            last_cmd_at[tg_id] = now

            chat_id = koth_session["chat_id"]
            async with group_locks[chat_id]:
                fresh = await db.get_group_session(chat_id)
                if not fresh or fresh["status"] != "phase1_defend" or not fresh.get("container_id"):
                    await message.answer("Фаза 1 (Захист) вже завершилася.")
                    return
                await message.bot.send_chat_action(message.chat.id, "typing")
                try:
                    output, timed_out, new_cwd = await dm.run_command(
                        fresh["container_id"], cmd, fresh["cwd"], user="student"
                    )
                except NotFound:
                    await db.delete_group_session(chat_id)
                    await message.answer("Контейнер битви більше не існує.")
                    return
                except Exception:
                    log.exception("koth dm run_command failed")
                    await message.answer("⚠️ Не вдалося виконати команду.")
                    return
                if new_cwd != fresh["cwd"]:
                    await db.update_group_session(chat_id, cwd=new_cwd)
            await message.answer("🛡 <b>[KOTH Захист]</b>\n" + format_output(output, timed_out, new_cwd))
            return

    if len(text) > MAX_CMD_LEN:
        await message.answer(f"Команда задовга (максимум {MAX_CMD_LEN} символів).")
        return

    now = time.monotonic()
    if now - last_cmd_at.get(tg_id, 0) < MIN_CMD_INTERVAL:
        await message.answer("Не так швидко 🙂")
        return
    last_cmd_at[tg_id] = now

    async with locks[tg_id]:
        user = await db.get_user(tg_id)
        session = await db.get_session(user["id"]) if user else None
        if not session:
            await state.clear()
            await message.answer("Активної сесії немає. Обери завдання: /tasks")
            return

        # Audit: all commands are logged (for incident investigation).
        log.info("CMD tg=%s task=%s: %r", tg_id, session["task_id"], text)

        # Restore FSM state if lost (e.g., after a bot restart).
        await state.set_state(Sandbox.in_container)
        await message.bot.send_chat_action(message.chat.id, "typing")

        try:
            output, timed_out, cwd = await dm.run_command(
                session["container_id"], text, session["cwd"]
            )
        except NotFound:
            await db.delete_session(user["id"])
            await state.clear()
            await message.answer("Контейнер більше не існує, сесію завершено. /tasks")
            return
        except Exception:
            log.exception("run_command failed")
            await message.answer("⚠️ Не вдалося виконати команду.")
            return

        if cwd != session["cwd"]:
            await db.set_cwd(user["id"], cwd)

    await message.answer(format_output(output, timed_out, cwd))


@router.message(
    F.chat.type == "private",
    StateFilter(Sandbox.in_container),
    F.text,
    ~F.text.regexp(BOT_COMMANDS_RE),
)
async def on_terminal_text(message: Message, state: FSMContext):
    await process_terminal_input(message, state)


# Fallback handler without state (private chats only): restores session from DB after a bot restart.
@router.message(
    F.chat.type == "private",
    F.text,
    ~F.text.regexp(BOT_COMMANDS_RE),
)
async def on_text_fallback(message: Message, state: FSMContext):
    await process_terminal_input(message, state)
