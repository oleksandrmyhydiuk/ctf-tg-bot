# CTF/DevOps & Security Sandbox — Telegram Bot

An interactive Telegram bot built with `aiogram` 3 for solving hands-on Linux, DevOps, Database, and Cybersecurity challenges inside isolated Docker containers. Supports both solo mode (private chat) and four multiplayer group modes (`/race`, `/coop`, `/koth`, `/relay`).

## Quick Start (Local)

> [!WARNING]
> **Security Note:** Access to the Docker socket is effectively equivalent to `root` access on the host. Bot users only execute commands inside isolated sandbox containers, but compromising the bot itself compromises the host. For public deployments, run the bot on a dedicated VM.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set BOT_TOKEN from @BotFather

python main.py
```

The user running the bot must belong to the `docker` group (or have access to the Docker daemon).
On first startup, the bot automatically builds the `ctf-sandbox:3` image from `sandbox.Dockerfile` (requires internet access, takes 2–5 minutes, ~600 MB).

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | Yes | — | Telegram Bot API token from `@BotFather` |
| `DB_PATH` | No | `sandbox.db` | Path to SQLite database file (overridden to `/data/sandbox.db` in Docker Compose) |
| `DOCKER_RUNTIME` | No | — | Optional OCI runtime (e.g., `runsc` for gVisor) |
| `DOCKER_STORAGE_SIZE` | No | — | Hard container disk limit (only on Linux `overlay2` + `xfs` with `pquota`, e.g. `500m`) |
| `MAX_CONTAINERS` | No | `20` | Global limit on concurrent sandbox containers |
| `DOCKER_SOCK` | No | `/var/run/docker.sock` | Host Docker socket path for `docker compose` (useful for rootless Docker/Podman) |

## Running with Docker (x86_64 & ARM64)

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-arch bot image (`python:3.12-slim`) for both `amd64` and `arm64` |
| `sandbox.Dockerfile` | Sandbox image (`ubuntu:22.04` + nginx, apache2, PostgreSQL, sqlite3, security tools), built automatically by the bot |
| `docker-compose.amd64.yml` | Compose setup for `x86_64` (Intel/AMD) |
| `docker-compose.arm64.yml` | Compose setup for `ARM64` (Raspberry Pi 4/5 64-bit OS, Apple Silicon, AWS Graviton) |

```bash
cp .env.example .env   # set BOT_TOKEN

# x86_64
docker compose -f docker-compose.amd64.yml up -d --build
# ARM64
docker compose -f docker-compose.arm64.yml up -d --build

