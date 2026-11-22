import html
import json

from config import CMD_TIMEOUT


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
