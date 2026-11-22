import html
import time

from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
from bot.constants import DEFAULT_GROUP_SLUGS, DIFF_EMOJI, MAX_RACE_PARTICIPANTS
from bot.formatting import format_user_mention, load_steps
from config import KOTH_ATTACK_SECONDS, KOTH_DEFEND_SECONDS


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
    rows = await db.list_tasks_for_picker()
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
