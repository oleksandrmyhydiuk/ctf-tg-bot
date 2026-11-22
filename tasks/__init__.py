"""Task pool (multi-step scenarios).

Task format:
  slug, title, category, difficulty (easy|medium|hard), reward_points,
  intro        — HTML description of the scenario,
  setup_script — bash run as root (prepares environment, may start services),
  mem_limit / pids_limit — optional container resource limit overrides,
  steps        — list of steps: {text (HTML), hint (HTML), check (bash, exit 0 = pass)}.

User commands run as `student` (home: /home/student) with passwordless sudo.
Check scripts run as `root` (and verify unprivileged access explicitly where needed).
In HTML texts, < > & characters must be escaped (&lt; &gt; &amp;).
"""

from tasks.group import GROUP_TASKS
from tasks.linux import LINUX_TASKS
from tasks.security_forensics import SECURITY_FORENSICS_TASKS
from tasks.security_network_crypto import SECURITY_NETWORK_CRYPTO_TASKS
from tasks.security_privesc import SECURITY_PRIVESC_TASKS
from tasks.web_db import WEB_DB_TASKS

_ALL_BY_SLUG = {
    t["slug"]: t
    for t in (
        LINUX_TASKS
        + WEB_DB_TASKS
        + SECURITY_PRIVESC_TASKS
        + SECURITY_FORENSICS_TASKS
        + SECURITY_NETWORK_CRYPTO_TASKS
        + GROUP_TASKS
    )
}

_TASK_ORDER = [
    "perms",
    "needle",
    "hidden",
    "users",
    "bash_script",
    "sqlite_hr",
    "access_log",
    "processes",
    "nginx_fix",
    "port_conflict",
    "postgres_shop",
    "reverse_proxy",
    "suid_privesc",
    "sudo_path_hijack",
    "forensics_phantom",
    "siem_intrusion_log",
    "persistence_backdoors",
    "network_pivot_waf",
    "secrets_in_env_git_mem",
    "crypto_shadow_vault",
    "postgres_sec_audit",
    "acl_and_special_bits",
    "iptables_firewall_lockdown",
    "race_incident_patch",
    "coop_hydra_malware",
    "koth_leaky_portal",
    "relay_crypto_heist",
]

# Preserve exact canonical order while also picking up any newly added tasks automatically.
TASKS = [_ALL_BY_SLUG[slug] for slug in _TASK_ORDER if slug in _ALL_BY_SLUG] + [
    t for slug, t in _ALL_BY_SLUG.items() if slug not in _TASK_ORDER
]
