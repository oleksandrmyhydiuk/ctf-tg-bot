import re

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
