import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import db
import docker_manager as dm
from api.server import start_webapp_server
from bot.handlers import build_root_router
from bot.services.workers import disk_watchdog, reconcile, ttl_worker
from config import BOT_TOKEN, WEBAPP_ENABLED


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    await db.init_db()
    await dm.ensure_image()
    await reconcile()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_root_router())

    webapp_runner = None
    if WEBAPP_ENABLED:
        webapp_runner = await start_webapp_server()

    background = [
        asyncio.create_task(ttl_worker(bot)),
        asyncio.create_task(disk_watchdog(bot)),
    ]
    try:
        await dp.start_polling(bot)
    finally:
        for t in background:
            t.cancel()
        if webapp_runner is not None:
            await webapp_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