docker compose -f docker-compose.<amd64|arm64>.yml logs -f   # follow logs (first start builds sandbox image)
docker compose -f docker-compose.<amd64|arm64>.yml down      # stop bot (SQLite DB persists in bot-data volume)
```

Choose the Compose file matching your **host** architecture (`uname -m`: `x86_64` → `amd64`, `aarch64`/`arm64` → `arm64`) to avoid slow QEMU emulation.

To build the bot image manually (e.g., cross-building for Raspberry Pi):

```bash
docker buildx build --platform linux/arm64 -t ctf-sandbox-bot:arm64 --load .
docker buildx build --platform linux/amd64,linux/arm64 -t REGISTRY/ctf-sandbox-bot:latest --push .
```

## Project Structure

| Path | Purpose |
|---|---|
| `main.py` | Entry point: startup initialization, router registration, background task orchestration |
| `bot/constants.py` | Command regexes, mode titles, UI footers, default slugs |
| `bot/state.py` | FSM states (`Sandbox`), concurrency locks (`alloc_lock`, `locks`, `group_locks`), rate-limit store |
| `bot/formatting.py` | Terminal output escaping/truncation, step rendering, reward calculation, mention formatting |
| `bot/keyboards.py` | Inline keyboards and lobby/scoreboard renderers for solo and group modes |
| `bot/handlers/` | Modular `aiogram` routers (`common.py`, `solo.py`, `group_common.py`, `group_race.py`, `group_koth.py`, `terminal.py`) |
| `bot/services/` | Domain services (`sessions.py`, `koth.py`) and background workers (`workers.py`: TTL, disk watchdog, startup reconcile) |
| `docker_manager.py` | Container lifecycle, command execution, out-of-band file reads, KOTH sanitization (via `asyncio.to_thread`) |
| `db/` | Async SQLite layer split by domain (`core.py`, `users.py`, `tasks.py`, `sessions.py`, `groups.py`) |
| `tasks/` | Pool of 27 multi-step challenges grouped by category (`linux.py`, `web_db.py`, `security_privesc.py`, `security_forensics.py`, `security_network_crypto.py`, `group.py`) |
| `config.py` | Resource limits, timeouts, and environment configuration |

## Architecture & Security Controls

- **Container Isolation:** Unprivileged `student` user (with passwordless `sudo` inside the container where applicable), `network_disabled=True` (loopback only), `privileged=False`, `cap_drop=["ALL"]` with minimal `CAP_ADD`, default Docker seccomp/AppArmor profiles, and `tmpfs` mounts for writable directories (`/home/student`, `/home/attacker`, `/tmp`, `/var/tmp`).
- **Resource Limits & Watchdogs:** Per-container CPU, RAM (`128m` default, `256m–384m` for service tasks), PID limits (`64` default, `150` for service tasks), ulimits, 10s command timeout, output truncation & HTML escaping, per-user rate limiting, and a background `disk_watchdog` that terminates containers exceeding `MAX_DISK_BYTES`.
- **Concurrency & Recovery:** `UNIQUE(user_id)` constraint on active sessions, global `alloc_lock` for `MAX_CONTAINERS`, per-user and per-group `asyncio.Lock`s, and startup `reconcile()` to clean up orphaned `ctf_sandbox` containers and stale DB sessions.
- **Persistent Working Directory:** `cd` state is preserved across commands via `/dev/shm/.cwd_<user>`.

## Bot Commands

### Solo Mode (Private Chat / DM)
- `/start` — welcome message, score, and command overview
- `/tasks` — list available challenges with difficulty and completion status
- `/task` — show current step instructions
- `/check` — verify the current step
- `/hint` — get a hint for the current step (reduces reward by ~20% per step, capped at 50%)
- `/stop` — terminate the active session without points
- `/top` — view the global leaderboard

### Group Modes (Add the Bot to a Group)
- `/race [slug]` — **Speed Race:** each player gets their own isolated container in DM; first to pass the final `/check` wins (1.5x bonus).
- `/coop [slug]` — **Co-op:** shared container in the group chat; run commands using `$ <cmd>` or `! <cmd>`.
- `/koth [slug]` — **Attack-Defense (King of the Hill):** Phase 1 (5 min) defenders harden the system and plant decoy flags (`CTF{trap_...}`) while keeping SLA on port `8080`; Phase 2 (10 min) attackers (as unprivileged `attacker`) hunt for the real flag and submit via `/capture CTF{...}`.
- `/relay [slug]` — **Relay:** shared container where the same player cannot complete two consecutive steps (`/force_turn` overrides for solo testing).
- `/gtask`, `/gcheck`, `/ghint`, `/gstop`, `/ready` — manage active group sessions.

## Challenges (27 Multi-Step Scenarios)

| # | Slug | Difficulty | Steps | Category |
|---|---|---|---|---|
| 1 | `perms` | 🟢 Easy | 2 | Linux (`chmod`, executable scripts) |
| 2 | `needle` | 🟢 Easy | 2 | Linux (`grep`, `cut`, `wc`) |
| 3 | `hidden` | 🟢 Easy | 2 | Linux (hidden files, `find`, `tar`) |
| 4 | `users` | 🟢 Easy | 3 | Linux (`useradd`, `groupadd`, `setgid`) |
| 5 | `bash_script` | 🟡 Medium | 3 | Scripting (arguments, exit codes) |
| 6 | `sqlite_hr` | 🟡 Medium | 3 | Databases (SQLite `SELECT`/`UPDATE`, indexes) |
| 7 | `access_log` | 🟡 Medium | 3 | Linux (`awk`, `sort`, `uniq`) |
| 8 | `processes` | 🟡 Medium | 3 | Linux (`ps`, `kill`, `ss`, `sudo`) |
| 9 | `nginx_fix` | 🟡 Medium | 3 | Web servers (`nginx -t`, `location`, `add_header`) |
| 10 | `port_conflict` | 🟡 Medium | 2 | Web servers (nginx + Apache, `a2enmod`) |
| 11 | `postgres_shop` | 🔴 Hard | 3 | Databases (PostgreSQL roles, `GRANT`, `JOIN`, CSV) |
| 12 | `reverse_proxy` | 🔴 Hard | 2 | Web servers (`proxy_pass`, `error_page`) |
| 13 | `suid_privesc` | 🟡 Medium | 3 | Security / Privesc (SUID binary exploitation & remediation) |
| 14 | `sudo_path_hijack` | 🔴 Hard | 3 | Security / Privesc (`sudo` `PATH` hijacking & hardening) |
| 15 | `forensics_phantom` | 🔴 Hard | 3 | Security / Forensics (`/proc/<PID>/fd` deleted file recovery) |
| 16 | `siem_intrusion_log` | 🟡 Medium | 3 | Security / Log Analysis (SSH brute-force, Base64 webshell, backdoor user) |
| 17 | `persistence_backdoors` | 🔴 Hard | 3 | Security / Incident Response (systemd, cron, profile hooks, watchdog) |
| 18 | `network_pivot_waf` | 🔴 Hard | 3 | Security / Network (loopback discovery, DNS sinkhole, nginx WAF) |
| 19 | `secrets_in_env_git_mem` | 🔴 Hard | 3 | Security / Secrets & Forensics (`/proc/environ`, `.git` history, core dump) |
| 20 | `crypto_shadow_vault` | 🟡 Medium | 2 | Security / Cryptography (SHA-256 dictionary attack, OpenSSL AES-256-CBC) |
| 21 | `postgres_sec_audit` | 🔴 Hard | 3 | Security / Databases (rogue superuser, least privilege, `pg_hba.conf`) |
| 22 | `acl_and_special_bits` | 🟡 Medium | 3 | Security / Access Control (SGID, Sticky Bit, POSIX ACL `setfacl`) |
| 23 | `iptables_firewall_lockdown` | 🔴 Hard | 2 | Security / Network (`iptables` audit & port isolation) |
| 24 | `race_incident_patch` | 🟡 Medium | 3 | Group / Speed Race (`.env` leak, port conflict, nginx dotfile deny) |
| 25 | `coop_hydra_malware` | 🔴 Hard | 2 | Group / Co-op (dual-watchdog malware eradication) |
| 26 | `koth_leaky_portal` | 🔴 Hard | 3 | Group / Attack-Defense (intranet portal hardening & SLA) |
| 27 | `relay_crypto_heist` | 🟡 Medium | 3 | Group / Relay (multi-stage crypto forensics) |

## Adding a New Task

Add a dictionary entry to the appropriate category module in `tasks/` (e.g. `tasks/linux.py`, `tasks/web_db.py`, `tasks/security_*.py`, or `tasks/group.py`) with `slug`, `title`, `category`, `difficulty`, `reward_points`, `intro`, `setup_script`, and `steps` (`text`, `hint`, `check`). Check scripts run as `root` (or test user permissions explicitly) and exit `0` on success. Tasks are automatically synced to SQLite on bot startup by `slug`.

## Known Limitations

- Interactive TUI programs (`vim`, `top`, `less`) do not work because commands execute without a TTY.
- `aiogram` FSM uses `MemoryStorage`, though active container sessions are automatically recovered from SQLite after a bot restart.
- The global `MAX_CONTAINERS` check is soft under extreme concurrency across different users.
