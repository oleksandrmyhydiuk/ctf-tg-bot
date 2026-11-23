import type { Task, TaskCategory } from '../types';

export const TASK_CATEGORIES: TaskCategory[] = [
  'Усі',
  'Permissions',
  'Logs & Text',
  'Filesystem',
];

export const INITIAL_TASKS: Task[] = [
  {
    id: 1,
    title: 'Діряві права',
    category: 'Permissions',
    difficulty: 'Easy',
    xp: 100,
    solved: false,
    icon: 'lock',
    shortDesc: 'Віднови права доступу до заблокованого файлу flag.txt',
    loreDesc:
      'Під час нічного деплою скрипт скинув права доступу на секретний файл flag.txt до 000. Поверни права на читання (наприклад chmod 400 або chmod +r), прочитай прапор та натисни Check завдання.',
    hint: 'Перевір права командою "ls -l", а потім відкрий доступ на читання через "chmod 400 flag.txt" або "chmod +r flag.txt".',
    review:
      'Чудова робота! Ти відновив права читання для власника за принципом найменших привілеїв. Для файлів із секретами в Linux завжди використовуй 400 або 600 замість 777.',
    initialFiles: {
      'flag.txt': {
        perms: '----------',
        readable: false,
        content: 'CTF{chmod_m4st3r_2026}',
        size: '22B',
      },
      'readme.md': {
        perms: '-rw-r--r--',
        readable: true,
        content:
          'Emergency recovery: restore read permissions on flag.txt to verify the secret.',
        size: '78B',
      },
    },
  },
  {
    id: 2,
    title: 'Голка в стозі сіна',
    category: 'Logs & Text',
    difficulty: 'Medium',
    xp: 150,
    solved: false,
    icon: 'search',
    shortDesc: 'Знайди пароль у логах server.log і збережи його в answer.txt',
    loreDesc:
      'У продакшн-логах server.log випадково зберігся пароль сервісу. Знайди рядок із PASSWORD за допомогою grep та запиши знайдене значення пароля у файл answer.txt.',
    hint: 'Виконай "grep PASSWORD server.log", щоб знайти рядок із секретом, а потім запиши значення пароля командою: echo "super_secret_devops_pass" > answer.txt',
    review:
      'Відмінний пошук по логах! Команда grep дозволяє миттєво знаходити чутливі дані у великих файлах. У продакшені не забувай маскувати секрети на рівні логера.',
    initialFiles: {
      'server.log': {
        perms: '-rw-r--r--',
        readable: true,
        content: [
          '[2026-11-23 10:01:12] INFO  boot: container sandbox-02 initialized',
          '[2026-11-23 10:01:15] INFO  nginx: listening on 0.0.0.0:8080',
          '[2026-11-23 10:02:04] WARN  auth: fallback env dump triggered',
          '[2026-11-23 10:02:04] DEBUG config: DB_HOST=10.0.4.12',
          '[2026-11-23 10:02:05] DEBUG config: PASSWORD=super_secret_devops_pass',
          '[2026-11-23 10:02:09] INFO  healthcheck: status=200 OK',
        ].join('\n'),
        size: '342B',
      },
    },
  },
  {
    id: 3,
    title: 'Невидимець',
    category: 'Filesystem',
    difficulty: 'Easy',
    xp: 120,
    solved: true,
    icon: 'eye-off',
    shortDesc: 'Знайди прихований конфіг зловмисника і зроби його видимим',
    loreDesc:
      'У робочій директорії схований підозрілий dotfile із параметрами бекдору. Знайди його за допомогою ls -la та перейменуй у visible.txt через mv.',
    hint: 'Файли, що починаються з крапки, приховані від звичайного ls. Виконай "ls -la", а потім "mv .hidden_config_992.cfg visible.txt".',
    review:
      'Прихований конфіг виявлено та демасковано! Перевірка dotfiles через ls -la — обов’язковий крок під час аудиту та інцидент-респонсу в Linux.',
    initialFiles: {
      '.hidden_config_992.cfg': {
        perms: '-rw-------',
        readable: true,
        content: 'BACKDOOR_PORT=4444\nC2_HOST=10.0.0.99',
        size: '36B',
      },
      'notes.txt': {
        perms: '-rw-r--r--',
        readable: true,
        content: 'Audit checklist: inspect hidden dotfiles in /home/sandbox',
        size: '57B',
      },
    },
  },
];
