"""Multiplayer / Group mode tasks (Speed Race, Co-op, Attack-Defense, Relay)."""

GROUP_TASKS = [
    {
        "slug": "race_incident_patch",
        "title": "Швидкісна гонка: Хотфікс під вогнем",
        "category": "Group / Speed Race",
        "difficulty": "medium",
        "reward_points": 40,
        "group_mode": "race",
        "mem_limit": "256m",
        "pids_limit": 150,
        "intro": (
            "🏎 <b>Швидкісна гонка (Speed Race):</b> На продакшн-сервері через помилку деплою одночасно "
            "впав <code>nginx</code>, витік секретний <code>.env</code> у публічний веб-корінь і завис процес, "
            "який блокує порт <code>8080</code>. Хто перший полагодить усі 3 проблеми?"
        ),
        "setup_script": r"""
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/app/.git
echo "DB_PASS=s3cr3t_prod_99" > /var/www/app/.env
echo "App Ready" > /var/www/app/index.html
echo "[core]" > /var/www/app/.git/config
chmod 644 /var/www/app/.env /var/www/app/index.html /var/www/app/.git/config

setsid nohup nc -lk 127.0.0.1 8080 >/dev/null 2>&1 </dev/null &
sleep 0.5

cat > /etc/nginx/sites-available/default <<'EOF'
server {
    listen 8080 default_server;
    server_name _;
    root /var/www/app;
    index index.html;
}
EOF
ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
""",
        "steps": [
            {
                "text": (
                    "Перемісти секретний файл <code>/var/www/app/.env</code> із публічного веб-кореня у "
                    "<code>/etc/app.env</code> і встанови на нього власника <code>root:root</code> та права <code>600</code>."
                ),
                "hint": "<code>sudo mv /var/www/app/.env /etc/app.env &amp;&amp; sudo chown root:root /etc/app.env &amp;&amp; sudo chmod 600 /etc/app.env</code>",
                "check": r"""
[ ! -e /var/www/app/.env ] && [ "$(stat -c '%a %U %G' /etc/app.env 2>/dev/null)" = "600 root root" ]
""",
            },
            {
                "text": (
                    "Звільни TCP-порт <code>8080</code> (заверши сторонній процес, який його утримує) і запусти "
                    "<code>nginx</code>, щоб <code>http://127.0.0.1:8080/</code> віддавав <code>App Ready</code>."
                ),
                "hint": "Подивись <code>sudo ss -ltnp | grep 8080</code>, вбий процес через <code>sudo kill -9 &lt;PID&gt;</code> і виконай <code>sudo service nginx start</code>.",
                "check": r"""
[ "$(curl -s --max-time 3 http://127.0.0.1:8080/)" = "App Ready" ]
""",
            },
            {
                "text": (
                    "Заблокуй у конфігу <code>/etc/nginx/sites-available/default</code> доступ до всіх прихованих файлів "
                    "і папок (що починаються з крапки, як-от <code>/.git/config</code>), щоб запит "
                    "<code>http://127.0.0.1:8080/.git/config</code> повертав <b>403</b>, а <code>/</code> — і далі <code>App Ready</code>."
                ),
                "hint": "Додай у блок <code>server</code> правило <code>location ~ /\\. { deny all; }</code> і виконай <code>sudo service nginx reload</code>.",
                "check": r"""
[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8080/.git/config)" = "403" ] \
  && [ "$(curl -s --max-time 3 http://127.0.0.1:8080/)" = "App Ready" ]
""",
            },
        ],
    },
    {
        "slug": "coop_hydra_malware",
        "title": "Co-op: Гідра — активна протидія малварі",
        "category": "Group / Co-op",
        "difficulty": "hard",
        "reward_points": 45,
        "group_mode": "coop",
        "intro": (
            "🤝 <b>Кооперативний режим (Один термінал на всіх):</b> У системі працюють два взаємно-пов'язані "
            "процеси-сторожі (<b>Hydra Watchdogs</b>): <code>alpha_guard.sh</code> та <code>beta_guard.sh</code>. "
            "Кожні 2 секунди вони перевіряють один одного і миттєво відновлюють напарника з прихованого "
            "каталогу-джерела, перезаписуючи <code>/var/www/html/status.txt</code> значенням <code>infected</code>!"
        ),
        "setup_script": r"""
mkdir -p /opt/hydra /var/lib/.hidden_seed /var/www/html
cat > /var/lib/.hidden_seed/alpha.sh <<'EOF'
#!/bin/bash
while true; do
  if ! pgrep -f 'beta_guard.sh' >/dev/null; then
    cp /var/lib/.hidden_seed/beta.sh /tmp/beta_guard.sh && chmod +x /tmp/beta_guard.sh
    setsid nohup /tmp/beta_guard.sh >/dev/null 2>&1 </dev/null &
  fi
  sleep 2
done
EOF
cat > /var/lib/.hidden_seed/beta.sh <<'EOF'
#!/bin/bash
while true; do
  if ! pgrep -f 'alpha_guard.sh' >/dev/null; then
    cp /var/lib/.hidden_seed/alpha.sh /var/tmp/alpha_guard.sh && chmod +x /var/tmp/alpha_guard.sh
    setsid nohup /var/tmp/alpha_guard.sh >/dev/null 2>&1 </dev/null &
  fi
  echo "infected" > /var/www/html/status.txt
  sleep 2
done
EOF
cp /var/lib/.hidden_seed/alpha.sh /var/tmp/alpha_guard.sh
cp /var/lib/.hidden_seed/beta.sh /tmp/beta_guard.sh
chmod +x /var/tmp/alpha_guard.sh /tmp/beta_guard.sh
setsid nohup /var/tmp/alpha_guard.sh >/dev/null 2>&1 </dev/null &
setsid nohup /tmp/beta_guard.sh >/dev/null 2>&1 </dev/null &
sleep 0.5
""",
        "steps": [
            {
                "text": (
                    "<b>Крок 1 (Розвідка):</b> Дослідіть запущені процеси <code>alpha_guard.sh</code> та "
                    "<code>beta_guard.sh</code>, знайдіть приховану директорію-джерело, з якої вони відновлюють "
                    "один одного, і запишіть її точний шлях у <code>/home/student/seed_path.txt</code>."
                ),
                "hint": "Прочитайте код скрипта: <code>cat /var/tmp/alpha_guard.sh</code>.",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/seed_path.txt)" = "/var/lib/.hidden_seed" ]
""",
            },
            {
                "text": (
                    "<b>Крок 2 (Ліквідація Гідри):</b> Видаліть директорію-джерело <code>/var/lib/.hidden_seed</code>, "
                    "одночасно вбийте обидва процеси (<code>alpha_guard.sh</code> та <code>beta_guard.sh</code>), "
                    "видаліть їхні скрипти в <code>/var/tmp</code> і <code>/tmp</code>, та запишіть слово "
                    "<code>clean</code> у <code>/var/www/html/status.txt</code>."
                ),
                "hint": (
                    "<code>sudo rm -rf /var/lib/.hidden_seed /var/tmp/alpha_guard.sh /tmp/beta_guard.sh "
                    "&amp;&amp; sudo pkill -9 -f 'alpha_guard|beta_guard' "
                    "&amp;&amp; echo clean | sudo tee /var/www/html/status.txt</code>"
                ),
                "check": r"""
! pgrep -f 'alpha_guard|beta_guard' >/dev/null || exit 1
[ ! -d /var/lib/.hidden_seed ] || exit 1
sleep 2
! pgrep -f 'alpha_guard|beta_guard' >/dev/null \
  && [ "$(tr -d '[:space:]' 2>/dev/null < /var/www/html/status.txt)" = "clean" ]
""",
            },
        ],
    },
    {
        "slug": "koth_leaky_portal",
        "title": "Фортеця (King of the Hill): Дірявий інтранет",
        "category": "Group / Attack-Defense",
        "difficulty": "hard",
        "reward_points": 50,
        "group_mode": "koth",
        "mem_limit": "256m",
        "pids_limit": 150,
        "intro": (
            "🏰 <b>Attack-Defense (King of the Hill):</b> На порту <code>8080</code> працює внутрішній портал "
            "(<code>/var/www/portal</code>), а прапор лежить у <code>/var/www/flag.txt</code>.\n"
            "• У режимі <b>/koth</b>: Фаза 1 (5 хв) — Захисники закривають діри та ставлять пастки "
            "<code>CTF{trap_...}</code>, зберігаючи SLA порталу на порту <code>8080</code>; "
            "Фаза 2 (10 хв) — Атакуючі (від непривілейованого <code>attacker</code>) шукають прапор і здають "
            "його через <code>/capture CTF{...}</code>.\n"
            "• У покроковому режимі: виконай повний цикл захисту порталу з 3 кроків."
        ),
        "setup_script": r"""
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/portal
echo "CTF{koth_default_portal_flag_901}" > /var/www/flag.txt
chown www-data:www-data /var/www/flag.txt
chmod 0644 /var/www/flag.txt

# Example decoy flag (honeypot) for defenders
echo "CTF{trap_honeypot_decoy_001}" > /var/www/portal/flag_backup_decoy.txt
chown www-data:www-data /var/www/portal/flag_backup_decoy.txt
chmod 0644 /var/www/portal/flag_backup_decoy.txt

# Vulnerability 1: forgotten config backup in web root
cat > /var/www/portal/config.bak <<'EOF'
# Legacy intranet configuration backup
PORTAL_MODE=debug
FLAG_STORAGE=/var/www/flag.txt
SUID_HELPER=/usr/local/bin/status_check
EOF
chown www-data:www-data /var/www/portal/config.bak
chmod 0644 /var/www/portal/config.bak

# Vulnerability 2: world-writable diagnostic script
cat > /var/www/portal/view.sh <<'EOF'
#!/bin/bash
# Diagnostic view helper
cat "/var/www/portal/${1:-index.html}"
EOF
chown www-data:www-data /var/www/portal/view.sh
chmod 0777 /var/www/portal/view.sh

# Vulnerability 3: SUID/SGID binary owned by www-data (allows reading www-data files)
cp /usr/bin/find /usr/local/bin/status_check
chown www-data:www-data /usr/local/bin/status_check
chmod 6755 /usr/local/bin/status_check

cat > /var/www/portal/index.html <<'EOF'
Intranet Portal v2.4 - SLA OK
EOF
chown -R www-data:www-data /var/www/portal

cat > /etc/nginx/sites-available/portal <<'CONF'
server {
    listen 8080 default_server;
    server_name _;
    root /var/www/portal;
    index index.html;

    location = /health {
        return 200 "SLA_OK";
    }
}
CONF
ln -sf /etc/nginx/sites-available/portal /etc/nginx/sites-enabled/portal
service nginx start
""",
        "steps": [
            {
                "text": (
                    "<b>Крок 1 (Захист прапора з дотриманням SLA):</b> Закрий публічний доступ на читання "
                    "(для <code>others</code>) до файлу <code>/var/www/flag.txt</code>, встановивши права "
                    "<code>0640</code> або <code>0600</code> (власник має залишитися <code>www-data:www-data</code>), "
                    "при цьому портал на <code>http://127.0.0.1:8080/</code> має залишатися доступним."
                ),
                "hint": "<code>sudo chown www-data:www-data /var/www/flag.txt &amp;&amp; sudo chmod 0600 /var/www/flag.txt</code>",
                "check": r"""
[ "$(stat -c '%U:%G' /var/www/flag.txt 2>/dev/null)" = "www-data:www-data" ] \
  && [ $(( 0$(stat -c '%a' /var/www/flag.txt 2>/dev/null) & 7 )) -eq 0 ] \
  && runuser -u www-data -- test -r /var/www/flag.txt \
  && curl -s --max-time 3 http://127.0.0.1:8080/ | grep -q 'Intranet Portal'
""",
            },
            {
                "text": (
                    "<b>Крок 2 (Зачистка витоків у веб-корені):</b> Видали забутий бекап "
                    "<code>/var/www/portal/config.bak</code> та прибери права запису й доступу для сторонніх "
                    "(<code>others</code>) зі скрипта <code>/var/www/portal/view.sh</code> (встанови права <code>0750</code>)."
                ),
                "hint": "<code>sudo rm -f /var/www/portal/config.bak &amp;&amp; sudo chmod 0750 /var/www/portal/view.sh</code>",
                "check": r"""
[ ! -e /var/www/portal/config.bak ] \
  && [ "$(stat -c '%a' /var/www/portal/view.sh 2>/dev/null)" = "750" ]
""",
            },
            {
                "text": (
                    "<b>Крок 3 (Ліквідація SUID/SGID вектора):</b> Зніми спеціальні біти SUID та SGID із бінарника "
                    "<code>/usr/local/bin/status_check</code> (встанови права <code>0755</code>), щоб непривілейований "
                    "атакуючий не міг прочитати <code>/var/www/flag.txt</code> від імені <code>www-data</code>."
                ),
                "hint": "<code>sudo chmod 0755 /usr/local/bin/status_check</code>",
                "check": r"""
[ "$(stat -c '%a' /usr/local/bin/status_check 2>/dev/null)" = "755" ] \
  && curl -s --max-time 3 http://127.0.0.1:8080/ | grep -q 'Intranet Portal'
""",
            },
        ],
    },
    {
        "slug": "relay_crypto_heist",
        "title": "Естафета: Лабораторія крипто-форензики",
        "category": "Group / Relay",
        "difficulty": "medium",
        "reward_points": 45,
        "group_mode": "relay",
        "intro": (
            "🏃‍♂️ <b>Режим Естафети (Relay):</b> Кожен наступний крок у груповому режимі <code>/relay</code> "
            "має виконувати <b>інший учасник</b> групи! Передавайте знайдені артефакти через спільну "
            "директорію <code>/srv/relay</code>."
        ),
        "setup_script": r"""
mkdir -p /srv/relay /var/backups/.deep/vault
chmod 1777 /srv/relay
echo "CTF{teamwork_makes_the_dream_work_77}" > /tmp/flag.plain
openssl enc -aes-256-cbc -pbkdf2 -salt -in /tmp/flag.plain -out /var/backups/.deep/vault/secret.enc -pass pass:bruised_orange_42
rm -f /tmp/flag.plain
chmod 644 /var/backups/.deep/vault/secret.enc
echo "2026-10-10 12:01:04 AUTH_TRACE KEY_PART1=bruised_" > /var/log/auth_trace.log
chmod 644 /var/log/auth_trace.log
sqlite3 /var/lib/tokens.db "CREATE TABLE parts(id INT, val TEXT); INSERT INTO parts VALUES (1,'fake_'),(2,'orange_42');"
chmod 644 /var/lib/tokens.db
""",
        "steps": [
            {
                "text": (
                    "<b>Етап 1 (Слідопит):</b> Знайди у файловій системі зашифрований файл <code>secret.enc</code> "
                    "і скопіюй його в <code>/srv/relay/secret.enc</code>. Також знайди в "
                    "<code>/var/log/auth_trace.log</code> першу частину ключа (після <code>KEY_PART1=</code>) "
                    "і запиши її в <code>/srv/relay/part1.txt</code>."
                ),
                "hint": "<code>find / -name secret.enc 2&gt;/dev/null</code> та <code>grep KEY_PART1 /var/log/auth_trace.log</code>",
                "check": r"""
[ -f /srv/relay/secret.enc ] \
  && cmp -s /srv/relay/secret.enc /var/backups/.deep/vault/secret.enc \
  && [ "$(tr -d '[:space:]' 2>/dev/null < /srv/relay/part1.txt)" = "bruised_" ]
""",
            },
            {
                "text": (
                    "<b>Етап 2 (Дата-аналітик — виконує наступний гравець!):</b> У SQLite-базі "
                    "<code>/var/lib/tokens.db</code> у таблиці <code>parts</code> візьми значення з <code>id=2</code>, "
                    "з'єднай його з вмістом <code>/srv/relay/part1.txt</code> і запиши повний пароль у "
                    "<code>/srv/relay/full_pass.txt</code>."
                ),
                "hint": "<code>sqlite3 /var/lib/tokens.db 'SELECT val FROM parts WHERE id=2;'</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /srv/relay/full_pass.txt)" = "bruised_orange_42" ]
""",
            },
            {
                "text": (
                    "<b>Етап 3 (Криптограф — виконує наступний гравець!):</b> Розшифруй "
                    "<code>/srv/relay/secret.enc</code> алгоритмом <code>aes-256-cbc</code> з <code>-pbkdf2</code> "
                    "та паролем із <code>/srv/relay/full_pass.txt</code>. Запиши розшифрований прапор у "
                    "<code>/srv/relay/flag.txt</code>."
                ),
                "hint": "<code>openssl enc -d -aes-256-cbc -pbkdf2 -in /srv/relay/secret.enc -out /srv/relay/flag.txt -pass file:/srv/relay/full_pass.txt</code>",
                "check": r"""
grep -qx 'CTF{teamwork_makes_the_dream_work_77}' /srv/relay/flag.txt
""",
            },
        ],
    },
]
