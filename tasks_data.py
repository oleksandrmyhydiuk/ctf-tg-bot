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

TASKS = [
    # ------------------------------------------------------------------ 1
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
    # ------------------------------------------------------------------ 2
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
    # ------------------------------------------------------------------ 3
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
    # ------------------------------------------------------------------ 4
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
    # ------------------------------------------------------------------ 5
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
    # ------------------------------------------------------------------ 6
    {
        "slug": "sqlite_hr",
        "title": "SQLite: кадри",
        "category": "Databases",
        "difficulty": "medium",
        "reward_points": 20,
        "intro": "База <code>~/inventory.db</code> (SQLite), таблиця <code>employees(id, name, dept, salary)</code>. Клієнт: <code>sqlite3</code>.",
        "setup_script": r"""
sqlite3 /home/student/inventory.db <<'SQL'
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT, salary INTEGER);
INSERT INTO employees VALUES
 (1,'Anna','dev',5000),(2,'Ivan','dev',5500),(3,'Olga','support',2500),
 (4,'Petro','support',2700),(5,'Maria','hr',3000),(6,'Taras','sales',3500),(7,'Iryna','sales',4000);
SQL
chown student:student /home/student/inventory.db
""",
        "steps": [
            {
                "text": "Який відділ має найбільшу <b>сумарну</b> зарплату? Запиши його назву в <code>~/answer.txt</code>.",
                "hint": "<code>SELECT dept, SUM(salary) FROM employees GROUP BY dept ORDER BY 2 DESC;</code>",
                "check": r"""[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/answer.txt)" = "dev" ]""",
            },
            {
                "text": "Підніми зарплату на 10% <b>лише</b> відділу <code>support</code> (команда <code>UPDATE</code>).",
                "hint": "<code>sqlite3 ~/inventory.db \"UPDATE employees SET salary = salary*1.1 WHERE dept='support';\"</code>",
                "check": r"""
q() { sqlite3 /home/student/inventory.db "$1"; }
[ "$(q "select cast(round(salary) as integer) from employees where name='Olga'")" = 2750 ] \
  && [ "$(q "select cast(round(salary) as integer) from employees where name='Petro'")" = 2970 ] \
  && [ "$(q "select sum(salary) from employees where dept!='support'")" = 21000 ]
""",
            },
            {
                "text": "Створи індекс з іменем <code>idx_dept</code> по колонці <code>dept</code> таблиці <code>employees</code>.",
                "hint": "<code>CREATE INDEX idx_dept ON employees(dept);</code>",
                "check": r"""
[ "$(sqlite3 /home/student/inventory.db "select count(*) from sqlite_master where type='index' and name='idx_dept'")" = 1 ]
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 7
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
    # ------------------------------------------------------------------ 8
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
    # ------------------------------------------------------------------ 9
    {
        "slug": "nginx_fix",
        "title": "Зламаний nginx",
        "category": "Web servers",
        "difficulty": "medium",
        "reward_points": 30,
        "mem_limit": "256m",
        "pids_limit": 150,
        "intro": (
            "На сервері встановлено nginx із сайтом <code>mysite</code>, але він не стартує. "
            "Корисно: <code>sudo nginx -t</code>, <code>sudo service nginx start|reload</code>, "
            "<code>curl</code>, <code>sudo sed -i</code>, <code>sudo tee</code>."
        ),
        "setup_script": r"""
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/mysite
echo "Hello from mysite" > /var/www/mysite/index.html
cat > /etc/nginx/sites-available/mysite <<'CONF'
server {
    listen 80;
    server_name localhost;
    root /var/www/mysite
    index index.html;
}
CONF
ln -sf /etc/nginx/sites-available/mysite /etc/nginx/sites-enabled/mysite
""",
        "steps": [
            {
                "text": (
                    "Знайди помилку в конфігу (<code>/etc/nginx/sites-available/mysite</code>), виправ її "
                    "та запусти nginx. <code>http://127.0.0.1/</code> має віддавати «Hello from mysite»."
                ),
                "hint": "<code>sudo nginx -t</code> покаже рядок із помилкою (чогось не вистачає в кінці директиви).",
                "check": r"""curl -s --max-time 3 http://127.0.0.1/ | grep -q 'Hello from mysite'""",
            },
            {
                "text": (
                    "Додай ендпоінт <code>/health</code>, що повертає статус <b>200</b> і тіло <code>OK</code> "
                    "(без створення файлів, через <code>location</code>), та перезавантаж nginx."
                ),
                "hint": "<code>location /health { return 200 \"OK\"; }</code> усередині <code>server { }</code>, потім <code>sudo service nginx reload</code>.",
                "check": r"""
[ "$(curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1/health)" = 200 ] \
  && [ "$(curl -s --max-time 3 http://127.0.0.1/health)" = "OK" ]
""",
            },
            {
                "text": "Додай до відповідей заголовок <code>X-Powered-By: sandbox</code> (директива <code>add_header</code> у блоці <code>server</code>) і застосуй конфіг.",
                "hint": "<code>add_header X-Powered-By \"sandbox\" always;</code>, перевір через <code>curl -I http://127.0.0.1/</code>.",
                "check": r"""curl -sI --max-time 3 http://127.0.0.1/ | grep -qi '^x-powered-by: sandbox'""",
            },
        ],
    },
    # ------------------------------------------------------------------ 10
    {
        "slug": "port_conflict",
        "title": "Конфлікт портів: nginx + Apache",
        "category": "Web servers",
        "difficulty": "medium",
        "reward_points": 30,
        "mem_limit": "256m",
        "pids_limit": 150,
        "intro": (
            "На порту 80 працює nginx (віддає «nginx OK»). Також встановлено Apache, який не може стартувати: "
            "порт зайнятий. Корисно: <code>sudo apache2ctl configtest</code>, <code>sudo service apache2 start</code>, "
            "<code>sudo ss -ltnp</code>."
        ),
        "setup_script": r"""
mkdir -p /var/www/nginx-site
echo "nginx OK" > /var/www/nginx-site/index.html
cat > /etc/nginx/sites-available/default <<'CONF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/nginx-site;
    index index.html;
}
CONF
echo "Apache OK" > /var/www/html/index.html
service nginx start
""",
        "steps": [
            {
                "text": (
                    "Налаштуй Apache на порт <b>8081</b> і запусти його: <code>http://127.0.0.1:8081/</code> "
                    "має віддавати «Apache OK», а nginx на порту 80 має далі працювати."
                ),
                "hint": (
                    "Змінюй і <code>/etc/apache2/ports.conf</code> (<code>Listen</code>), і "
                    "<code>&lt;VirtualHost *:80&gt;</code> у <code>/etc/apache2/sites-available/000-default.conf</code>."
                ),
                "check": r"""
[ "$(curl -s --max-time 3 http://127.0.0.1:8081/)" = "Apache OK" ] \
  && [ "$(curl -s --max-time 3 http://127.0.0.1/)" = "nginx OK" ]
""",
            },
            {
                "text": (
                    "Увімкни в Apache модуль <code>headers</code> і додай до всіх відповідей заголовок "
                    "<code>X-Env: sandbox</code>, потім перезапусти Apache."
                ),
                "hint": (
                    "<code>sudo a2enmod headers</code>, рядок <code>Header set X-Env \"sandbox\"</code> "
                    "(напр. у новому файлі в <code>/etc/apache2/conf-available/</code> + <code>sudo a2enconf</code>), "
                    "<code>sudo service apache2 restart</code>."
                ),
                "check": r"""curl -sI --max-time 3 http://127.0.0.1:8081/ | grep -qi '^x-env: sandbox'""",
            },
        ],
    },
    # ------------------------------------------------------------------ 11
    {
        "slug": "postgres_shop",
        "title": "PostgreSQL: інтернет-магазин",
        "category": "Databases",
        "difficulty": "hard",
        "reward_points": 35,
        "mem_limit": "384m",
        "pids_limit": 150,
        "intro": (
            "Працює PostgreSQL із базою <code>shop</code> (таблиці <code>products(id, name, price, stock)</code> "
            "і <code>orders(id, product_id, qty)</code>). Підключення від адміна: "
            "<code>sudo -u postgres psql -d shop</code>."
        ),
        "setup_script": r"""
echo "shared_buffers = 24MB" >> /etc/postgresql/14/main/postgresql.conf
echo "max_connections = 20" >> /etc/postgresql/14/main/postgresql.conf
service postgresql start
for i in $(seq 1 60); do pg_isready -q && break; sleep 0.5; done
runuser -u postgres -- createdb shop
runuser -u postgres -- psql -d shop -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE products (id serial PRIMARY KEY, name text NOT NULL, price numeric(10,2) NOT NULL, stock int NOT NULL);
INSERT INTO products (name, price, stock) VALUES
 ('Keyboard',49.90,10),('Monitor',199.00,4),('Mouse',19.50,30),('Laptop',899.99,2),('Cable',4.99,100);
CREATE TABLE orders (id serial PRIMARY KEY, product_id int REFERENCES products(id), qty int NOT NULL);
INSERT INTO orders (product_id, qty) VALUES (4,1),(3,3),(3,2),(5,5),(2,2),(5,10);
SQL
""",
        "steps": [
            {
                "text": "Знайди <b>найдорожчий</b> товар і запиши його назву в <code>~/answer.txt</code>.",
                "hint": "<code>SELECT name FROM products ORDER BY price DESC LIMIT 1;</code>",
                "check": r"""[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/answer.txt)" = "Laptop" ]""",
            },
            {
                "text": (
                    "Створи роль <code>report</code> з правом входу та паролем <code>rep0rt</code>, яка має "
                    "право <b>лише SELECT</b> на таблицю <code>products</code> (не суперкористувач, без INSERT/UPDATE)."
                ),
                "hint": (
                    "<code>CREATE ROLE report LOGIN PASSWORD 'rep0rt';</code> і "
                    "<code>GRANT SELECT ON products TO report;</code>"
                ),
                "check": r"""
P='sudo -n -u postgres psql -d shop -tA'
[ "$($P -c "select count(*) from pg_roles where rolname='report' and rolcanlogin and not rolsuper")" = 1 ] || exit 1
[ "$($P -c "select has_table_privilege('report','products','SELECT')")" = t ] || exit 1
[ "$($P -c "select has_table_privilege('report','products','INSERT')")" = f ] || exit 1
[ "$(PGPASSWORD=rep0rt psql -h 127.0.0.1 -U report -d shop -tA -c 'select count(*) from products' 2>/dev/null)" = 5 ]
""",
            },
            {
                "text": (
                    "Підготуй звіт <code>~/report.csv</code>: для кожного товару, що має замовлення, рядок "
                    "<code>name,total_qty</code> (сума <code>qty</code>), без заголовка, за спаданням total_qty."
                ),
                "hint": (
                    "JOIN products і orders, GROUP BY name. Формат CSV без заголовка: "
                    "<code>psql -tA -F, -c \"...\" &gt; ~/report.csv</code>."
                ),
                "check": r"""
exp=$(printf 'Cable,15\nMouse,5\nMonitor,2\nLaptop,1')
[ "$(cat /home/student/report.csv 2>/dev/null)" = "$exp" ]
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 12
    {
        "slug": "reverse_proxy",
        "title": "Reverse proxy: nginx перед Apache",
        "category": "Web servers",
        "difficulty": "hard",
        "reward_points": 40,
        "mem_limit": "256m",
        "pids_limit": 150,
        "intro": (
            "Бекенд на Apache слухає <code>127.0.0.1:8081</code> («backend OK»), фронтенд nginx на порту 80 "
            "віддає свою сторінку («front OK»). Зроби з nginx reverse proxy."
        ),
        "setup_script": r"""
echo "Listen 8081" > /etc/apache2/ports.conf
sed -i 's/<VirtualHost \*:80>/<VirtualHost *:8081>/' /etc/apache2/sites-available/000-default.conf
echo "backend OK" > /var/www/html/index.html
service apache2 start
mkdir -p /var/www/front
echo "front OK" > /var/www/front/index.html
cat > /etc/nginx/sites-available/default <<'CONF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/front;
    index index.html;
    location / {
        try_files $uri $uri/ =404;
    }
}
CONF
service nginx start
""",
        "steps": [
            {
                "text": (
                    "Налаштуй nginx так, щоб запити до <code>/app/</code> проксувалися на Apache "
                    "(<code>http://127.0.0.1:8081/</code>): <code>http://127.0.0.1/app/</code> віддає «backend OK», "
                    "а <code>/</code> і далі віддає «front OK»."
                ),
                "hint": (
                    "Додай <code>location /app/ { proxy_pass http://127.0.0.1:8081/; }</code> у "
                    "<code>/etc/nginx/sites-available/default</code>, потім <code>sudo nginx -t &amp;&amp; sudo service nginx reload</code>. "
                    "Слеш у кінці <code>proxy_pass</code> важливий."
                ),
                "check": r"""
[ "$(curl -s --max-time 3 http://127.0.0.1/app/)" = "backend OK" ] \
  && [ "$(curl -s --max-time 3 http://127.0.0.1/)" = "front OK" ]
""",
            },
            {
                "text": (
                    "Тепер зупини Apache. Налаштуй nginx так, щоб коли бекенд недоступний, "
                    "<code>/app/</code> повертав HTTP <b>503</b> з тілом <code>maintenance</code> "
                    "(замість 502 Bad Gateway)."
                ),
                "hint": (
                    "<code>error_page 502 =503 @maint;</code> і <code>location @maint { return 503 \"maintenance\"; }</code>; "
                    "Apache: <code>sudo service apache2 stop</code>."
                ),
                "check": r"""
! curl -s --max-time 2 http://127.0.0.1:8081/ >/dev/null 2>&1 || exit 1
[ "$(curl -s --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1/app/)" = 503 ] \
  && [ "$(curl -s --max-time 3 http://127.0.0.1/app/)" = "maintenance" ]
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 13
    {
        "slug": "suid_privesc",
        "title": "SUID-експлойт: втеча з непривілейованого оточення",
        "category": "Security / Privesc",
        "difficulty": "medium",
        "reward_points": 35,
        "intro": (
            "У цій задачі в тебе <b>забрали <code>sudo</code></b>. Ти звичайний користувач "
            "<code>student</code>, але адміністратор залишив у системі неправильно налаштований "
            "бінарний файл із бітом <b>SUID</b> (<code>rwsr-xr-x</code>), що виконується з правами <code>root</code>."
        ),
        "setup_script": r"""
rm -f /etc/sudoers.d/student
echo "CTF{suid_gtfobins_pwned_941}" > /root/vault_flag.txt
chmod 0400 /root/vault_flag.txt
chown root:root /root/vault_flag.txt

cp /usr/bin/find /usr/local/bin/sysbackup-find
chown root:root /usr/local/bin/sysbackup-find
chmod 4755 /usr/local/bin/sysbackup-find
""",
        "steps": [
            {
                "text": (
                    "Знайди нестандартний SUID-бінарник у каталозі <code>/usr/local/bin</code>, який належить "
                    "<code>root</code>, і запиши його <b>повний шлях</b> у <code>~/suid_bin.txt</code>."
                ),
                "hint": "Пошук SUID-файлів: <code>find /usr/local/bin -perm -4000 -type f 2&gt;/dev/null</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/suid_bin.txt)" = "/usr/local/bin/sysbackup-find" ]
""",
            },
            {
                "text": (
                    "Використай знайдений SUID-бінарник, щоб прочитати закритий файл <code>/root/vault_flag.txt</code> "
                    "(права <code>0400</code>), і збережи прапор у <code>~/flag.txt</code>."
                ),
                "hint": (
                    "Утиліта <code>find</code> має прапорець <code>-exec</code>: "
                    "<code>/usr/local/bin/sysbackup-find /root -name vault_flag.txt -exec cat {} + &gt; ~/flag.txt</code>"
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/flag.txt)" = "CTF{suid_gtfobins_pwned_941}" ]
""",
            },
            {
                "text": (
                    "Виправ вразливість (remediation): скористайся цим же SUID-бінарником, щоб <b>зняти SUID-біт</b> "
                    "із самого себе (<code>/usr/local/bin/sysbackup-find</code> має мати права <code>0755</code>)."
                ),
                "hint": (
                    "Виконай <code>chmod</code> через сам SUID-бінарник: "
                    "<code>/usr/local/bin/sysbackup-find /root -maxdepth 0 -exec chmod 0755 /usr/local/bin/sysbackup-find \\;</code>"
                ),
                "check": r"""
[ "$(stat -c '%a' /usr/local/bin/sysbackup-find 2>/dev/null)" = "755" ]
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 14
    {
        "slug": "sudo_path_hijack",
        "title": "Компрометація sudo: PATH Hijacking",
        "category": "Security / Privesc",
        "difficulty": "hard",
        "reward_points": 40,
        "intro": (
            "Повний доступ до <code>sudo</code> вимкнено, але в <code>sudo -l</code> дозволено запускати "
            "один адміністративний скрипт від <code>root</code>. Досліди скрипт та використай перехоплення "
            "шляху пошуку виконуваних файлів (<b>PATH Hijacking</b>)."
        ),
        "setup_script": r"""
sed -i 's/^Defaults\s\+secure_path/# Defaults secure_path/' /etc/sudoers
cat > /etc/sudoers.d/student <<'EOF'
Defaults !secure_path
Defaults env_keep += "PATH"
student ALL=(root) NOPASSWD: /opt/sysadmin/diag.sh
EOF
chmod 440 /etc/sudoers.d/student

mkdir -p /opt/sysadmin
cat > /opt/sysadmin/diag.sh <<'EOF'
#!/bin/bash
echo "[*] Running system diagnostics..."
portcheck-util --quick
EOF
chown root:root /opt/sysadmin/diag.sh
chmod 755 /opt/sysadmin/diag.sh

cat > /usr/local/bin/portcheck-util <<'EOF'
#!/bin/bash
echo "All local ports healthy."
EOF
chown root:root /usr/local/bin/portcheck-util
chmod 755 /usr/local/bin/portcheck-util

echo "CTF{path_hijack_root_escalation_77}" > /root/root_flag.txt
chmod 400 /root/root_flag.txt
""",
        "steps": [
            {
                "text": (
                    "Перевір свої права через <code>sudo -l</code> та проаналізуй дозволений скрипт. "
                    "Яка зовнішня утиліта викликається в ньому <b>без абсолютного шляху</b>? "
                    "Запиши лише її назву в <code>~/vuln_util.txt</code>."
                ),
                "hint": "Прочитай <code>cat /opt/sysadmin/diag.sh</code>.",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/vuln_util.txt)" = "portcheck-util" ]
""",
            },
            {
                "text": (
                    "Підміни цю утиліту через змінну <code>PATH</code> при виклику <code>sudo /opt/sysadmin/diag.sh</code>, "
                    "щоб прочитати <code>/root/root_flag.txt</code> і записати прапор у <code>~/flag.txt</code>."
                ),
                "hint": (
                    "Створи виконуваний скрипт <code>/tmp/portcheck-util</code>, який копіює <code>/root/root_flag.txt</code> "
                    "у <code>/home/student/flag.txt</code> (та дає права <code>chmod 644</code>), і запусти: "
                    "<code>PATH=/tmp:$PATH sudo /opt/sysadmin/diag.sh</code>"
                ),
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/flag.txt)" = "CTF{path_hijack_root_escalation_77}" ]
""",
            },
            {
                "text": (
                    "Використай отримані привілеї <code>root</code>, щоб усунути вразливість: "
                    "заміни виклик у <code>/opt/sysadmin/diag.sh</code> на безпечний абсолютний шлях "
                    "<code>/usr/local/bin/portcheck-util --quick</code> та видали <code>env_keep</code> і "
                    "<code>!secure_path</code> із <code>/etc/sudoers.d/student</code>."
                ),
                "hint": (
                    "У своєму <code>/tmp/portcheck-util</code> виконай: "
                    "<code>sed -i 's|portcheck-util|/usr/local/bin/portcheck-util|' /opt/sysadmin/diag.sh</code> "
                    "та <code>sed -i '/env_keep\\|secure_path/d' /etc/sudoers.d/student</code>, після чого запусти "
                    "<code>PATH=/tmp:$PATH sudo /opt/sysadmin/diag.sh</code>."
                ),
                "check": r"""
grep -q '/usr/local/bin/portcheck-util --quick' /opt/sysadmin/diag.sh || exit 1
t=$(mktemp -d /tmp/.chkXXXXXX)
chmod 755 "$t"
printf '#!/bin/bash\necho HIJACKED\nexit 99\n' > "$t/portcheck-util"
chmod 755 "$t/portcheck-util"
if [ "$(id -u)" = 0 ]; then
  ! grep -Eq 'env_keep|!secure_path' /etc/sudoers.d/student || { rm -rf "$t"; exit 1; }
  out=$(runuser -u student -- env PATH="$t:$PATH" sudo -n /opt/sysadmin/diag.sh 2>/dev/null)
  rc=$?
else
  out=$(PATH="$t:$PATH" sudo -n /opt/sysadmin/diag.sh 2>/dev/null)
  rc=$?
fi
rm -rf "$t"
[ $rc -eq 0 ] && echo "$out" | grep -qx 'All local ports healthy.' && ! echo "$out" | grep -q 'HIJACKED'
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 15
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
    # ------------------------------------------------------------------ 16
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
    # ------------------------------------------------------------------ 17
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
    # ------------------------------------------------------------------ 18
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
    # ------------------------------------------------------------------ 19
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
    # ------------------------------------------------------------------ 20
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
    # ------------------------------------------------------------------ 21
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
    # ------------------------------------------------------------------ 22
    {
        "slug": "acl_and_special_bits",
        "title": "Спеціальні біти доступу, POSIX ACL та захист спільних каталогів",
        "category": "Security / Access Control",
        "difficulty": "medium",
        "reward_points": 30,
        "intro": (
            "Стандартних прав <code>rwx</code> часто недостатньо для гнучкого розмежування доступу. "
            "Налаштуй безпечний спільний каталог зі <b>Sticky Bit</b> та <b>SGID</b>, усунь небезпечний "
            "світовий запис (world-writable) на конфігурації та налаштуй точкові права доступу."
        ),
        "setup_script": r"""
groupadd secops
useradd -m -s /bin/bash -G secops alice
useradd -m -s /bin/bash -G secops bob
useradd -m -s /bin/bash auditor

mkdir -p /srv/secvault/dropzone
chown root:root /srv/secvault/dropzone
chmod 0777 /srv/secvault/dropzone

echo "CTF{sticky_sgid_and_strict_perms_404}" > /srv/secvault/master.conf
chown root:secops /srv/secvault/master.conf
chmod 0666 /srv/secvault/master.conf
""",
        "steps": [
            {
                "text": (
                    "Файл <code>/srv/secvault/master.conf</code> має небезпечні права <code>0666</code> (кожен може "
                    "редагувати). Прочитай із нього прапор у <code>~/flag.txt</code>, а потім закрий права на "
                    "<code>/srv/secvault/master.conf</code> до <code>0640</code> (власник <code>root</code>, група <code>secops</code>)."
                ),
                "hint": "<code>cp /srv/secvault/master.conf ~/flag.txt &amp;&amp; sudo chmod 0640 /srv/secvault/master.conf</code>",
                "check": r"""
[ "$(tr -d '[:space:]' 2>/dev/null < /home/student/flag.txt)" = "CTF{sticky_sgid_and_strict_perms_404}" ] \
  && [ "$(stat -c '%a %U %G' /srv/secvault/master.conf)" = "640 root secops" ]
""",
            },
            {
                "text": (
                    "Налаштуй каталог <code>/srv/secvault/dropzone</code> для безпечної спільної роботи групи "
                    "<code>secops</code>: власник <code>root:secops</code>, права <code>3770</code> "
                    "(<b>SGID</b> + <b>Sticky Bit</b>: усі файли всередині успадковують групу <code>secops</code>, "
                    "а видаляти файли може лише їхній автор або root; сторонні доступу не мають)."
                ),
                "hint": "<code>sudo chown root:secops /srv/secvault/dropzone &amp;&amp; sudo chmod 3770 /srv/secvault/dropzone</code>",
                "check": r"""
[ "$(stat -c '%a %U %G' /srv/secvault/dropzone)" = "3770 root secops" ]
""",
            },
            {
                "text": (
                    "Надай користувачу <code>auditor</code> індивідуальне право <b>лише на читання</b> (<code>r--</code>) "
                    "файлу <code>/srv/secvault/master.conf</code> через POSIX ACL (<code>setfacl</code>) або додай "
                    "<code>auditor</code> до групи <code>secops</code>, не відкриваючи доступ для <code>others</code>."
                ),
                "hint": (
                    "Через ACL: <code>sudo setfacl -m u:auditor:r /srv/secvault/master.conf</code> "
                    "(або через групу: <code>sudo usermod -aG secops auditor</code>). Перевір: "
                    "<code>sudo -u auditor cat /srv/secvault/master.conf</code>."
                ),
                "check": r"""
[ $(( 0$(stat -c '%a' /srv/secvault/master.conf) & 7 )) -eq 0 ] \
  && [ "$(sudo -n -u auditor cat /srv/secvault/master.conf 2>/dev/null)" = "CTF{sticky_sgid_and_strict_perms_404}" ]
""",
            },
        ],
    },
    # ------------------------------------------------------------------ 23
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
    # ------------------------------------------------------------------ 24
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
    # ------------------------------------------------------------------ 25
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
    # ------------------------------------------------------------------ 26
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
    # ------------------------------------------------------------------ 27
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
