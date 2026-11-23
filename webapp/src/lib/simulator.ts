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
];

export function cloneFiles(files: VirtualFileSystem): VirtualFileSystem {
  const copy: VirtualFileSystem = {};
  for (const [name, file] of Object.entries(files)) {
    copy[name] = { ...file };
  }
  return copy;
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
  if (!symbolicMatch) {
    return null;
  }

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

export function executeCommand(
  rawCmd: string,
  files: VirtualFileSystem
): { entries: TerminalEntry[]; nextFiles: VirtualFileSystem; clear?: boolean } {
  const trimmed = rawCmd.trim();
  if (!trimmed) {
    return { entries: [], nextFiles: files };
  }

  const nextFiles = cloneFiles(files);
  const cmdEntry: TerminalEntry = {
    type: 'cmd',
    text: `sandbox@devops:~$ ${trimmed}`,
  };

  // Handle echo with > or >> redirection before generic tokenization
  if (/^echo(?:\s|$)/.test(trimmed)) {
    const redirMatch = trimmed.match(/^echo\s+([\s\S]*?)\s*(>>?)\s*(\S+)\s*$/);
    if (redirMatch) {
      const [, rawText, operator, targetFile] = redirMatch;
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

      return {
        entries: [cmdEntry],
        nextFiles,
      };
    }

    const rest = trimmed.slice(4).trim();
    const unquoted =
      (rest.startsWith('"') && rest.endsWith('"') && rest.length >= 2) ||
      (rest.startsWith("'") && rest.endsWith("'") && rest.length >= 2)
        ? rest.slice(1, -1)
        : rest;

    return {
      entries: [cmdEntry, { type: 'out', text: unquoted }],
      nextFiles,
    };
  }

  const tokens = tokenize(trimmed);
  const [cmd, ...args] = tokens;

  switch (cmd) {
    case 'clear':
      return { entries: [], nextFiles, clear: true };

    case 'help':
      return {
        entries: [
          cmdEntry,
          {
            type: 'out',
            text: [
              'Доступні команди:',
              '  ls [-a|-l|-la]           — список файлів у директорії',
              '  cat <file>               — вивести вміст файлу',
              '  chmod <mode> <file>      — змінити права (напр. 400, 644, +r)',
              '  grep [-i] <pat> <file>   — пошук рядків у файлі',
              '  echo "<text>" > <file>   — записати текст у файл',
              '  mv <src> <dst>           — перейменувати файл',
              '  pwd / whoami / clear     — інформація та очищення екрану',
            ].join('\n'),
          },
        ],
        nextFiles,
      };

    case 'pwd':
      return {
        entries: [cmdEntry, { type: 'out', text: '/home/sandbox' }],
        nextFiles,
      };

    case 'whoami':
      return {
        entries: [cmdEntry, { type: 'out', text: 'sandbox' }],
        nextFiles,
      };

    case 'ls': {
      let showAll = false;
      let longFormat = false;
      for (const arg of args) {
        if (arg.startsWith('-')) {
          if (arg.includes('a')) showAll = true;
          if (arg.includes('l')) longFormat = true;
        }
      }

      const names = Object.keys(nextFiles)
        .filter((name) => showAll || !name.startsWith('.'))
        .sort();

      if (longFormat) {
        const lines: string[] = [];
        if (showAll) {
          lines.push('drwxr-xr-x 1 sandbox sandbox   40B Nov 23 18:00 .');
          lines.push('drwxr-xr-x 1 root    root      40B Nov 23 18:00 ..');
        }
        for (const name of names) {
          const f = nextFiles[name];
          lines.push(
            `${f.perms} 1 sandbox sandbox ${f.size.padStart(5)} Nov 23 18:00 ${name}`
          );
        }
        return {
          entries: [
            cmdEntry,
            { type: 'out', text: lines.length > 0 ? lines.join('\n') : '(empty)' },
          ],
          nextFiles,
        };
      }

      return {
        entries: [
          cmdEntry,
          { type: 'out', text: names.length > 0 ? names.join('  ') : '(empty)' },
        ],
        nextFiles,
      };
    }

    case 'cat': {
      const target = args[0];
      if (!target) {
        return {
          entries: [cmdEntry, { type: 'err', text: 'cat: missing file operand' }],
          nextFiles,
        };
      }
      const file = nextFiles[target];
      if (!file) {
        return {
          entries: [
            cmdEntry,
            { type: 'err', text: `cat: ${target}: No such file or directory` },
          ],
          nextFiles,
        };
      }
      if (!file.readable) {
        return {
          entries: [cmdEntry, { type: 'err', text: `cat: ${target}: Permission denied` }],
          nextFiles,
        };
      }
      return {
        entries: [cmdEntry, { type: 'out', text: file.content }],
        nextFiles,
      };
    }

    case 'chmod': {
      const [mode, target] = args;
      if (!mode || !target) {
        return {
          entries: [
            cmdEntry,
            { type: 'err', text: 'chmod: usage: chmod <mode> <file>' },
          ],
          nextFiles,
        };
      }
      const file = nextFiles[target];
      if (!file) {
        return {
          entries: [
            cmdEntry,
            {
              type: 'err',
              text: `chmod: cannot access '${target}': No such file or directory`,
            },
          ],
          nextFiles,
        };
      }
      const updated = applyChmod(mode, file.perms);
      if (!updated) {
        return {
          entries: [cmdEntry, { type: 'err', text: `chmod: invalid mode: '${mode}'` }],
          nextFiles,
        };
      }
      nextFiles[target] = {
        ...file,
        perms: updated.perms,
        readable: updated.readable,
      };
      return {
        entries: [
          cmdEntry,
          {
            type: 'system',
            text: `Права ${target} оновлено: ${updated.perms}`,
          },
        ],
        nextFiles,
      };
    }

    case 'grep': {
      let ignoreCase = false;
      const positional: string[] = [];
      for (const arg of args) {
        if (arg === '-i') {
          ignoreCase = true;
        } else {
          positional.push(arg);
        }
      }
      const [pattern, target] = positional;
      if (!pattern || !target) {
        return {
          entries: [
            cmdEntry,
            { type: 'err', text: 'grep: usage: grep [-i] <pattern> <file>' },
          ],
          nextFiles,
        };
      }
      const file = nextFiles[target];
      if (!file) {
        return {
          entries: [
            cmdEntry,
            { type: 'err', text: `grep: ${target}: No such file or directory` },
          ],
          nextFiles,
        };
      }
      if (!file.readable) {
        return {
          entries: [
            cmdEntry,
            { type: 'err', text: `grep: ${target}: Permission denied` },
          ],
          nextFiles,
        };
      }
      const needle = ignoreCase ? pattern.toLowerCase() : pattern;
      const matched = file.content
        .split('\n')
        .filter((line) => (ignoreCase ? line.toLowerCase() : line).includes(needle));

      return {
        entries: [
          cmdEntry,
          matched.length > 0
            ? { type: 'out', text: matched.join('\n') }
            : { type: 'system', text: '(збігів не знайдено)' },
        ],
        nextFiles,
      };
    }

    case 'mv': {
      const [src, dst] = args;
      if (!src || !dst) {
        return {
          entries: [cmdEntry, { type: 'err', text: 'mv: usage: mv <source> <dest>' }],
          nextFiles,
        };
      }
      const file = nextFiles[src];
      if (!file) {
        return {
          entries: [
            cmdEntry,
            {
              type: 'err',
              text: `mv: cannot stat '${src}': No such file or directory`,
            },
          ],
          nextFiles,
        };
      }
      nextFiles[dst] = { ...file };
      if (src !== dst) {
        delete nextFiles[src];
      }
      return {
        entries: [
          cmdEntry,
          { type: 'system', text: `Файл перейменовано: ${src} → ${dst}` },
        ],
        nextFiles,
      };
    }

    default:
      return {
        entries: [
          cmdEntry,
          {
            type: 'err',
            text: `bash: ${cmd}: command not found (введи 'help')`,
          },
        ],
        nextFiles,
      };
  }
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

export function checkTaskSolution(taskId: number, files: VirtualFileSystem): boolean {
  switch (taskId) {
    case 1:
      return Boolean(files['flag.txt']?.readable);
    case 2:
      return Boolean(
        files['answer.txt']?.readable &&
          files['answer.txt'].content.includes('super_secret_devops_pass')
      );
    case 3:
      return Boolean(
        files['visible.txt'] &&
          files['visible.txt'].content.includes('BACKDOOR_PORT=4444') &&
          !files['.hidden_config_992.cfg']
      );
    default:
      return false;
  }
}

export function getQuickCommands(taskId: number): Array<{ label: string; cmd: string }> {
  switch (taskId) {
    case 1:
      return [
        { label: 'ls -l', cmd: 'ls -l' },
        { label: 'cat flag.txt', cmd: 'cat flag.txt' },
        { label: 'chmod 400', cmd: 'chmod 400 flag.txt' },
      ];
    case 2:
      return [
        { label: 'ls -l', cmd: 'ls -l' },
        { label: 'grep PASSWORD', cmd: 'grep PASSWORD server.log' },
        { label: 'echo > answer.txt', cmd: 'echo "super_secret_devops_pass" > answer.txt' },
      ];
    case 3:
      return [
        { label: 'ls -la', cmd: 'ls -la' },
        { label: 'cat .hidden', cmd: 'cat .hidden_config_992.cfg' },
        { label: 'mv → visible.txt', cmd: 'mv .hidden_config_992.cfg visible.txt' },
      ];
    default:
      return [
        { label: 'ls -la', cmd: 'ls -la' },
        { label: 'help', cmd: 'help' },
      ];
  }
}
