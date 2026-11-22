import asyncio
import html
import json
import logging
import time

from aiogram import Bot

import db
import docker_manager as dm
from bot.formatting import format_user_mention, parse_meta
from bot.services.sessions import cleanup_group_session
from bot.state import group_locks
from config import KOTH_ATTACK_SECONDS

log = logging.getLogger("bot")


async def koth_phase1_timer(bot: Bot, chat_id: int, session_id: int, delay: float) -> None:
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

        asyncio.create_task(koth_phase2_timer(bot, chat_id, session["id"]))


async def koth_phase2_timer(bot: Bot, chat_id: int, session_id: int) -> None:
    while True:
        await asyncio.sleep(5)
        session = await db.get_group_session(chat_id)
        if not session or session["id"] != session_id or session["mode"] != "koth" or session["status"] != "active":
            return
        if time.time() >= session["expires_at"]:
            await finish_koth_defenders_win(bot, chat_id)
            return


async def finish_koth_defenders_win(bot: Bot, chat_id: int) -> None:
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
