import type { TerminalEntry, VirtualFileSystem } from '../types';

const KNOWN_COMMANDS = [
  'help',
  'clear',
  'pwd',
  'whoami',
  'ls',
  'cat',
  'chmod',
  'grep',
  'echo',
  'mv',
  'find',
  'tar',
  './run.sh',
];

export const FULL_DEMO_SLUGS = new Set(['perms', 'needle', 'hidden']);

export function cloneFiles(files: VirtualFileSystem): VirtualFileSystem {
  const copy: VirtualFileSystem = {};
  for (const [name, file] of Object.entries(files)) {
    copy[name] = { ...file };
  }
  return copy;
}

export function getInitialDemoFiles(slug: string): VirtualFileSystem {
  switch (slug) {
    case 'perms':
      return {
        'flag.txt': {
          perms: '----------',
          readable: false,
          content: 'CTF{chmod_is_easy}',
          size: '19B',
        },
        'run.sh': {
          perms: '-rw-r--r--',
          readable: true,
          content: '#!/bin/bash\necho ok > /home/student/done.txt',
          size: '47B',
        },
      };

    case 'needle':
      return {
        '/var/log/server.log': {
          perms: '-rw-r--r--',
          readable: true,
          content: [
            'INFO: connection from 192.168.1.1',
            'INFO: connection from 192.168.1.2',
            'PASSWORD=super_secret_admin_pass',
            'DEBUG: timeout error 1',
            'DEBUG: timeout error 2',
          ].join('\n'),
          size: '148B',
        },
        '/var/log/app.log': {
          perms: '-rw-r--r--',
          readable: true,
          content: Array.from({ length: 300 }, (_, i) => {
            const n = i + 1;
            return n % 8 === 0 ? `ERROR: disk failure ${n}` : `INFO: ok ${n}`;
          }).join('\n'),
          size: '4.1K',
        },
      };

    case 'hidden':
      return {
        '/tmp/.hidden_config_992.cfg': {
          perms: '-rw-------',
          readable: true,
          content: 'hidden_marker_992',
          size: '18B',
        },
        '/srv/data/a/1.bak': { perms: '-rw-r--r--', readable: true, content: '', size: '0B' },
        '/srv/data/b/c/2.bak': { perms: '-rw-r--r--', readable: true, content: '', size: '0B' },
        '/srv/data/b/3.bak': { perms: '-rw-r--r--', readable: true, content: '', size: '0B' },
        '/srv/data/d/4.bak': { perms: '-rw-r--r--', readable: true, content: '', size: '0B' },
        '/srv/data/d/5.bak': { perms: '-rw-r--r--', readable: true, content: '', size: '0B' },
        '/srv/data/a/keep.txt': { perms: '-rw-r--r--', readable: true, content: 'keep', size: '5B' },
      };

    default:
      return {
        'README.txt': {
          perms: '-rw-r--r--',
          readable: true,
          content:
            'Локальний DEMO-режим активний.\nПовноцінне Docker-середовище для цього сценарію запускається при підключенні до Python-сервера бота.',
          size: '132B',
        },
      };
  }
}

function normalizePath(path: string): string {
  if (path.startsWith('~/')) return path.slice(2);
  if (path.startsWith('/home/student/')) return path.slice('/home/student/'.length);
  if (path === '~' || path === '/home/student') return '';
  return path;
}

