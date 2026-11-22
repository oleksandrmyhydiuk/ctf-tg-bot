"""Linux & Scripting tasks."""

LINUX_TASKS = [
    {
        "slug": "perms",
        "title": "Діряві права",
        "category": "Linux",
        "difficulty": "easy",
        "reward_points": 10,
        "intro": "Базові права доступу до файлів у твоїй домашній директорії (<code>~</code>).",
        "setup_script": r"""
echo "CTF{chmod_is_easy}" > /home/student/flag.txt
chown student:student /home/student/flag.txt
chmod 000 /home/student/flag.txt
printf '#!/bin/bash\necho ok > /home/student/done.txt\n' > /home/student/run.sh
chown student:student /home/student/run.sh
chmod 644 /home/student/run.sh
""",
        "steps": [
            {
                "text": "Файл <code>~/flag.txt</code> нечитабельний. Зроби його читабельним для себе.",
                "hint": "Подивись права через <code>ls -l</code> і скористайся <code>chmod</code>.",
                "check": r"""grep -qx 'CTF{chmod_is_easy}' /home/student/flag.txt""",
            },
            {
                "text": (
                    "Скрипт <code>~/run.sh</code> не запускається. Дай права <code>700</code> "
                    "(тільки власник) і виконай його: він створить <code>~/done.txt</code>."
                ),
                "hint": "<code>chmod 700 run.sh &amp;&amp; ./run.sh</code>",
                "check": r"""
[ "$(stat -c %a /home/student/run.sh)" = 700 ] && [ "$(cat /home/student/done.txt 2>/dev/null)" = ok ]
""",
            },
        ],
    },
    {
        "slug": "needle",
        "title": "Голка в стозі сіна",
        "category": "Linux",
        "difficulty": "easy",
        "reward_points": 15,
        "intro": "Аналіз великих логів стандартними утилітами (<code>grep</code>, <code>wc</code>, <code>awk</code>).",
        "setup_script": r"""
seq 1 1000 | sed 's/^/INFO: connection from 192.168.1./' > /var/log/server.log
echo "PASSWORD=super_secret_admin_pass" >> /var/log/server.log
seq 1 500 | sed 's/^/DEBUG: timeout error /' >> /var/log/server.log
chmod 644 /var/log/server.log
awk 'BEGIN{for(i=1;i<=300;i++){ if(i%8==0) print "ERROR: disk failure " i; else print "INFO: ok " i }}' > /var/log/app.log
chmod 644 /var/log/app.log
""",
        "steps": [
            {
                "text": (
                    "У <code>/var/log/server.log</code> серед тисяч рядків є <code>PASSWORD=...</code>. "
                    "Запиши <b>лише значення</b> пароля (без <code>PASSWORD=</code>) у <code>~/answer.txt</code>."
                ),
                "hint": "<code>grep PASSWORD /var/log/server.log | cut -d= -f2 &gt; ~/answer.txt</code>",
                "check": r"""[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/answer.txt)" = "super_secret_admin_pass" ]""",
            },
            {
                "text": (
                    "Скільки рядків із <code>ERROR</code> у <code>/var/log/app.log</code>? "
                    "Запиши число в <code>~/count.txt</code>."
                ),
                "hint": "<code>grep -c ERROR /var/log/app.log &gt; ~/count.txt</code>",
                "check": r"""
exp=$(grep -c ERROR /var/log/app.log)
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/count.txt)" = "$exp" ]
""",
            },
        ],
    },
    {
        "slug": "hidden",
        "title": "Невидимець",
        "category": "Linux",
        "difficulty": "easy",
        "reward_points": 15,
        "intro": "Пошук файлів, прихованих файлів і архівація.",
        "setup_script": r"""
echo "hidden_marker_992" > /tmp/.hidden_config_992.cfg
chown student:student /tmp/.hidden_config_992.cfg
mkdir -p /srv/data/a /srv/data/b/c /srv/data/d
touch /srv/data/a/1.bak /srv/data/b/c/2.bak /srv/data/b/3.bak /srv/data/d/4.bak /srv/data/d/5.bak
echo keep > /srv/data/a/keep.txt
echo keep > /srv/data/b/c/keep2.txt
""",
        "steps": [
            {
                "text": (
                    "У <code>/tmp</code> лежить прихований файл. Знайди його, перейменуй на "
                    "<code>visible.txt</code> і перемісти в домашню директорію (<code>~</code>)."
                ),
                "hint": "Приховані файли видно через <code>ls -a /tmp</code>; перемістити: <code>mv</code>.",
                "check": r"""[ ! -e /tmp/.hidden_config_992.cfg ] && grep -qx 'hidden_marker_992' /home/student/visible.txt""",
            },
            {
                "text": (
                    "У <code>/srv/data</code> (з вкладеними папками) розкидані файли <code>*.bak</code>. "
                    "Створи архів <code>~/backups.tar.gz</code>, що містить <b>тільки</b> усі <code>.bak</code> файли."
                ),
                "hint": (
                    "<code>find /srv/data -name '*.bak' | tar czf ~/backups.tar.gz -T -</code> "
                    "(або <code>-T</code> замість xargs)."
                ),
                "check": r"""
files=$(tar tzf /home/student/backups.tar.gz 2>/dev/null | grep -v '/$')
[ "$(echo "$files" | grep -c '\.bak$')" = 5 ] && [ "$(echo "$files" | wc -l)" = 5 ]
""",
            },
        ],
    },
    {
        "slug": "users",
        "title": "Користувачі та групи",
        "category": "Linux",
        "difficulty": "easy",
        "reward_points": 20,
        "intro": "Адміністрування користувачів: тепер ти можеш використовувати <code>sudo</code>.",
        "setup_script": r"""
mkdir -p /srv/project
""",
        "steps": [
            {
                "text": "Створи користувача <code>deploy</code> з домашньою директорією <code>/home/deploy</code> та оболонкою <code>/bin/bash</code>.",
                "hint": "<code>sudo useradd -m -s /bin/bash deploy</code>",
                "check": r"""
[ "$(getent passwd deploy | cut -d: -f6,7)" = "/home/deploy:/bin/bash" ] && [ -d /home/deploy ]
""",
            },
            {
                "text": "Створи групу <code>devs</code> і додай до неї користувачів <code>deploy</code> та <code>student</code>.",
                "hint": "<code>sudo groupadd devs</code>, потім <code>sudo usermod -aG devs deploy</code> (і для student).",
                "check": r"""
getent group devs >/dev/null \
  && id -nG deploy | tr ' ' '\n' | grep -qx devs \
  && id -nG student | tr ' ' '\n' | grep -qx devs
""",
            },
            {
                "text": (
                    "Каталог <code>/srv/project</code> має належати групі <code>devs</code>, мати права "
                    "<code>2770</code> (rwx для власника й групи, <b>setgid</b>, нічого для інших)."
                ),
                "hint": "<code>sudo chgrp devs /srv/project &amp;&amp; sudo chmod 2770 /srv/project</code>",
                "check": r"""[ "$(stat -c '%a %U %G' /srv/project)" = "2770 root devs" ]""",
            },
        ],
    },
    {
        "slug": "bash_script",
        "title": "Bash-скрипт з аргументами",
        "category": "Scripting",
        "difficulty": "medium",
        "reward_points": 25,
        "intro": (
            "Пишемо скрипт крок за кроком. Редактори недоступні, тож створюй файл через "
            "<code>cat &gt; файл</code> з heredoc або <code>printf</code>/<code>tee</code>."
        ),
        "setup_script": r"""
true
""",
        "steps": [
            {
                "text": (
                    "Створи <code>~/count_users.sh</code>, що друкує <b>кількість</b> користувачів у "
                    "<code>/etc/passwd</code>, чия оболонка <code>/bin/bash</code>."
                ),
                "hint": (
                    "Заготовка: <code>grep -c ':/bin/bash$' /etc/passwd</code>. "
                    "Файл: <code>cat &gt; ~/count_users.sh</code> + heredoc."
                ),
                "check": r"""
s=/home/student/count_users.sh
[ -f "$s" ] && [ "$(bash "$s" 2>/dev/null)" = "$(grep -c ':/bin/bash$' /etc/passwd)" ]
""",
            },
            {
                "text": (
                    "Додай аргумент: якщо передано <code>$1</code>, рахуй користувачів із цією оболонкою "
                    "(напр. <code>/usr/sbin/nologin</code>). Без аргументу працюй як раніше (<code>/bin/bash</code>)."
                ),
                "hint": "Значення за замовчуванням: <code>shell=${1:-/bin/bash}</code>.",
                "check": r"""
s=/home/student/count_users.sh
[ "$(bash "$s" /usr/sbin/nologin 2>/dev/null)" = "$(grep -c ':/usr/sbin/nologin$' /etc/passwd)" ] \
  && [ "$(bash "$s" 2>/dev/null)" = "$(grep -c ':/bin/bash$' /etc/passwd)" ]
""",
            },
            {
                "text": (
                    "Код виходу: якщо користувачів із такою оболонкою немає (результат 0), скрипт має "
                    "завершуватися з кодом <code>1</code>, інакше з <code>0</code>."
                ),
                "hint": "<code>[ \"$n\" -gt 0 ]</code> як остання команда скрипта поверне 0 або 1.",
                "check": r"""
s=/home/student/count_users.sh
bash "$s" /no/such/shell >/dev/null 2>&1; [ $? -eq 1 ] || exit 1
bash "$s" >/dev/null 2>&1; [ $? -eq 0 ]
""",
            },
        ],
    },
    {
        "slug": "access_log",
        "title": "Розслідування access.log",
        "category": "Linux",
        "difficulty": "medium",
        "reward_points": 25,
        "intro": (
            "Веб-сервер віддав <code>/var/log/access.log</code> (формат: "
            "<code>IP - - [дата] \"GET /шлях HTTP/1.1\" статус байти</code>). Допоможи адміну розібратися."
        ),
        "setup_script": r"""
awk 'BEGIN{
  split("/index.html /about /api/users /login /static/app.js /contact /api/orders /health /blog", P, " ");
  for (i=1; i<=500; i++) {
    st=200; if (i%10==0) st=404; if (i%25==0) st=500;
    printf "10.0.0.%d - - [10/Oct/2026:13:%02d:%02d +0000] \"GET %s HTTP/1.1\" %d %d\n", (i%7)+1, int(i/60)%60, i%60, P[(i%9)+1], st, 200+i
  }
  for (i=1; i<=60; i++) printf "10.0.0.3 - - [10/Oct/2026:14:%02d:%02d +0000] \"GET /index.html HTTP/1.1\" 200 512\n", int(i/60), i%60
  for (i=1; i<=25; i++) printf "10.0.0.%d - - [10/Oct/2026:15:00:%02d +0000] \"GET /missing.php HTTP/1.1\" 404 0\n", (i%7)+1, i%60
}' > /var/log/access.log
chmod 644 /var/log/access.log
""",
        "steps": [
            {
                "text": "Який IP робить найбільше запитів? Запиши його в <code>~/top_ip.txt</code>.",
                "hint": "<code>awk '{print $1}' log | sort | uniq -c | sort -rn | head -1</code>",
                "check": r"""
exp=$(awk '{c[$1]++} END{for(k in c) print c[k], k}' /var/log/access.log | sort -rn | head -1 | cut -d' ' -f2)
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/top_ip.txt)" = "$exp" ]
""",
            },
            {
                "text": "Скільки запитів завершились статусом <b>404</b>? Запиши число в <code>~/count404.txt</code>.",
                "hint": "Статус у 9-му полі: <code>awk '$9==404' /var/log/access.log | wc -l</code>",
                "check": r"""
exp=$(awk '$9==404' /var/log/access.log | wc -l | tr -d ' ')
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/count404.txt)" = "$exp" ]
""",
            },
            {
                "text": "Який URL найчастіше дає 404? Запиши шлях (напр. <code>/abc</code>) у <code>~/top404.txt</code>.",
                "hint": "Шлях у 7-му полі; відфільтруй <code>$9==404</code>, порахуй через <code>sort | uniq -c</code>.",
                "check": r"""
exp=$(awk '$9==404{c[$7]++} END{for(k in c) print c[k], k}' /var/log/access.log | sort -rn | head -1 | cut -d' ' -f2)
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/top404.txt)" = "$exp" ]
""",
            },
        ],
    },
    {
        "slug": "processes",
        "title": "Процеси та порти",
        "category": "Linux",
        "difficulty": "medium",
        "reward_points": 25,
        "intro": "У системі працює підозрілий процес, що вантажить CPU, і щось слухає мережевий порт. Тобі знадобиться <code>sudo</code>.",
        "setup_script": r"""
cat > /opt/worker.sh <<'EOS'
#!/bin/bash
while true; do :; done
EOS
chmod +x /opt/worker.sh
setsid nohup /opt/worker.sh >/dev/null 2>&1 </dev/null &
setsid nohup nc -lk 9999 >/dev/null 2>&1 </dev/null &
sleep 1
""",
        "steps": [
            {
                "text": "Знайди PID процесу <code>/opt/worker.sh</code> і запиши його в <code>~/pid.txt</code>.",
                "hint": "<code>ps aux | grep worker</code> або <code>pgrep -f worker.sh</code>.",
                "check": r"""
pid=$(tr -d '[:space:]' 2>/dev/null < /home/student/pid.txt)
case "$pid" in ''|*[!0-9]*) exit 1;; esac
tr '\0' ' ' 2>/dev/null < /proc/$pid/cmdline | grep -q 'worker.sh'
""",
            },
            {
                "text": "Заверши цей процес (він належить root).",
                "hint": "<code>sudo kill &lt;PID&gt;</code>; якщо не завершується, <code>sudo kill -9 &lt;PID&gt;</code>.",
                "check": r"""! pgrep -f '[/]opt/worker.sh' >/dev/null""",
            },
            {
                "text": "Яка програма слухає TCP-порт <code>9999</code>? Запиши її назву в <code>~/listener.txt</code>.",
                "hint": "<code>sudo ss -ltnp | grep 9999</code>: назва в <code>users:((\"...\"</code>.",
                "check": r"""
v=$(tr -d '[:space:]' 2>/dev/null < /home/student/listener.txt)
[ "$v" = nc ] || [ "$v" = nc.openbsd ]
""",
            },
        ],
    },
]
