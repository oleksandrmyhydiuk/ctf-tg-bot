import asyncio
import html
import json
import logging
import re
import secrets
import sqlite3
import time
from collections import defaultdict

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from docker.errors import NotFound

import db
import docker_manager as dm
from config import (
    BOT_TOKEN,
    CMD_TIMEOUT,
    GROUP_SESSION_TTL,
    KOTH_ATTACK_SECONDS,
    KOTH_DEFEND_SECONDS,
    MAX_CMD_LEN,
    MAX_CONTAINERS,
    MAX_DISK_BYTES,
    MIN_CMD_INTERVAL,
    SESSION_TTL,
    TTL_CHECK_INTERVAL,
    WATCHDOG_INTERVAL,
)

log = logging.getLogger("bot")
router = Router()

# Global lock for checking and reserving MAX_CONTAINERS slots.
alloc_lock = asyncio.Lock()

# One user — one operation at a time (command / check / stop / creation).
locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
# One group chat — one operation on the shared container/session at a time.
group_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

last_cmd_at: dict[int, float] = {}

# Bot service commands. Everything else in private chat (even "/bin/ls") is treated as a terminal command.
BOT_COMMANDS_RE = re.compile(
    r"^/(start|tasks|task|hint|check|stop|top|race|coop|koth|relay|gtask|ghint|gcheck|gstop|capture|ready|force_turn)(@\w+)?(\s|$)"
)

# Terminal command prefix in group chats: `$ <cmd>` or `! <cmd>`
GROUP_CMD_RE = re.compile(r"^[!$]\s*(.+)", re.DOTALL)

DIFF_EMOJI = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}

MODE_TITLES = {
    "race": "🏎 Швидкісна гонка (Speed Race)",
    "coop": "🤝 Кооператив (Один термінал на всіх)",
    "koth": "🏰 Attack-Defense (King of the Hill)",
    "relay": "🏃‍♂️ Естафета (Relay)",
}

DEFAULT_GROUP_SLUGS = {
    "race": "race_incident_patch",
    "coop": "coop_hydra_malware",
    "koth": "koth_leaky_portal",
    "relay": "relay_crypto_heist",
}

MAX_RACE_PARTICIPANTS = 6

FOOTER = (
    "Надсилай команди текстом (початкова директорія: <code>/home/student</code>, можна багаторядково). "
    "Доступний <code>sudo</code> без пароля; мережі немає, лише localhost. "
    "Редактори (<code>vim</code>, <code>nano</code>) не працюють: використовуй "
    "<code>sed -i</code>, <code>tee</code>, heredoc.\n\n"
    "/check: перевірити крок · /hint: підказка (знижує нагороду) · "
    "/task: показати завдання · /stop: здатися"
)

GROUP_FOOTER = (
    "💬 <b>Як працювати в групі:</b>\n"
    "• Надсилай команди в чат через префікс <code>$ команда</code> або <code>! команда</code> (звичайні повідомлення ігноруються).\n"
    "• /gcheck — перевірити крок · /ghint — підказка · /gtask — умова · /gstop — зупинити сесію"
)


class Sandbox(StatesGroup):
    in_container = State()


# --------------------------------------------------------------- helpers

def format_output(raw: str, timed_out: bool, cwd: str) -> str:
    text = raw.replace("\x00", "")
    limit = 3000
    while True:
        part = text[:limit]
        escaped = html.escape(part)
        if len(escaped) <= 3500:
            break
        limit = int(limit * 0.7)

    notes = []
    if len(text) > len(part):
        notes.append("… вивід обрізано")
    if timed_out:
        notes.append(f"⏱ Команду перервано (ліміт {CMD_TIMEOUT} с)")

    body = escaped if escaped.strip() else "(порожній вивід)"
    result = f"<pre>{body}</pre>"
    if notes:
        result += "\n" + html.escape("\n".join(notes))
    return result + f"\n📂 <code>{html.escape(cwd)}</code>"


def load_steps(session) -> list[dict]:
    return json.loads(session["steps_json"])


def current_index(session, steps: list[dict]) -> int:
    return min(session["step"], len(steps) - 1)


def render_step(steps: list[dict], idx: int) -> str:
    return f"📌 <b>Крок {idx + 1}/{len(steps)}</b>\n{steps[idx]['text']}"


