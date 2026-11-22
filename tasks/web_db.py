"""Web servers & Databases tasks."""

WEB_DB_TASKS = [
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
]
