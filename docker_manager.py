"""Isolated container management.

docker-py is synchronous, so all public async functions run their work
via asyncio.to_thread to avoid blocking the aiogram event loop.

Isolation model: the user has sudo (root inside the container), but the
container is unprivileged, has no network (loopback only), no host mounts,
a reduced set of capabilities, CPU/RAM/PID limits, and Docker's default
seccomp/AppArmor profiles. Security relies on isolation rather than input filtering.
"""
import asyncio
import io
import logging
import re
import tarfile
from pathlib import Path
from typing import Optional

import docker
from docker.errors import ImageNotFound, NotFound
from docker.types import Ulimit

from config import (
    BASE_IMAGE,
    CMD_TIMEOUT,
    IMAGE,
    MAX_RAW_OUTPUT,
    MEM_LIMIT,
    PIDS_LIMIT,
    RUNTIME,
    STORAGE_SIZE,
)

log = logging.getLogger(__name__)

client = docker.from_env(timeout=120, max_pool_size=20)

LABEL = "ctf_sandbox"
USER = "student"
HOME = "/home/student"
# File for persisting cwd between commands. Stored in /dev/shm so it doesn't show up in `ls -a /tmp`.
CWD_FILE = "/dev/shm/.cwd"

# The sandbox Dockerfile lives alongside this file (sandbox.Dockerfile): single source of truth,
# also used by docker compose / manual builds.
SANDBOX_DOCKERFILE = Path(__file__).resolve().parent / "sandbox.Dockerfile"

# Executed before each task setup: sudo should not stall on hostname resolution.
PRELUDE = "grep -q ' sandbox' /etc/hosts || echo '127.0.0.1 sandbox' >> /etc/hosts\n"

# Minimal capability set for root inside the container. Excludes SYS_ADMIN, NET_RAW,
# MKNOD, SYS_PTRACE, SYS_MODULE, DAC_READ_SEARCH, SYS_RAWIO, SETFCAP, SETPCAP, etc.
# NET_ADMIN is safe because network_disabled=True isolates the container in its own loopback netns.
CAP_ADD = [
    "CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID",
    "SETUID", "SETGID", "KILL", "SYS_CHROOT", "AUDIT_WRITE",
    "NET_BIND_SERVICE", "NET_ADMIN",
]

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_CWD_RE = re.compile(r"/[^\n\x00]*")


class SandboxError(Exception):
    pass


def _wrap(timeout: int, max_bytes: int) -> str:
    """Wrapper for `bash -c <wrapper> <script>`.

    Script output goes to a file rather than a pipe: daemons started by a command
    (e.g., service nginx start) inherit the file instead of the pipe, so exec does
    not hang waiting for EOF. stdin = /dev/null. Script exit code is preserved (124 = timeout).
    """
    return (
        "f=$(mktemp -p /dev/shm .outXXXXXX); "
        f'timeout -k 1 {timeout} bash -c "$0" >"$f" 2>&1 </dev/null; rc=$?; '
        f'head -c {max_bytes} "$f"; rm -f "$f"; exit $rc'
    )


# ---------------------------------------------------------------- sync part

def _ensure_image_sync() -> None:
    try:
        client.images.get(IMAGE)
        return
    except ImageNotFound:
        pass
    log.info("Building image %s from %s (internet required, 2-5 min, one-time)...", IMAGE, BASE_IMAGE)
    dockerfile = SANDBOX_DOCKERFILE.read_bytes()
    client.images.build(
        fileobj=io.BytesIO(dockerfile),
        tag=IMAGE,
        rm=True,
        buildargs={"BASE_IMAGE": BASE_IMAGE},
    )


def _exec_simple(container, script: str, user: str, timeout: int):
    code, out = container.exec_run(
        ["bash", "-c", _wrap(timeout, 2000), script],
        user=user,
        workdir="/",
    )
    return code, (out or b"").decode("utf-8", "replace")


