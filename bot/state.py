import asyncio
from collections import defaultdict

from aiogram.fsm.state import State, StatesGroup

# Global lock for checking and reserving MAX_CONTAINERS slots.
alloc_lock = asyncio.Lock()

# One user — one operation at a time (command / check / stop / creation).
locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# One group chat — one operation on the shared container/session at a time.
group_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# Rate-limiting timestamps per user (monotonic clock).
last_cmd_at: dict[int, float] = {}


class Sandbox(StatesGroup):
    in_container = State()
