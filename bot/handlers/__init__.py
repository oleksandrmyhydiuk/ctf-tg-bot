from aiogram import Router

from bot.handlers import common, group_common, group_koth, group_race, solo, terminal


def build_root_router() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(solo.router)
    root.include_router(group_common.router)
    root.include_router(group_race.router)
    root.include_router(group_koth.router)
    # Must be registered last so fallback private text handlers do not shadow commands.
    root.include_router(terminal.router)
    return root