def _create_sync(setup_script: str, mem_limit: str | None, pids_limit: int | None) -> str:
    mem = mem_limit or MEM_LIMIT
    kwargs = dict(
        command="sleep infinity",
        detach=True,
        tty=True,
        init=True,
        hostname="sandbox",
        labels={LABEL: "1"},
        # Resources (limits may be raised for service-based tasks)
        mem_limit=mem,
        memswap_limit=mem,
        nano_cpus=500_000_000,
        pids_limit=pids_limit or PIDS_LIMIT,
        shm_size="16m",
        # Network and privileges. Intentionally omit no-new-privileges: it breaks sudo.
        # Default Docker seccomp and AppArmor profiles remain active.
        network_disabled=True,
        privileged=False,
        cap_drop=["ALL"],
        cap_add=CAP_ADD,
        ulimits=[
            Ulimit(name="nofile", soft=1024, hard=2048),
            Ulimit(name="fsize", soft=52428800, hard=52428800),
            Ulimit(name="core", soft=0, hard=0),
        ],
        tmpfs={
            HOME: "size=20m,uid=1000,gid=1000,mode=755",
            "/home/attacker": "size=10m,uid=1001,gid=1001,mode=755",
            "/tmp": "size=20m,mode=1777",
            "/var/tmp": "size=10m,mode=1777",
        },
    )
    if RUNTIME:
        kwargs["runtime"] = RUNTIME
    if STORAGE_SIZE:
        kwargs["storage_opt"] = {"size": STORAGE_SIZE}

    container = client.containers.run(IMAGE, **kwargs)
    try:
        code, out = _exec_simple(container, PRELUDE + setup_script, user="root", timeout=60)
        if code != 0:
            raise SandboxError(f"setup_script failed ({code}): {out}")
    except Exception:
        _destroy_sync(container.id)
        raise
    return container.id


def _destroy_sync(container_id: str) -> None:
    try:
        client.containers.get(container_id).remove(force=True)
    except NotFound:
        pass


def _run_command_sync(container_id: str, cmd: str, cwd: str, user: str = USER):
    container = client.containers.get(container_id)
    safe_user = re.sub(r"[^a-zA-Z0-9_-]", "", user) or USER
    cwd_file = f"{CWD_FILE}_{safe_user}"

    # User command + save resulting cwd. `exit $__rc` preserves the exit code.
    inner = f"{cmd}\n__rc=$?\npwd > {cwd_file} 2>/dev/null\nexit $__rc"
    outer = f"rm -f {cwd_file}; " + _wrap(CMD_TIMEOUT, MAX_RAW_OUTPUT)
    code, out = container.exec_run(["bash", "-c", outer, inner], user=user, workdir=cwd)
    text = _ANSI_RE.sub("", (out or b"").decode("utf-8", "replace"))

    new_cwd = cwd
    c2, o2 = container.exec_run(["cat", cwd_file], user=user)
    if c2 == 0:
        candidate = (o2 or b"").decode("utf-8", "replace").strip()
        if _CWD_RE.fullmatch(candidate):
            new_cwd = candidate

    return text, code in (124, 137), new_cwd


def _run_check_sync(container_id: str, script: str) -> bool:
    container = client.containers.get(container_id)
    code, _ = _exec_simple(container, script, user="root", timeout=10)
    return code == 0


def _read_file_from_container_sync(
    container_id: str, path: str, max_bytes: int = 1024 * 1024
) -> Optional[bytes]:
    """Reads a file from the container out-of-band via the Docker archive API in host memory."""
    try:
        container = client.containers.get(container_id)
        bits, _ = container.get_archive(path)
        buf = io.BytesIO()
        total = 0
        for chunk in bits:
            total += len(chunk)
            if total > max_bytes * 2:
                return None
            buf.write(chunk)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:*") as tar:
            for member in tar.getmembers():
                if member.isfile() and member.size <= max_bytes:
                    f = tar.extractfile(member)
                    if f is not None:
                        return f.read(max_bytes)
        return None
    except NotFound:
        return None
    except Exception:
        log.debug("Failed to read %s from container %s", path, container_id[:12], exc_info=True)
        return None