def calc_reward(reward: int, hint_mask: int) -> int:
    """Each hint (on a separate step) deducts ~20% of the reward, capped at half."""
    hints = bin(hint_mask).count("1")
    return max(reward // 2, reward - hints * max(1, reward // 5))


def format_user_mention(tg_id: int, username: str | None) -> str:
    if username:
        return f"@{html.escape(username)}"
    return f"id{str(tg_id)[-4:]}"


def parse_meta(session) -> dict:
    try:
        return json.loads(session["meta_json"] or "{}")
    except Exception:
        return {}


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


def render_race_lobby_text(session: dict, participants: list[dict]) -> str:
    steps = load_steps(session)
    emoji = DIFF_EMOJI.get(session["difficulty"], "⚪")
    bonus = int(session["reward_points"] * 1.5)
    if participants:
        p_list = ", ".join(format_user_mention(p["tg_id"], p["username"]) for p in participants)
    else:
        p_list = "<i>поки нікого — тисни кнопку нижче!</i>"

    return (
        f"🏎 <b>Швидкісна гонка: «{html.escape(session['title'])}»</b> {emoji}\n\n"
        f"{session['description']}\n\n"
        f"📊 Кроків: <b>{len(steps)}</b> · Нагорода переможцю: <b>+{bonus} балів</b> (1.5x)\n"
        f"👥 Учасники ({len(participants)}/{MAX_RACE_PARTICIPANTS}): {p_list}\n\n"
        "<i>Кожен учасник отримає власний ізольований контейнер в особистих повідомленнях (DM) з ботом. "
        "Хто першим пройде фінальний /check — забирає перемогу!</i>"
    )


def build_race_lobby_kb(session_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="🏁 Беру участь", callback_data=f"race_join:{session_id}")
    kb.button(text="▶️ Старт", callback_data=f"race_start:{session_id}")
    kb.button(text="❌ Скасувати", callback_data=f"race_cancel:{session_id}")
    kb.adjust(2, 1)
    return kb.as_markup()


def render_race_board(session: dict, participants: list[dict], winner_tg_id: int | None = None) -> str:
    steps = load_steps(session)
    total = len(steps)
    rem = max(0, int(session["expires_at"] - time.time()))
    mins, secs = divmod(rem, 60)

    header = (
        f"🏁 <b>Гонку завершено: «{html.escape(session['title'])}»</b>\n"
        if winner_tg_id
        else f"🏎 <b>Гонка триває: «{html.escape(session['title'])}»</b> (⏱ {mins:02d}:{secs:02d})\n"
    )

    lines = [header]
    for p in participants:
        name = format_user_mention(p["tg_id"], p["username"])
        if winner_tg_id and p["tg_id"] == winner_tg_id:
            bar = "█" * total
            lines.append(f"🏆 <b>{name}</b> — Переможець! <code>[{bar}]</code> ({total}/{total})")
        elif p["role"] == "forfeited":
            lines.append(f"🏳️ {name} — <i>зійшов з дистанції</i>")
        else:
            done = min(p["step"], total)
            bar = "█" * done + "░" * max(0, total - done)
            cur = min(done + 1, total)
            lines.append(f"🏃 {name} — Крок {cur}/{total} <code>[{bar}]</code>")

    if not winner_tg_id:
        lines.append("\n<i>Учасники виконують команди та /check в особистих повідомленнях з ботом.</i>")
    return "\n".join(lines)


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


def render_koth_lobby_text(session: dict, participants: list[dict]) -> str:
    defenders = [format_user_mention(p["tg_id"], p["username"]) for p in participants if p["role"] == "defender"]
    attackers = [format_user_mention(p["tg_id"], p["username"]) for p in participants if p["role"] == "attacker"]
    def_str = ", ".join(defenders) if defenders else "<i>немає</i>"
    att_str = ", ".join(attackers) if attackers else "<i>немає</i>"

    return (
        f"🏰 <b>Attack-Defense (King of the Hill): «{html.escape(session['title'])}»</b>\n\n"
        f"{session['description']}\n\n"
        f"🛡 <b>Захисники (Фаза 1 — {KOTH_DEFEND_SECONDS // 60} хв, sudo/root):</b> {def_str}\n"
        f"⚔️ <b>Атакуючі (Фаза 2 — {KOTH_ATTACK_SECONDS // 60} хв, user=attacker):</b> {att_str}\n\n"
        "Оберіть команду та натисніть <b>▶️ Старт битви</b>!"
    )


def build_koth_lobby_kb(session_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="🛡 Захисник (Фаза 1)", callback_data=f"koth_role:{session_id}:defender")
    kb.button(text="⚔️ Атакуючий (Фаза 2)", callback_data=f"koth_role:{session_id}:attacker")
    kb.button(text="▶️ Старт битви", callback_data=f"koth_start:{session_id}")
    kb.button(text="❌ Скасувати", callback_data=f"koth_cancel:{session_id}")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def build_koth_phase1_kb(session_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Захист готовий — почати Фазу 2", callback_data=f"koth_ready:{session_id}")
    return kb.as_markup()


async def build_task_picker_kb(mode: str):
    async with db.conn() as conn:
        cur = await conn.execute(
            "SELECT id, slug, title, difficulty, reward_points FROM tasks "
            "ORDER BY CASE difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id"
        )
        rows = await cur.fetchall()
    kb = InlineKeyboardBuilder()
    default_slug = DEFAULT_GROUP_SLUGS.get(mode)
    # Recommended task for this mode comes first
    sorted_rows = sorted(rows, key=lambda r: (0 if r["slug"] == default_slug else 1, r["id"]))
    for r in sorted_rows[:12]:
        star = "⭐ " if r["slug"] == default_slug else ""
        emoji = DIFF_EMOJI.get(r["difficulty"], "⚪")
        kb.button(
            text=f"{star}{emoji} {r['title']} (+{r['reward_points']})",
            callback_data=f"gpick:{mode}:{r['slug']}",
        )
    kb.adjust(1)
    return kb.as_markup()


# --------------------------------------------------------------- universal commands (/start, /top)

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.upsert_user(message.from_user.id, message.from_user.username)
    if message.chat.type == "private":
        await message.answer(
            "👋 Вітаю в <b>CTF/DevOps &amp; Security Sandbox</b>!\n\n"
            "Розв'язуй практичні завдання з Linux, кібербезпеки, баз даних і мереж в ізольованому "
            "контейнері прямо в чаті. Більшість задач складаються з кількох кроків.\n\n"
            f"🏆 Твої бали: <b>{user['score']}</b>\n\n"
            "<b>Індивідуальні команди (в DM):</b>\n"
            "/tasks — список завдань\n"
            "/task — поточне завдання\n"
            "/check — перевірити крок\n"
            "/hint — підказка\n"
            "/top — рейтинг\n"
            "/stop — завершити сесію\n\n"
            "<b>Групові режими (додай бота в групу!):</b>\n"
            "/race — 🏎 Швидкісна гонка (кожному свій контейнер у DM)\n"
            "/coop — 🤝 Один термінал на всіх (спільний інцидент-респонс)\n"
            "/koth — 🏰 Attack-Defense (5 хв Захист vs 10 хв Атака)\n"
            "/relay — 🏃‍♂️ Естафета з примусовою передачею ходу"
        )
    else:
        await message.answer(
            "👋 Вітаю в <b>CTF/DevOps &amp; Security Sandbox (Груповий режим)</b>!\n\n"
            f"🏆 Твої бали: <b>{user['score']}</b>\n\n"
            "<b>Мультиплеєрні режими для групи:</b>\n"
            "• /race <code>[slug]</code> — 🏎 <b>Швидкісна гонка:</b> кожен отримує власний контейнер у DM, перший /check перемагає!\n"
            "• /coop <code>[slug]</code> — 🤝 <b>Один термінал на всіх:</b> спільний контейнер у групі (команди через <code>$ cmd</code> або <code>! cmd</code>).\n"
            "• /koth <code>[slug]</code> — 🏰 <b>King of the Hill (Attack-Defense):</b> Фаза 1 (5 хв) захисники ховають прапор і ставлять пастки, Фаза 2 (10 хв) атакуючі шукають прапор і здають через <code>/capture CTF{...}</code>.\n"
            "• /relay <code>[slug]</code> — 🏃‍♂️ <b>Естафета:</b> один гравець не може закрити два етапи поспіль!\n\n"
            "<b>Керування груповою грою:</b>\n"
            "/gtask — поточне завдання · /gcheck — перевірити крок · /ghint — підказка · /gstop — зупинити · /top — рейтинг\n\n"
            "<i>Для індивідуальної гри напиши боту /tasks в особисті повідомлення (DM)!</i>"
        )


@router.message(Command("top"))
async def cmd_top(message: Message):
    rows = await db.leaderboard(10)
    if not rows:
        hint_cmd = "/tasks" if message.chat.type == "private" else "/coop або /race"
        await message.answer(f"Рейтинг поки порожній. Розв'яжи першу задачу: {hint_cmd}")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, r in enumerate(rows):
        name = f"@{r['username']}" if r["username"] else f"id{str(r['tg_id'])[-4:]}"
        lines.append(f"{medals[i] if i < 3 else f'{i + 1}.'} {html.escape(name)}: {r['score']}")
    await message.answer("🏆 <b>Рейтинг</b>\n" + "\n".join(lines))


# --------------------------------------------------------------- solo commands (private chat only)

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


async def _get_active(message: Message, state: FSMContext):
    """Returns (user, session) or (None, None) after replying to the user."""
    user = await db.get_user(message.from_user.id)
    session = await db.get_session(user["id"]) if user else None
    if not session:
        await state.clear()
        await message.answer("Активної сесії немає. Обери завдання: /tasks")
        return None, None
    return user, session


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
                    other_Racers = []
                    for p in participants:
                        if p["tg_id"] != tg_id and p.get("container_id") and p["role"] != "forfeited":
                            other_cids.append(p["container_id"])
                            other_Racers.append(p)
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
                    for p in other_Racers:
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


# --------------------------------------------------------------- group modes (/race, /coop, /koth, /relay)

async def _find_active_koth_defender_session(tg_id: int) -> dict | None:
    """Checks whether the user is a defender in an active Phase 1 (/koth) of any group."""
    async with db.conn() as conn:
        cur = await conn.execute(
            """
            SELECT gs.*
            FROM group_participants gp
            JOIN group_sessions gs ON gs.id = gp.session_id
            WHERE gs.mode = 'koth'
              AND gs.status = 'phase1_defend'
              AND gp.tg_id = ?
              AND gp.role = 'defender'
            ORDER BY gs.id DESC LIMIT 1
            """,
            (tg_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


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


# --------------------------------------------------------------- Mode 1: Speed Race callbacks

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


# --------------------------------------------------------------- Mode 3: King of the Hill (Attack-Defense)

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

        asyncio.create_task(_koth_phase1_timer(call.bot, chat_id, session["id"], KOTH_DEFEND_SECONDS))


async def _koth_phase1_timer(bot: Bot, chat_id: int, session_id: int, delay: float) -> None:
    await asyncio.sleep(max(1.0, delay))
    session = await db.get_group_session(chat_id)
    if session and session["id"] == session_id and session["mode"] == "koth" and session["status"] == "phase1_defend":
        await transition_koth_to_phase2(bot, chat_id)


async def transition_koth_to_phase2(bot: Bot, chat_id: int) -> None:
    """Atomic Phase 1 -> Phase 2 transition with environment sanitization and Anti-Brick SLA check."""
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "koth" or session["status"] != "phase1_defend":
            return

        cid = session["container_id"]
        meta = parse_meta(session)
        flag = meta.get("flag", "")

        # 1. Sanitize environment before Phase 2
        try:
            await dm.sanitize_koth_phase2(cid)
        except Exception:
            log.exception("sanitize_koth_phase2 failed")

        # 2. Out-of-band flag check from host via get_archive + portal SLA check on port 8080
        raw_bytes = await dm.read_file_from_container(cid, "/var/www/flag.txt")
        flag_intact = bool(raw_bytes and flag.encode() in raw_bytes)

        sla_check_script = (
            f"runuser -u www-data -- grep -qx '{flag}' /var/www/flag.txt && "
            f"curl -s --max-time 3 http://127.0.0.1:8080/ | grep -q 'Intranet Portal'"
        )
        try:
            sla_ok = flag_intact and await dm.run_check(cid, sla_check_script)
        except Exception:
            sla_ok = False

        sla_notice = "✅ <b>SLA перевірка пройдена:</b> портал на порту <code>8080</code> працює, прапор валідний."
        if not sla_ok:
            restore_script = (
                f"mkdir -p /var/www/portal && "
                f"printf '%s\\n' '{flag}' > /var/www/flag.txt && "
                f"chown www-data:www-data /var/www/flag.txt && "
                f"chmod 0640 /var/www/flag.txt && "
                f"echo 'Intranet Portal v2.4 - SLA OK' > /var/www/portal/index.html && "
                f"chown -R www-data:www-data /var/www/portal && "
                f"(service nginx restart 2>/dev/null || nginx 2>/dev/null || true)"
            )
            try:
                await dm.run_check(cid, restore_script)
            except Exception:
                log.exception("Failed to restore KOTH SLA")
            meta["sla_restored"] = True
            sla_notice = (
                "⚠️ <b>Anti-Brick SLA спрацював!</b> Захисники пошкодили прапор або поклали портал на порту 8080. "
                "Файл <code>/var/www/flag.txt</code> (права <code>0640</code>, власник <code>www-data</code>) та веб-сервіс автоматично відновлено!"
            )

        now = time.time()
        phase2_end = now + KOTH_ATTACK_SECONDS
        meta["phase2_started_at"] = now
        meta["phase2_ends_at"] = phase2_end

        await db.update_group_session(
            chat_id,
            status="active",
            cwd="/home/attacker",
            expires_at=phase2_end,
            meta_json=json.dumps(meta),
        )

        participants = await db.get_group_participants(session["id"])
        attackers = [format_user_mention(p["tg_id"], p["username"]) for p in participants if p["role"] == "attacker"]
        att_str = ", ".join(attackers) if attackers else "усі учасники групи"

        try:
            await bot.send_message(
                chat_id,
                f"⚔️ <b>Фаза 2: Атака почалася! ({KOTH_ATTACK_SECONDS // 60} хв)</b>\n\n"
                f"{sla_notice}\n\n"
                f"• Захисники переведені в режим глядачів (root/sudo та фонові процеси очищено).\n"
                f"• Атакуючі ({att_str}) працюють від непривілейованого <code>user=attacker</code> (UID 1001, без sudo).\n"
                f"• Вводьте команди в чаті через <code>$ команда</code> або <code>! команда</code>.\n"
                f"• Знайдіть справжній прапор і здайте його командою:\n"
                f"  <code>/capture CTF{{...}}</code>\n"
                f"⚠️ Обережно: здача фейкового прапора-пастки <code>CTF{{trap_...}}</code> штрафує час атаки на <b>-60 сек</b>!",
            )
        except Exception:
            log.warning("Failed to send Phase 2 start message to %s", chat_id)

        asyncio.create_task(_koth_phase2_timer(bot, chat_id, session["id"]))


async def _koth_phase2_timer(bot: Bot, chat_id: int, session_id: int) -> None:
    while True:
        await asyncio.sleep(5)
        session = await db.get_group_session(chat_id)
        if not session or session["id"] != session_id or session["mode"] != "koth" or session["status"] != "active":
            return
        if time.time() >= session["expires_at"]:
            await _finish_koth_defenders_win(bot, chat_id)
            return


async def _finish_koth_defenders_win(bot: Bot, chat_id: int) -> None:
    async with group_locks[chat_id]:
        session = await db.get_group_session(chat_id)
        if not session or session["mode"] != "koth" or session["status"] != "active":
            return

        participants = await db.get_group_participants(session["id"])
        defenders = [p for p in participants if p["role"] == "defender"]
        points = session["reward_points"]

        awarded_names = []
        for d in defenders:
            pts = await db.award_points(d["user_id"], session["task_id"], points)
            name = format_user_mention(d["tg_id"], d["username"])
            awarded_names.append(f"{name} (+{pts})" if pts else f"{name} (вже зараховано)")

        await cleanup_group_session(chat_id, session)

        def_summary = ", ".join(awarded_names) if awarded_names else "Захисники"
        try:
            await bot.send_message(
                chat_id,
                f"🛡🏆 <b>Час вийшов! Захисники втримали фортецю «{html.escape(session['title'])}»!</b>\n\n"
                f"Атакуючі не змогли здобути прапор за відведений час.\n"
                f"🎁 Нагорода захисникам: {def_summary}",
            )
        except Exception:
            pass


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
        koth_session = await _find_active_koth_defender_session(message.from_user.id)
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
                asyncio.create_task(_finish_koth_defenders_win(message.bot, chat_id))
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


# --------------------------------------------------------------- shared group commands (/gtask, /ghint, /gcheck, /gstop, /force_turn)

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


# ------------------------------------------------- group terminal input (`$ <cmd>` or `! <cmd>`)

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


# ------------------------------------------------- solo terminal input (Private Chat Only)

async def process_terminal_input(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    text = message.text or ""

    # If the user is an active Defender in Phase 1 (/koth) and writes `$ <cmd>` in DM (with no solo session)
    user = await db.get_user(tg_id)
    solo_session = await db.get_session(user["id"]) if user else None
    if not solo_session:
        koth_session = await _find_active_koth_defender_session(tg_id)
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


# --------------------------------------------------------------- background

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
                    await _finish_koth_defenders_win(bot, chat_id)
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


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    await db.init_db()
    await dm.ensure_image()
    await reconcile()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    background = [
        asyncio.create_task(ttl_worker(bot)),
        asyncio.create_task(disk_watchdog(bot)),
    ]
    try:
        await dp.start_polling(bot)
    finally:
        for t in background:
            t.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
