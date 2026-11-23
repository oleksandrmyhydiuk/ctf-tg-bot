import html

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

import db
from config import WEBAPP_URL

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.upsert_user(message.from_user.id, message.from_user.username)
    if message.chat.type == "private":
        reply_markup = (
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⚡ Відкрити Cyberpunk Mini App",
                            web_app=WebAppInfo(url=WEBAPP_URL),
                        )
                    ]
                ]
            )
            if WEBAPP_URL
            else None
        )
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
            "/relay — 🏃‍♂️ Естафета з примусовою передачею ходу",
            reply_markup=reply_markup,
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