_KOTH_SANITIZE_SCRIPT = """
set +e
# 1. Remove sudo privileges for student and defender
rm -f /etc/sudoers.d/student /etc/sudoers.d/defender
sed -i '/^student\\b/d; /^defender\\b/d; /^attacker\\b/d' /etc/sudoers 2>/dev/null

# 2. Remove all cron jobs and stop cron daemon
rm -rf /var/spool/cron/crontabs/* /etc/cron.d/* /etc/cron.hourly/* /etc/cron.daily/* /etc/cron.weekly/* /etc/cron.monthly/* 2>/dev/null
> /etc/crontab 2>/dev/null
service cron stop 2>/dev/null || pkill -9 cron 2>/dev/null || true

# 3. Kill all processes started by student/defender/attacker or non-service background loops
pkill -9 -u student 2>/dev/null || true
pkill -9 -u defender 2>/dev/null || true
pkill -9 -u attacker 2>/dev/null || true
outer_pid=$(awk '/^PPid:/ {print $2}' /proc/$PPID/status 2>/dev/null || echo 0)
for p in /proc/[0-9]*; do
    pid=${p#/proc/}
    [ "$pid" = "1" ] && continue
    [ "$pid" = "$$" ] && continue
    [ "$pid" = "$PPID" ] && continue
    [ "$pid" = "$outer_pid" ] && continue
    ppid=$(awk '/^PPid:/ {print $2}' "$p/status" 2>/dev/null || echo 0)
    comm=$(cat "$p/comm" 2>/dev/null || true)
    [ "$ppid" = "1" ] && [ "$comm" = "sleep" ] && continue
    [ "$ppid" = "$$" ] && continue
    case "$comm" in
        nginx|apache2|postgres|docker-init) continue ;;
    esac
    kill -9 "$pid" 2>/dev/null || true
done

# 4. Clean /home/attacker and restore shell profiles if modified
find /home/attacker -mindepth 1 -delete 2>/dev/null || true
chown 1001:1001 /home/attacker 2>/dev/null || true
chmod 755 /home/attacker 2>/dev/null || true
rm -rf /etc/profile.d/*.sh 2>/dev/null || true
sed -i '/trap /d; /exit/d; /kill/d; /pkill/d; /alias /d' /etc/profile /etc/bash.bashrc 2>/dev/null || true

# 5. Ensure apache2/nginx is running if configured
if [ -f /etc/nginx/sites-enabled/portal ] || [ -f /etc/nginx/conf.d/portal.conf ] || pgrep -x nginx >/dev/null 2>&1; then
    service nginx start 2>/dev/null || nginx 2>/dev/null || true
elif [ -f /etc/apache2/sites-enabled/000-default.conf ] && pgrep -x apache2 >/dev/null 2>&1; then
    service apache2 start 2>/dev/null || true
fi
exit 0
"""


def _sanitize_koth_phase2_sync(container_id: str) -> bool:
    container = client.containers.get(container_id)
    code, _ = _exec_simple(container, _KOTH_SANITIZE_SCRIPT, user="root", timeout=15)
    return code == 0


def _list_sandbox_ids_sync() -> list[str]:
    return [c.id for c in client.containers.list(all=True, filters={"label": LABEL})]


def _disk_usage_sync(container_id: str) -> int:
    """Size of the container's writable layer in bytes (tmpfs is not counted)."""
    info = client.api.inspect_container(container_id, size=True)
    return int(info.get("SizeRw") or 0)


# --------------------------------------------------------------- async API

async def ensure_image() -> None:
    await asyncio.to_thread(_ensure_image_sync)


async def create_sandbox(setup_script: str, mem_limit: str | None = None,
                         pids_limit: int | None = None) -> str:
    return await asyncio.to_thread(_create_sync, setup_script, mem_limit, pids_limit)


async def destroy(container_id: str) -> None:
    await asyncio.to_thread(_destroy_sync, container_id)


async def run_command(container_id: str, cmd: str, cwd: str, user: str = USER):
    """Returns (output, timed_out, new_cwd). Raises NotFound if the container does not exist."""
    return await asyncio.to_thread(_run_command_sync, container_id, cmd, cwd, user)


async def run_check(container_id: str, script: str) -> bool:
    return await asyncio.to_thread(_run_check_sync, container_id, script)


async def read_file_from_container(container_id: str, path: str) -> Optional[bytes]:
    return await asyncio.to_thread(_read_file_from_container_sync, container_id, path)


async def sanitize_koth_phase2(container_id: str) -> bool:
    return await asyncio.to_thread(_sanitize_koth_phase2_sync, container_id)


async def list_sandbox_ids() -> list[str]:
    return await asyncio.to_thread(_list_sandbox_ids_sync)


async def disk_usage(container_id: str) -> int:
    return await asyncio.to_thread(_disk_usage_sync, container_id)
