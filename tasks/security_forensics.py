"""Security: Forensics, Log Analysis, Incident Response & Secrets tasks."""

SECURITY_FORENSICS_TASKS = [
    {
        "slug": "forensics_phantom",
        "title": "Інцидент-форензика: фантомний процес і видалені файли",
        "category": "Security / Forensics",
        "difficulty": "hard",
        "reward_points": 45,
        "intro": (
            "Зловмисник запустив у системі шкідливий процес, який маскується під потік ядра Linux "
            "(<code>[kworker/u8:3-events]</code>), відкрив файл із ключем ексфільтрації і одразу "
            "<b>видалив (unlinked)</b> і сам файл ключа, і свій бінарник із диска! "
            "Увага: якщо ти вб'єш процес до того, як витягнеш дані з <code>/proc</code>, ключ буде втрачено назавжди."
        ),
        "setup_script": r"""
mkdir -p /var/tmp/.X11-unix
cat > /var/tmp/.X11-unix/phantom_runner.sh <<'EOS'
#!/bin/bash
echo "CTF{proc_fd_recovery_before_kill_509}" > /tmp/.exfil_key.dat
exec 7</tmp/.exfil_key.dat
rm -f /tmp/.exfil_key.dat
rm -f /var/tmp/.X11-unix/phantom_runner.sh
exec -a "[kworker/u8:3-events]" sleep 36000
EOS
chmod +x /var/tmp/.X11-unix/phantom_runner.sh
setsid /var/tmp/.X11-unix/phantom_runner.sh >/dev/null 2>&1 </dev/null &
sleep 0.5
""",
        "steps": [
            {
                "text": (
                    "Знайди PID підозрілого процесу, який маскується під <code>[kworker/u8:3-events]</code>, "
                    "але насправді є звичайним процесом у просторі користувача, і запиши його PID у <code>~/phantom_pid.txt</code>."
                ),
                "hint": "Перевір <code>ps aux | grep kworker</code> або переглянь <code>sudo ls -l /proc/*/fd/ 2&gt;/dev/null | grep deleted</code>.",
                "check": r"""
pid=$(tr -d '[:space:]' 2>/dev/null < /home/student/phantom_pid.txt)
case "$pid" in ''|*[!0-9]*) exit 1;; esac
grep -q 'kworker/u8:3-events' /proc/$pid/cmdline 2>/dev/null
""",
            },
            {
                "text": (
                    "<b>Не завершуючи процес</b>, віднови вміст видаленого файлу <code>/tmp/.exfil_key.dat (deleted)</code> "
                    "через відкриті файлові дескриптори процесу в <code>/proc/&lt;PID&gt;/fd/</code> і запиши прапор у "
                    "<code>~/recovered_key.txt</code>."
                ),
                "hint": (
                    "Подивись <code>sudo ls -l /proc/&lt;PID&gt;/fd</code>, знайди номер дескриптора, що вказує на "
                    "<code>/tmp/.exfil_key.dat (deleted)</code>, і прочитай його через <code>sudo cat /proc/&lt;PID&gt;/fd/7</code>."
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/recovered_key.txt)" = "CTF{proc_fd_recovery_before_kill_509}" ]
""",
            },
            {
                "text": (
                    "Тепер ліквідуй загрозу: заверши фантомний процес та видали прихований каталог дроппера "
                    "<code>/var/tmp/.X11-unix</code>."
                ),
                "hint": "<code>sudo kill -9 &lt;PID&gt; &amp;&amp; sudo rm -rf /var/tmp/.X11-unix</code>",
                "check": r"""
! pgrep -f 'kworker/u8:3-events' >/dev/null && [ ! -d /var/tmp/.X11-unix ]
""",
            },
        ],
    },
    {
        "slug": "siem_intrusion_log",
        "title": "Розслідування злому: SSH Brute-force, Webshell та Backdoor-юзер",
        "category": "Security / Log Analysis",
        "difficulty": "medium",
        "reward_points": 35,
        "intro": (
            "Сервер пережив комплексну атаку. У тебе є системний журнал авторизації "
            "<code>/var/log/auth.log</code> та журнал веб-сервера <code>/var/log/nginx/intrusion.log</code>. "
            "Відтвори ланцюжок атаки (Kill Chain) та очисти систему від бекдору."
        ),
        "setup_script": r"""
mkdir -p /var/log/nginx
awk 'BEGIN{
  ips[1]="185.220.101.44"; ips[2]="45.155.205.99"; ips[3]="198.51.100.17";
  for (i=1; i<=120; i++) {
    ip = ips[(i%3)+1];
    printf "Nov 17 14:01:%02d sandbox sshd[%d]: Failed password for invalid user admin from %s port %d ssh2\n", i%60, 2000+i, ip, 40000+i;
  }
  for (i=1; i<=45; i++) {
    printf "Nov 17 14:03:%02d sandbox sshd[%d]: Failed password for deploy from 91.240.118.222 port %d ssh2\n", i%60, 3000+i, 50000+i;
  }
  print "Nov 17 14:04:12 sandbox sshd[3099]: Accepted password for deploy from 91.240.118.222 port 51234 ssh2";
  print "Nov 17 14:04:45 sandbox sudo:   deploy : TTY=pts/0 ; PWD=/home/deploy ; USER=root ; COMMAND=/usr/sbin/useradd -M -s /bin/bash sysmaint_bkd";
}' > /var/log/auth.log
chmod 644 /var/log/auth.log

useradd -M -s /bin/bash sysmaint_bkd

b64_ok=$(printf "echo CTF{log_forensics_webshell_decoded_88}" | base64 -w0)
b64_noise=$(printf "whoami; id; uname -a" | base64 -w0)
cat > /var/log/nginx/intrusion.log <<EOF
10.10.1.5 - - [17/Nov/2026:14:00:01 +0000] "GET /index.php?id=1%27%20OR%201=1-- HTTP/1.1" 403 152
91.240.118.222 - - [17/Nov/2026:14:05:10 +0000] "GET /assets/.cache.php?cmd=${b64_noise} HTTP/1.1" 404 0
91.240.118.222 - - [17/Nov/2026:14:05:22 +0000] "GET /uploads/.shell.php?cmd=${b64_ok} HTTP/1.1" 200 48
10.10.1.8 - - [17/Nov/2026:14:06:00 +0000] "GET /health HTTP/1.1" 200 2
EOF
chmod 644 /var/log/nginx/intrusion.log
""",
        "steps": [
            {
                "text": (
                    "Проаналізуй <code>/var/log/auth.log</code>: знайди IP-адресу зловмисника, який після серії "
                    "невдалих спроб (<code>Failed password</code>) успішно увійшов у систему (<code>Accepted password</code>). "
                    "Запиши цей IP у <code>~/attacker_ip.txt</code>."
                ),
                "hint": "<code>grep 'Accepted password' /var/log/auth.log</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/attacker_ip.txt)" = "91.240.118.222" ]
""",
            },
            {
                "text": (
                    "У <code>/var/log/nginx/intrusion.log</code> знайди успішний запит (статус <b>200</b>) до "
                    "веб-шелла з параметром <code>cmd=</code> (закодованим у Base64). Розкодуй значення <code>cmd</code> "
                    "і запиши прапор <code>CTF{...}</code> у <code>~/webshell_flag.txt</code>."
                ),
                "hint": (
                    "Знайди рядок зі статусом 200 і <code>cmd=</code>, виріж Base64-рядок і прожени через "
                    "<code>base64 -d</code>."
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/webshell_flag.txt)" = "CTF{log_forensics_webshell_decoded_88}" ]
""",
            },
            {
                "text": (
                    "У <code>/var/log/auth.log</code> зафіксовано, якого бекдор-користувача створив зловмисник через "
                    "<code>sudo useradd</code>. Знайди його ім'я та <b>видали цього користувача</b> з системи."
                ),
                "hint": "Подивись кінець <code>/var/log/auth.log</code> і виконай <code>sudo userdel &lt;ім'я&gt;</code>.",
                "check": r"""
! getent passwd sysmaint_bkd >/dev/null
""",
            },
        ],
    },
    {
        "slug": "persistence_backdoors",
        "title": "Полювання на Persistence: Cron, Systemd та Respawn-демон",
        "category": "Security / Incident Response",
        "difficulty": "hard",
        "reward_points": 45,
        "intro": (
            "Атакувальник закріпився в системі (Persistence) одразу в трьох місцях: через маскований unit-файл "
            "<code>systemd</code>, завдання <code>cron</code> і фоновий сторожовий процес (watchdog), який кожні "
            "2 секунди перезапускає мережевий бекдор на TCP-порту <code>4444</code>. Якщо просто вбити <code>nc</code>, "
            "він одразу воскресне!"
        ),
        "setup_script": r"""
mkdir -p /etc/systemd/system /usr/local/lib/.sysd
cat > /etc/systemd/system/systemd-journald-sync.service <<'EOF'
[Unit]
Description=Systemd Journal Synchronization Helper
After=network.target

[Service]
Type=simple
Environment="BACKDOOR_KEY=CTF{persistence_rooted_out_303}"
ExecStart=/usr/local/lib/.sysd/journal-syncd --stealth
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat > /usr/local/lib/.sysd/journal-syncd <<'EOF'
#!/bin/bash
while true; do
  if ! ss -ltn | grep -q ':4444 '; then
    setsid nohup nc -lk 127.0.0.1 4444 >/dev/null 2>&1 </dev/null &
  fi
  sleep 1.5
done
EOF
chmod +x /usr/local/lib/.sysd/journal-syncd

cat > /etc/cron.d/sys-journal-sync <<'EOF'
* * * * * root /usr/local/lib/.sysd/journal-syncd >/dev/null 2>&1
EOF
chmod 644 /etc/cron.d/sys-journal-sync

cat > /etc/profile.d/99-sys-check.sh <<'EOF'
# stealth persistence trigger
(/usr/local/lib/.sysd/journal-syncd >/dev/null 2>&1 &) 2>/dev/null
EOF

setsid /usr/local/lib/.sysd/journal-syncd >/dev/null 2>&1 </dev/null &
sleep 1
""",
        "steps": [
            {
                "text": (
                    "Досліди <code>/etc/systemd/system/</code> на наявність підозрілих сервісів. "
                    "Знайди прапор у змінній оточення <code>BACKDOOR_KEY</code> та збережи його в <code>~/flag.txt</code>."
                ),
                "hint": "<code>grep -rn 'CTF{' /etc/systemd/system/</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/flag.txt)" = "CTF{persistence_rooted_out_303}" ]
""",
            },
            {
                "text": (
                    "Видали всі файли закріплення зловмисника: фейковий unit-файл "
                    "<code>/etc/systemd/system/systemd-journald-sync.service</code>, cron-завдання "
                    "<code>/etc/cron.d/sys-journal-sync</code>, хук профілю <code>/etc/profile.d/99-sys-check.sh</code> "
                    "та виконуваний скрипт <code>/usr/local/lib/.sysd/journal-syncd</code>."
                ),
                "hint": "Використай <code>sudo rm -f ...</code> для кожного з чотирьох файлів.",
                "check": r"""
[ ! -e /etc/systemd/system/systemd-journald-sync.service ] \
  && [ ! -e /etc/cron.d/sys-journal-sync ] \
  && [ ! -e /etc/profile.d/99-sys-check.sh ] \
  && [ ! -e /usr/local/lib/.sysd/journal-syncd ]
""",
            },
            {
                "text": (
                    "Тепер заверши сторожовий процес (<code>journal-syncd</code>) та бекдор-слухач <code>nc</code> "
                    "на порту <code>4444</code>. Перевірка зачекає 2 секунди, щоб переконатися, що порт <code>4444</code> "
                    "більше не відкривається знову!"
                ),
                "hint": (
                    "Спочатку вбий сторожа: <code>sudo pkill -9 -f journal-syncd</code>, а потім "
                    "<code>sudo pkill -9 -f '4444'</code>. Перевір через <code>ss -ltn</code>."
                ),
                "check": r"""
! pgrep -f 'journal-syncd' >/dev/null || exit 1
! ss -ltn | grep -q ':4444 ' || exit 1
sleep 2
! ss -ltn | grep -q ':4444 ' && ! pgrep -f 'journal-syncd' >/dev/null
""",
            },
        ],
    },
    {
        "slug": "secrets_in_env_git_mem",
        "title": "Полювання на секрети: оточення процесу, .git та дамп пам'яті",
        "category": "Security / Secrets & Forensics",
        "difficulty": "hard",
        "reward_points": 45,
        "intro": (
            "Розробники випадково допустили витік трьох частин майстер-ключа <code>CTF{...}</code>: "
            "перша частина передана у змінні оточення запущеного воркера, друга залишилася в історії "
            "комітів репозиторію <code>/srv/webapp</code> після видалення файлу <code>.env</code>, "
            "а третя осіла в бінарному core-дампі пам'яті <code>/var/crash/authd.core</code>."
        ),
        "setup_script": r"""
# Part 1: process with secret in environ
cat > /usr/local/bin/auth-worker <<'EOS'
#!/bin/bash
exec sleep 36000
EOS
chmod +x /usr/local/bin/auth-worker
setsid env SECRET_PART1="CTF{trifecta_env_" /usr/local/bin/auth-worker >/dev/null 2>&1 </dev/null &

# Part 2: .git repository (compatible with both git CLI and basic grep/zcat without git)
mkdir -p /srv/webapp/.git/logs/refs/heads /srv/webapp/.git/objects/info
cat > /srv/webapp/app.py <<'EOF'
print("Webapp v1.2 - secrets removed from .env")
EOF
cat > /srv/webapp/.git/COMMIT_EDITMSG <<'EOF'
Hotfix: remove leaked SECRET_PART2=git_history_ from repository
EOF
cat > /srv/webapp/.git/logs/HEAD <<'EOF'
0000000000000000000000000000000000000000 a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4 Dev <dev@local> 1700000000 +0000	commit (initial): Add initial .env with SECRET_PART2=git_history_
a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4 f1e2d3c4b5a69788695a4b3c2d1e0f9a8b7c6d5e Dev <dev@local> 1700000600 +0000	commit: Delete .env
EOF
chmod -R a+rX /srv/webapp

# Part 3: binary memory dump with random bytes surrounding the secret
mkdir -p /var/crash
dd if=/dev/urandom bs=1024 count=32 2>/dev/null > /var/crash/authd.core
printf '\x00\x00MEMDUMP_STRUCT_START\x00SECRET_PART3=and_coredump_99}\x00MEMDUMP_END\x00' >> /var/crash/authd.core
dd if=/dev/urandom bs=1024 count=32 2>/dev/null >> /var/crash/authd.core
chmod 644 /var/crash/authd.core
""",
        "steps": [
            {
                "text": (
                    "Знайди запущений процес <code>auth-worker</code>, витягни значення змінної "
                    "<code>SECRET_PART1</code> з його оточення в <code>/proc/&lt;PID&gt;/environ</code> і "
                    "запиши у <code>~/part1.txt</code>."
                ),
                "hint": (
                    "Знайди PID через <code>pgrep -f auth-worker</code>, потім прочитай: "
                    "<code>sudo tr '\\0' '\\n' &lt; /proc/&lt;PID&gt;/environ | grep SECRET_PART1</code>"
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/part1.txt)" = "CTF{trifecta_env_" ]
""",
            },
            {
                "text": (
                    "Досліди приховану директорію <code>/srv/webapp/.git</code>, знайди видалену другу частину "
                    "ключа (<code>SECRET_PART2</code>, без назви змінної) і запиши її в <code>~/part2.txt</code>."
                ),
                "hint": "Пошукай рекурсивно у <code>/srv/webapp/.git</code>: <code>grep -rn 'SECRET_PART2' /srv/webapp/.git/</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/part2.txt)" = "git_history_" ]
""",
            },
            {
                "text": (
                    "Витягни третю частину (<code>SECRET_PART3</code>) із бінарного дампу пам'яті "
                    "<code>/var/crash/authd.core</code>, збери всі три частини разом у єдиний прапор "
                    "<code>CTF{...}</code> у файлі <code>~/master_flag.txt</code> та видали дамп <code>/var/crash/authd.core</code>."
                ),
                "hint": (
                    "Для пошуку тексту в бінарному файлі використай <code>grep -ao 'SECRET_PART3=[^[:cntrl:]]*' /var/crash/authd.core</code> "
                    "(або <code>strings</code>), об'єднай усі 3 частини і видали дамп через <code>sudo rm -f /var/crash/authd.core</code>."
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/master_flag.txt)" = "CTF{trifecta_env_git_history_and_coredump_99}" ] \
  && [ ! -e /var/crash/authd.core ]
""",
            },
        ],
    },
]
