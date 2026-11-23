import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env located next to config.py (regardless of current working directory)
load_dotenv(Path(__file__).resolve().parent / ".env")

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = os.getenv("DB_PATH", "sandbox.db")

# Docker
BASE_IMAGE = "ubuntu:22.04"
IMAGE = "ctf-sandbox:3"  # built automatically on startup (Dockerfile in docker_manager.py)
RUNTIME = os.getenv("DOCKER_RUNTIME") or None  # e.g. "runsc" for gVisor
# Hard container disk limit (only works on overlay2 + xfs with pquota), e.g. "500m"
STORAGE_SIZE = os.getenv("DOCKER_STORAGE_SIZE") or None

# Container resource limits
MEM_LIMIT = "128m"
PIDS_LIMIT = 64
MAX_DISK_BYTES = 300 * 1024 * 1024  # watchdog kills session if writable layer exceeds this
WATCHDOG_INTERVAL = 15              # seconds between disk usage checks

# Session and command limits
SESSION_TTL = 15 * 60       # session lifetime in seconds
GROUP_SESSION_TTL = 1200    # group session lifetime in seconds (20 min)
KOTH_DEFEND_SECONDS = 300   # Attack-Defense defend phase duration in seconds (5 min)
KOTH_ATTACK_SECONDS = 600   # Attack-Defense attack phase duration in seconds (10 min)
TTL_CHECK_INTERVAL = 60     # how often to scan for expired sessions
MAX_CONTAINERS = int(os.getenv("MAX_CONTAINERS", "20"))  # global limit on concurrent containers
CMD_TIMEOUT = 10            # timeout in seconds for a single user command
MAX_RAW_OUTPUT = 4000       # max output bytes read from container
MAX_CMD_LEN = 500           # maximum command length
MIN_CMD_INTERVAL = 0.7      # rate limit: minimum seconds between commands per user

# Telegram Mini App (WebApp)
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
WEBAPP_ENABLED = os.getenv("WEBAPP_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off", ""}
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0").strip() or "0.0.0.0"
WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8080"))
_webapp_dev_uid = os.getenv("WEBAPP_DEV_USER_ID", "").strip()
WEBAPP_DEV_USER_ID: int | None = int(_webapp_dev_uid) if _webapp_dev_uid else None