function tokenize(input: string): string[] {
  const tokens: string[] = [];
  let current = '';
  let quote: '"' | "'" | null = null;

  for (let i = 0; i < input.length; i++) {
    const ch = input[i];
    if (quote) {
      if (ch === quote) {
        quote = null;
      } else {
        current += ch;
      }
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (/\s/.test(ch)) {
      if (current.length > 0) {
        tokens.push(current);
        current = '';
      }
    } else {
      current += ch;
    }
  }

  if (current.length > 0) {
    tokens.push(current);
  }

  return tokens;
}

function octalDigitToRwx(digit: number): string {
  const r = digit & 4 ? 'r' : '-';
  const w = digit & 2 ? 'w' : '-';
  const x = digit & 1 ? 'x' : '-';
  return `${r}${w}${x}`;
}

function applyChmod(
  mode: string,
  currentPerms: string
): { perms: string; readable: boolean } | null {
  if (/^[0-7]{3}$/.test(mode)) {
    const owner = Number(mode[0]);
    const group = Number(mode[1]);
    const other = Number(mode[2]);
    const perms = `-${octalDigitToRwx(owner)}${octalDigitToRwx(group)}${octalDigitToRwx(other)}`;
    return { perms, readable: (owner & 4) !== 0 };
  }

  const symbolicMatch = mode.match(/^([ugoa]*)([+-=])([rwx]+)$/);
  if (!symbolicMatch) return null;

  const [, whoRaw, op, flags] = symbolicMatch;
  const who = whoRaw || 'a';
  const chars = (currentPerms.length === 10 ? currentPerms : '----------').split('');
  const scopes: number[] = [];
  if (who.includes('u') || who.includes('a')) scopes.push(1);
  if (who.includes('g') || who.includes('a')) scopes.push(4);
  if (who.includes('o') || who.includes('a')) scopes.push(7);

  for (const base of scopes) {
    if (op === '=') {
      chars[base] = flags.includes('r') ? 'r' : '-';
      chars[base + 1] = flags.includes('w') ? 'w' : '-';
      chars[base + 2] = flags.includes('x') ? 'x' : '-';
    } else if (op === '+') {
      if (flags.includes('r')) chars[base] = 'r';
      if (flags.includes('w')) chars[base + 1] = 'w';
      if (flags.includes('x')) chars[base + 2] = 'x';
    } else if (op === '-') {
      if (flags.includes('r')) chars[base] = '-';
      if (flags.includes('w')) chars[base + 1] = '-';
      if (flags.includes('x')) chars[base + 2] = '-';
    }
  }

  const perms = chars.join('');
  return { perms, readable: perms[1] === 'r' };
}

function executeSingleCommand(
  trimmed: string,
  nextFiles: VirtualFileSystem
): { entries: TerminalEntry[]; clear?: boolean } {
  // Handle simple pipelines used in bot hints
  if (trimmed.includes('|')) {
    const pipeParts = trimmed.split('|').map((p) => p.trim());
    // grep PASSWORD /var/log/server.log | cut -d= -f2 > ~/answer.txt
    if (
      pipeParts.length === 2 &&
      pipeParts[0].startsWith('grep') &&
      pipeParts[1].includes('cut')
    ) {
      const targetMatch = pipeParts[1].match(/>\s*(\S+)$/);
      const file = nextFiles['/var/log/server.log'];
      if (file) {
        const line = file.content.split('\n').find((l) => l.includes('PASSWORD='));
        const val = line ? line.split('=')[1] ?? '' : '';
        if (targetMatch) {
          const outName = normalizePath(targetMatch[1]);
          nextFiles[outName] = {
            perms: '-rw-r--r--',
            readable: true,
            content: val,
            size: `${val.length}B`,
          };
          return { entries: [] };
        }
        return { entries: [{ type: 'out', text: val }] };
      }
    }

    // find /srv/data -name '*.bak' | tar czf ~/backups.tar.gz -T -
    if (trimmed.includes('find') && trimmed.includes('tar') && trimmed.includes('.bak')) {
      const bakFiles = Object.keys(nextFiles).filter((k) => k.endsWith('.bak'));
      const outMatch = trimmed.match(/tar\s+\S+\s+(\S+\.tar\.gz)/);
      const outName = normalizePath(outMatch?.[1] ?? 'backups.tar.gz');
      nextFiles[outName] = {
        perms: '-rw-r--r--',
        readable: true,
        content: bakFiles.join('\n'),
        size: `${bakFiles.length * 16}B`,
      };
      return {
        entries: [
          {
            type: 'system',
            text: `[tar] Створено архів ${outName} (${bakFiles.length} файлів .bak)`,
          },
        ],
      };
    }
  }

  // Handle ./run.sh
  if (trimmed === './run.sh' || trimmed === '/home/student/run.sh') {
    const script = nextFiles['run.sh'];
    if (!script) {
      return { entries: [{ type: 'err', text: 'bash: ./run.sh: No such file or directory' }] };
    }
    if (script.perms[3] !== 'x') {
      return { entries: [{ type: 'err', text: 'bash: ./run.sh: Permission denied' }] };
    }
    nextFiles['done.txt'] = {
      perms: '-rw-r--r--',
      readable: true,
      content: 'ok',
      size: '3B',
    };
    return {
      entries: [{ type: 'system', text: '[run.sh] Створено ~/done.txt (ok)' }],
    };
  }

  // Handle grep -c ... > file
  if (/^grep\s/.test(trimmed) && trimmed.includes('>')) {
    const redir = trimmed.match(/^(.+?)\s*(>>?)\s*(\S+)\s*$/);
    if (redir) {
      const [, left, , rawDst] = redir;
      const res = executeSingleCommand(left.trim(), nextFiles);
      const outText = res.entries
        .filter((e) => e.type === 'out')
        .map((e) => e.text)
        .join('\n');
      if (outText) {
        const dst = normalizePath(rawDst);
        nextFiles[dst] = {
          perms: '-rw-r--r--',
          readable: true,
          content: outText,
          size: `${outText.length}B`,
        };
        return { entries: [] };
      }
      return res;
    }
  }

  // Handle echo with > or >>
  if (/^echo(?:\s|$)/.test(trimmed)) {
    const redirMatch = trimmed.match(/^echo\s+([\s\S]*?)\s*(>>?)\s*(\S+)\s*$/);
    if (redirMatch) {
      const [, rawText, operator, rawTarget] = redirMatch;
      const targetFile = normalizePath(rawTarget);
      let content = rawText.trim();
      if (
        (content.startsWith('"') && content.endsWith('"') && content.length >= 2) ||
        (content.startsWith("'") && content.endsWith("'") && content.length >= 2)
      ) {
        content = content.slice(1, -1);
      }

      const finalContent =
        operator === '>>' && nextFiles[targetFile]
          ? `${nextFiles[targetFile].content}\n${content}`
          : content;

      nextFiles[targetFile] = {
        perms: nextFiles[targetFile]?.perms ?? '-rw-r--r--',
        readable: true,
        content: finalContent,
        size: `${finalContent.length}B`,
      };
      return { entries: [] };
    }

    const rest = trimmed.slice(4).trim();
    const unquoted =
      (rest.startsWith('"') && rest.endsWith('"') && rest.length >= 2) ||
      (rest.startsWith("'") && rest.endsWith("'") && rest.length >= 2)
        ? rest.slice(1, -1)
        : rest;
    return { entries: [{ type: 'out', text: unquoted }] };
  }

  const tokens = tokenize(trimmed);
  const [cmd, ...args] = tokens;

  switch (cmd) {
    case 'clear':
      return { entries: [], clear: true };

    case 'help':
      return {
        entries: [
          {
            type: 'out',
            text: [
              'Доступні команди (DEMO-симулятор):',
              '  ls [-a|-l|-la] [dir]     — список файлів',
              '  cat <file>               — вивести вміст файлу',
              '  chmod <mode> <file>      — змінити права (напр. 400, 700, +r)',
              '  grep [-i|-c] <pat> <f>   — пошук / підрахунок рядків',
              '  echo "<text>" > <file>   — записати текст у файл',
              '  mv <src> <dst>           — перемістити / перейменувати файл',
              '  find /srv/data -name ... — пошук файлів',
              '  ./run.sh                 — запустити скрипт',
              '  pwd / whoami / clear     — службові команди',
            ].join('\n'),
          },
        ],
      };

    case 'pwd':
      return { entries: [{ type: 'out', text: '/home/student' }] };

    case 'whoami':
      return { entries: [{ type: 'out', text: 'student' }] };

    case 'ls': {
      let showAll = false;
      let longFormat = false;
      let dirArg = '';
      for (const arg of args) {
        if (arg.startsWith('-')) {
          if (arg.includes('a')) showAll = true;
          if (arg.includes('l')) longFormat = true;
        } else {
          dirArg = arg;
        }
      }

      const prefix = dirArg === '/tmp' ? '/tmp/' : dirArg === '/var/log' ? '/var/log/' : '';
      const names = Object.keys(nextFiles)
        .filter((name) => {
          if (prefix) {
            if (!name.startsWith(prefix)) return false;
            const base = name.slice(prefix.length);
            return showAll || !base.startsWith('.');
          }
          if (name.startsWith('/')) return false;
          return showAll || !name.startsWith('.');
        })
        .sort();

      const displayNames = names.map((n) => (prefix ? n.slice(prefix.length) : n));

      if (longFormat) {
        const lines: string[] = [];
        if (showAll) {
          lines.push('drwxr-xr-x 1 student student   40B Nov 23 18:00 .');
          lines.push('drwxr-xr-x 1 root    root      40B Nov 23 18:00 ..');
        }
        names.forEach((full, idx) => {
          const f = nextFiles[full];
          lines.push(
            `${f.perms} 1 student student ${f.size.padStart(5)} Nov 23 18:00 ${displayNames[idx]}`
          );
        });
        return {
          entries: [{ type: 'out', text: lines.length > 0 ? lines.join('\n') : '(empty)' }],
        };
      }

      return {
        entries: [{ type: 'out', text: displayNames.length > 0 ? displayNames.join('  ') : '(empty)' }],
      };
    }

    case 'cat': {
      const rawTarget = args[0];
      if (!rawTarget) {
        return { entries: [{ type: 'err', text: 'cat: missing file operand' }] };
      }
      const target = normalizePath(rawTarget);
      const file = nextFiles[target] ?? nextFiles[rawTarget];
      if (!file) {
        return {
          entries: [{ type: 'err', text: `cat: ${rawTarget}: No such file or directory` }],
        };
      }
      if (!file.readable) {
        return {
          entries: [{ type: 'err', text: `cat: ${rawTarget}: Permission denied` }],
        };
      }
      return { entries: [{ type: 'out', text: file.content }] };
    }

    case 'chmod': {
      const [mode, rawTarget] = args;
      if (!mode || !rawTarget) {
        return { entries: [{ type: 'err', text: 'chmod: usage: chmod <mode> <file>' }] };
      }
      const target = normalizePath(rawTarget);
      const file = nextFiles[target];
      if (!file) {
        return {
          entries: [
            { type: 'err', text: `chmod: cannot access '${rawTarget}': No such file or directory` },
          ],
        };
      }
      const updated = applyChmod(mode, file.perms);
      if (!updated) {
        return { entries: [{ type: 'err', text: `chmod: invalid mode: '${mode}'` }] };
      }
      nextFiles[target] = {
        ...file,
        perms: updated.perms,
        readable: updated.readable,
      };
      return {
        entries: [{ type: 'system', text: `Права ${target} оновлено: ${updated.perms}` }],
      };
    }

    case 'grep': {
      let ignoreCase = false;
      let countOnly = false;
      const positional: string[] = [];
      for (const arg of args) {
        if (arg.startsWith('-')) {
          if (arg.includes('i')) ignoreCase = true;
          if (arg.includes('c')) countOnly = true;
        } else {
          positional.push(arg);
        }
      }
      const [pattern, rawTarget] = positional;
      if (!pattern || !rawTarget) {
        return { entries: [{ type: 'err', text: 'grep: usage: grep [-i|-c] <pattern> <file>' }] };
      }
      const target = normalizePath(rawTarget);
      const file = nextFiles[target] ?? nextFiles[rawTarget];
      if (!file) {
        return {
          entries: [{ type: 'err', text: `grep: ${rawTarget}: No such file or directory` }],
        };
      }
      if (!file.readable) {
        return { entries: [{ type: 'err', text: `grep: ${rawTarget}: Permission denied` }] };
      }
      const needle = ignoreCase ? pattern.toLowerCase() : pattern;
      const matched = file.content
        .split('\n')
        .filter((line) => (ignoreCase ? line.toLowerCase() : line).includes(needle));

      if (countOnly) {
        return { entries: [{ type: 'out', text: String(matched.length) }] };
      }
      return {
        entries: [
          matched.length > 0
            ? { type: 'out', text: matched.join('\n') }
            : { type: 'system', text: '(збігів не знайдено)' },
        ],
      };
    }

    case 'mv': {
      const [rawSrc, rawDst] = args;
      if (!rawSrc || !rawDst) {
        return { entries: [{ type: 'err', text: 'mv: usage: mv <source> <dest>' }] };
      }
      const src = normalizePath(rawSrc);
      const dst = normalizePath(rawDst);
      const file = nextFiles[src] ?? nextFiles[rawSrc];
      const srcKey = nextFiles[src] ? src : rawSrc;
      if (!file) {
        return {
          entries: [{ type: 'err', text: `mv: cannot stat '${rawSrc}': No such file or directory` }],
        };
      }
      nextFiles[dst] = { ...file };
      if (srcKey !== dst) {
        delete nextFiles[srcKey];
      }
      return {
        entries: [{ type: 'system', text: `Файл переміщено: ${rawSrc} → ${rawDst}` }],
      };
    }

    case 'find': {
      const bakFiles = Object.keys(nextFiles)
        .filter((k) => k.startsWith('/srv/data') && k.endsWith('.bak'))
        .sort();
      return {
        entries: [{ type: 'out', text: bakFiles.join('\n') || '(empty)' }],
      };
    }

    default:
      return {
        entries: [
          {
            type: 'err',
            text: `bash: ${cmd}: command not found у DEMO-режимі (введи 'help' або підключи Docker-бекенд)`,
          },
        ],
      };
  }
}

export function executeCommand(
  rawCmd: string,
  files: VirtualFileSystem,
  cwd = '/home/student'
): { entries: TerminalEntry[]; nextFiles: VirtualFileSystem; clear?: boolean } {
  const trimmed = rawCmd.trim();
  if (!trimmed) {
    return { entries: [], nextFiles: files };
  }

  const nextFiles = cloneFiles(files);
  const prompt = `student@sandbox:${cwd}$`;
  const cmdEntry: TerminalEntry = {
    type: 'cmd',
    prompt,
    text: trimmed,
  };

  // Support chaining with `&&`
  const parts = trimmed.split('&&').map((s) => s.trim()).filter(Boolean);
  const outEntries: TerminalEntry[] = [cmdEntry];
  let cleared = false;

  for (const part of parts) {
    const res = executeSingleCommand(part, nextFiles);
    if (res.clear) {
      cleared = true;
      outEntries.length = 0;
    } else {
      outEntries.push(...res.entries);
      if (res.entries.some((e) => e.type === 'err')) {
        break;
      }
    }
  }

  return { entries: outEntries, nextFiles, clear: cleared };
}

export function autocompleteInput(input: string, files: VirtualFileSystem): string {
  if (!input) return input;

  const hasTrailingSpace = /\s$/.test(input);
  const parts = input.split(/\s+/);

  if (parts.length === 1 && !hasTrailingSpace) {
    const prefix = parts[0];
    const match = KNOWN_COMMANDS.find((c) => c.startsWith(prefix));
    return match ? `${match} ` : input;
  }

  const lastToken = hasTrailingSpace ? '' : parts[parts.length - 1];
  const fileNames = Object.keys(files).sort();
  const match = fileNames.find((name) => name.startsWith(lastToken));
  if (!match) return input;

  if (hasTrailingSpace) {
    return `${input}${match}`;
  }

  parts[parts.length - 1] = match;
  return parts.join(' ');
}

export function checkDemoStep(
  slug: string,
  stepIdx: number,
  files: VirtualFileSystem
): { passed: boolean; message?: string } {
  switch (slug) {
    case 'perms':
      if (stepIdx === 0) {
        return {
          passed: Boolean(files['flag.txt']?.readable),
          message: 'Крок ще не виконано: файл ~/flag.txt досі нечитабельний.',
        };
      }
      return {
        passed: Boolean(
          files['run.sh']?.perms === '-rwx------' &&
            files['done.txt']?.content.trim() === 'ok'
        ),
        message: 'Крок ще не виконано: встанови chmod 700 run.sh і запусти ./run.sh.',
      };

    case 'needle':
      if (stepIdx === 0) {
        return {
          passed: files['answer.txt']?.content.trim() === 'super_secret_admin_pass',
          message: 'Крок ще не виконано: запиши значення пароля у ~/answer.txt.',
        };
      }
      return {
        passed: files['count.txt']?.content.trim() === '37',
        message: 'Крок ще не виконано: порахуй рядки ERROR у /var/log/app.log і запиши число в ~/count.txt.',
      };

    case 'hidden':
      if (stepIdx === 0) {
        return {
          passed: Boolean(
            !files['/tmp/.hidden_config_992.cfg'] &&
              files['visible.txt']?.content.trim() === 'hidden_marker_992'
          ),
          message: 'Крок ще не виконано: перемісти /tmp/.hidden_config_992.cfg у ~/visible.txt.',
        };
      }
      return {
        passed: Boolean(
          files['backups.tar.gz'] &&
            files['backups.tar.gz'].content.split('\n').filter((l) => l.endsWith('.bak')).length === 5
        ),
        message: 'Крок ще не виконано: створи ~/backups.tar.gz з усіма 5 файлами .bak.',
      };

    default:
      return {
        passed: false,
        message:
          'Цей сценарій потребує реального Docker-контейнера. Запусти Python-сервер бота для повної перевірки, або спробуй демо-завдання perms / needle / hidden.',
      };
  }
}

export function getQuickCommands(
  slug: string,
  stepIdx = 0
): Array<{ label: string; cmd: string }> {
  switch (slug) {
    case 'perms':
      return stepIdx === 0
        ? [
            { label: 'ls -l', cmd: 'ls -l' },
            { label: 'chmod 400 flag.txt', cmd: 'chmod 400 flag.txt' },
            { label: 'cat flag.txt', cmd: 'cat flag.txt' },
          ]
        : [
            { label: 'chmod 700 run.sh', cmd: 'chmod 700 run.sh' },
            { label: './run.sh', cmd: './run.sh' },
            { label: 'cat done.txt', cmd: 'cat done.txt' },
          ];
    case 'needle':
      return stepIdx === 0
        ? [
            { label: 'grep PASSWORD', cmd: 'grep PASSWORD /var/log/server.log' },
            { label: 'cut → answer.txt', cmd: 'grep PASSWORD /var/log/server.log | cut -d= -f2 > ~/answer.txt' },
          ]
        : [
            { label: 'grep -c ERROR', cmd: 'grep -c ERROR /var/log/app.log' },
            { label: 'save → count.txt', cmd: 'grep -c ERROR /var/log/app.log > ~/count.txt' },
          ];
    case 'hidden':
      return stepIdx === 0
        ? [
            { label: 'ls -a /tmp', cmd: 'ls -a /tmp' },
            { label: 'mv → ~/visible.txt', cmd: 'mv /tmp/.hidden_config_992.cfg ~/visible.txt' },
          ]
        : [
            { label: 'find *.bak', cmd: "find /srv/data -name '*.bak'" },
            { label: 'tar → backups.tar.gz', cmd: "find /srv/data -name '*.bak' | tar czf ~/backups.tar.gz -T -" },
          ];
    default:
      return [
        { label: 'ls -la', cmd: 'ls -la' },
        { label: 'pwd', cmd: 'pwd' },
        { label: 'whoami', cmd: 'whoami' },
      ];
  }
}
