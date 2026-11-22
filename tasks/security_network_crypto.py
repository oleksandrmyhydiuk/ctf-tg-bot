"""Security: Network, Cryptography & Database Security tasks."""

SECURITY_NETWORK_CRYPTO_TASKS = [
    {
        "slug": "network_pivot_waf",
        "title": "Мережева безпека: таємний loopback-сервіс, DNS-сінкхол та WAF",
        "category": "Security / Network",
        "difficulty": "hard",
        "reward_points": 45,
        "mem_limit": "256m",
        "pids_limit": 150,
        "intro": (
            "Усередині мережевого стека контейнера (<code>127.0.0.0/8</code>) на нестандартній ІР-адресі піднято "
            "прихований адміністративний веб-сервіс. Крім того, шкідливий скрипт намагається стукати на домен "
            "<code>c2.shadownet.local</code>, а публічний <code>nginx</code> на порту 80 пропускає SQL-ін'єкції."
        ),
        "setup_script": r"""
echo "127.0.99.42 c2.shadownet.local" >> /etc/hosts

echo "Listen 127.0.42.77:8888" > /etc/apache2/ports.conf
cat > /etc/apache2/sites-available/000-default.conf <<'CONF'
<VirtualHost 127.0.42.77:8888>
    DocumentRoot /var/www/internal_api
    <Directory /var/www/internal_api>
        Require all granted
    </Directory>
</VirtualHost>
CONF
mkdir -p /var/www/internal_api
echo "CTF{internal_loopback_discovery_612}" > /var/www/internal_api/token.txt
service apache2 start

mkdir -p /var/www/public
echo "Public Portal OK" > /var/www/public/index.html
echo "SECRET_ADMIN_PANEL" > /var/www/public/admin.html
cat > /etc/nginx/sites-available/default <<'CONF'
# Note: legacy upstream was http://127.0.42.77:8888/token.txt
server {
    listen 80 default_server;
    server_name _;
    root /var/www/public;
    index index.html;
}
CONF
service nginx start
""",
        "steps": [
            {
                "text": (
                    "Вияви прихований локальний IP та порт, на якому слухає внутрішній HTTP-сервер (<code>apache2</code>), "
                    "звернися до ендпоінта <code>/token.txt</code> на ньому і збережи отриманий прапор у <code>~/net_flag.txt</code>."
                ),
                "hint": (
                    "Подивись усі відкриті сокети: <code>sudo ss -ltnp</code>, а також коментарі в "
                    "<code>/etc/nginx/sites-available/default</code>. Запит: <code>curl http://127.0.42.77:8888/token.txt</code>."
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/net_flag.txt)" = "CTF{internal_loopback_discovery_612}" ]
""",
            },
            {
                "text": (
                    "Зроби DNS-сінкхол (sinkhole) для шкідливого домену <code>c2.shadownet.local</code> у файлі "
                    "<code>/etc/hosts</code>: перенаправ його на адресу <code>0.0.0.0</code> замість <code>127.0.99.42</code>."
                ),
                "hint": "<code>sudo sed -i 's/127.0.99.42/0.0.0.0/' /etc/hosts</code>",
                "check": r"""
[ "$(getent hosts c2.shadownet.local | awk '{print $1}')" = "0.0.0.0" ]
""",
            },
            {
                "text": (
                    "Налаштуй базовий WAF у <code>/etc/nginx/sites-available/default</code> (порт 80): "
                    "1) закрий доступ до <code>/admin.html</code> кодом <b>403</b>; "
                    "2) блокуй запити, у яких заголовок <code>User-Agent</code> містить <code>sqlmap</code> (код <b>403</b>); "
                    "3) звичайні запити до <code>/</code> мають і далі повертати <b>200</b> («Public Portal OK»)."
                ),
                "hint": (
                    "Усередині <code>server { ... }</code> додай:\n"
                    "<code>if ($http_user_agent ~* \"sqlmap\") { return 403; }</code>\n"
                    "<code>location = /admin.html { return 403; }</code>\n"
                    "Потім <code>sudo nginx -t &amp;&amp; sudo service nginx reload</code>."
                ),
                "check": r"""
[ "$(curl -s --max-time 3 http://127.0.0.1/)" = "Public Portal OK" ] || exit 1
[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1/admin.html)" = "403" ] || exit 1
[ "$(curl -s -A 'sqlmap/1.7' -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1/)" = "403" ]
""",
            },
        ],
    },
    {
        "slug": "crypto_shadow_vault",
        "title": "Криптографія та аудит паролів: OpenSSL, хеші та словникова атака",
        "category": "Security / Cryptography",
        "difficulty": "medium",
        "reward_points": 35,
        "intro": (
            "У каталозі <code>/srv/vault</code> лежить зашифрований архів секретів <code>flag.txt.enc</code> "
            "(алгоритм <b>AES-256-CBC</b> з <code>-pbkdf2</code>). Пароль від нього адміністратор необачно "
            "зберіг у вигляді SHA-256 хешу разом із підказкою, що це одне зі стандартних слів зі словника "
            "<code>/srv/vault/wordlist.txt</code>."
        ),
        "setup_script": r"""
mkdir -p /srv/vault
cat > /srv/vault/wordlist.txt <<'EOF'
qwerty123
admin2026
winter_mute
cyber_sentinel_42
shadow_hunter
letmein99
root_access
EOF

printf "cyber_sentinel_42" | sha256sum | awk '{print $1}' > /srv/vault/pass.sha256
echo "CTF{openssl_aes256_cracked_and_decrypted}" | openssl enc -aes-256-cbc -pbkdf2 -salt -pass pass:cyber_sentinel_42 -out /srv/vault/flag.txt.enc
chmod 644 /srv/vault/wordlist.txt /srv/vault/pass.sha256 /srv/vault/flag.txt.enc
""",
        "steps": [
            {
                "text": (
                    "Підбери пароль за словником <code>/srv/vault/wordlist.txt</code>, порівнявши SHA-256 хеш "
                    "кожного слова (без символу нового рядка <code>\\n</code>!) із хешем у <code>/srv/vault/pass.sha256</code>. "
                    "Запиши знайдений пароль у <code>~/cracked_pass.txt</code>."
                ),
                "hint": (
                    "Цикл у bash: <code>while read w; do [ \"$(printf '%s' \"$w\" | sha256sum | cut -d' ' -f1)\" = "
                    "\"$(cat /srv/vault/pass.sha256)\" ] &amp;&amp; echo \"$w\"; done &lt; /srv/vault/wordlist.txt</code>"
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/cracked_pass.txt)" = "cyber_sentinel_42" ]
""",
            },
            {
                "text": (
                    "Розшифруй файл <code>/srv/vault/flag.txt.enc</code> за допомогою <code>openssl enc -d -aes-256-cbc -pbkdf2</code> "
                    "і знайденого пароля, та збережи прапор у <code>~/flag.txt</code>."
                ),
                "hint": (
                    "<code>openssl enc -d -aes-256-cbc -pbkdf2 -in /srv/vault/flag.txt.enc "
                    "-out ~/flag.txt -pass pass:cyber_sentinel_42</code>"
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/flag.txt)" = "CTF{openssl_aes256_cracked_and_decrypted}" ]
""",
            },
        ],
    },
    {
        "slug": "postgres_sec_audit",
        "title": "Аудит безпеки PostgreSQL: backdoor-ролі, витік токенів і pg_hba.conf",
        "category": "Security / Databases",
        "difficulty": "hard",
        "reward_points": 45,
        "mem_limit": "384m",
        "pids_limit": 150,
        "intro": (
            "Під час пентесту бази даних <code>corp_sec</code> у PostgreSQL виявлено критичні діри в безпеці: "
            "зайвий суперкористувач <code>hacker_dba</code>, веб-роль із надмірними правами та безпарольний доступ "
            "<code>trust</code> у конфігурації <code>pg_hba.conf</code>."
        ),
        "setup_script": r"""
echo "shared_buffers = 24MB" >> /etc/postgresql/14/main/postgresql.conf
echo "max_connections = 20" >> /etc/postgresql/14/main/postgresql.conf
sed -i 's/127\.0\.0\.1\/32\s\+scram-sha-256/127.0.0.1\/32 trust/' /etc/postgresql/14/main/pg_hba.conf
service postgresql start
for i in $(seq 1 60); do pg_isready -q && break; sleep 0.5; done

runuser -u postgres -- createdb corp_sec
runuser -u postgres -- psql -d corp_sec -v ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE hacker_dba SUPERUSER LOGIN PASSWORD 'pwned';
CREATE ROLE webapp_user SUPERUSER LOGIN PASSWORD 'webapp_pass';
CREATE TABLE api_secrets (id serial PRIMARY KEY, service text, token text);
INSERT INTO api_secrets (service, token) VALUES
  ('billing', 'tok_live_998123'),
  ('root_vault', 'CTF{pg_hardening_and_least_privilege}'),
  ('metrics', 'tok_test_112233');
CREATE TABLE audit_events (id serial PRIMARY KEY, msg text);
GRANT ALL ON TABLE api_secrets, audit_events TO webapp_user;
SQL
""",
        "steps": [
            {
                "text": (
                    "Підключись до бази <code>corp_sec</code>, знайди прапор <code>CTF{...}</code> у таблиці "
                    "<code>api_secrets</code> і запиши його в <code>~/db_flag.txt</code>."
                ),
                "hint": "<code>sudo -u postgres psql -d corp_sec -tA -c \"SELECT token FROM api_secrets WHERE service='root_vault';\" &gt; ~/db_flag.txt</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/db_flag.txt)" = "CTF{pg_hardening_and_least_privilege}" ]
""",
            },
            {
                "text": (
                    "Виправ привілеї ролей у БД <code>corp_sec</code>: "
                    "1) видали бекдор-роль <code>hacker_dba</code>; "
                    "2) забери права суперкористувача (<code>NOSUPERUSER</code>) у ролі <code>webapp_user</code>; "
                    "3) забери у <code>webapp_user</code> усі права на таблицю <code>api_secrets</code> (залиш доступ лише до <code>audit_events</code>)."
                ),
                "hint": (
                    "У <code>psql -d corp_sec</code>: <code>DROP ROLE hacker_dba;</code>, "
                    "<code>ALTER ROLE webapp_user NOSUPERUSER;</code>, "
                    "<code>REVOKE ALL ON TABLE api_secrets FROM webapp_user;</code>"
                ),
                "check": r"""
P='sudo -n -u postgres psql -d corp_sec -tA'
[ "$($P -c "SELECT count(*) FROM pg_roles WHERE rolname='hacker_dba'")" = 0 ] || exit 1
[ "$($P -c "SELECT rolsuper FROM pg_roles WHERE rolname='webapp_user'")" = f ] || exit 1
[ "$($P -c "SELECT has_table_privilege('webapp_user','api_secrets','SELECT')")" = f ] || exit 1
[ "$($P -c "SELECT has_table_privilege('webapp_user','audit_events','SELECT')")" = t ]
""",
            },
            {
                "text": (
                    "Захисти мережеву автентифікацію PostgreSQL: у <code>/etc/postgresql/14/main/pg_hba.conf</code> "
                    "заміни небезпечний метод <code>trust</code> для IPv4 <code>127.0.0.1/32</code> на "
                    "<code>scram-sha-256</code> і перезавантаж конфігурацію PostgreSQL."
                ),
                "hint": (
                    "<code>sudo sed -i 's/127.0.0.1\\/32 trust/127.0.0.1\\/32 scram-sha-256/' /etc/postgresql/14/main/pg_hba.conf "
                    "&amp;&amp; sudo service postgresql reload</code>"
                ),
                "check": r"""
! grep -E '^[[:space:]]*host.*127\.0\.0\.1/32.*trust' /etc/postgresql/14/main/pg_hba.conf \
  && grep -Eq '^[[:space:]]*host.*127\.0\.0\.1/32.*scram-sha-256' /etc/postgresql/14/main/pg_hba.conf \
  && ! psql -h 127.0.0.1 -U webapp_user -d corp_sec -w -c 'SELECT 1' >/dev/null 2>&1
""",
            },
        ],
    },
    {
        "slug": "iptables_firewall_lockdown",
        "title": "Брандмауер iptables: пошук бекдор-правила та ізоляція портів",
        "category": "Security / Network",
        "difficulty": "hard",
        "reward_points": 45,
        "intro": (
            "Зловмисник додав у таблицю фільтрації <code>iptables</code> прихований ланцюжок "
            "<code>BACKDOOR_ACCEPT</code> із коментарем-прапором і відкрив порт <code>31337</code>. "
            "Проведи аудит правил <code>iptables</code> та налаштуй політику блокування."
        ),
        "setup_script": r"""
iptables -F
iptables -X
iptables -N BACKDOOR_ACCEPT
iptables -A BACKDOOR_ACCEPT -p tcp --dport 31337 -m comment --comment "CTF{iptables_netfilter_guardian_88}" -j ACCEPT
iptables -A INPUT -j BACKDOOR_ACCEPT
""",
        "steps": [
            {
                "text": (
                    "Переглянь усі правила та коментарі <code>iptables</code>, знайди прапор <code>CTF{...}</code> "
                    "у ланцюжку <code>BACKDOOR_ACCEPT</code> та збережи його в <code>~/fw_flag.txt</code>."
                ),
                "hint": "<code>sudo iptables -S</code> або <code>sudo iptables -L -n -v</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/fw_flag.txt)" = "CTF{iptables_netfilter_guardian_88}" ]
""",
            },
            {
                "text": (
                    "Видали посилання на ланцюжок <code>BACKDOOR_ACCEPT</code> із <code>INPUT</code>, очисти та видали "
                    "сам ланцюжок <code>BACKDOOR_ACCEPT</code>, і додай правило в <code>INPUT</code>, яке "
                    "відкидає (<code>DROP</code>) усі вхідні TCP-пакети на порт <code>31337</code>."
                ),
                "hint": (
                    "<code>sudo iptables -D INPUT -j BACKDOOR_ACCEPT &amp;&amp; sudo iptables -F BACKDOOR_ACCEPT "
                    "&amp;&amp; sudo iptables -X BACKDOOR_ACCEPT &amp;&amp; sudo iptables -A INPUT -p tcp --dport 31337 -j DROP</code>"
                ),
                "check": r"""
! sudo iptables -S | grep -q 'BACKDOOR_ACCEPT' \
  && sudo iptables -S INPUT | grep -Eq -- '-A INPUT -p tcp -m tcp --dport 31337 -j DROP'
""",
            },
        ],
    },
]
