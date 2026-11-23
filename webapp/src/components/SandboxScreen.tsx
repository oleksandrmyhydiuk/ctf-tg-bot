import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  CornerDownLeft,
  Sparkles,
  Terminal as TerminalIcon,
  X,
} from 'lucide-react';
import type { Task, TerminalEntry, VirtualFileSystem } from '../types';
import {
  autocompleteInput,
  checkTaskSolution,
  cloneFiles,
  executeCommand,
  getQuickCommands,
} from '../lib/simulator';
import { hapticImpact, hapticNotification } from '../lib/telegram';

interface SandboxScreenProps {
  task: Task;
  hintUsed: boolean;
  onOpenHint: () => void;
  onTaskSolved: (timeSpentSeconds: number) => void;
}

const INITIAL_TTL_SECONDS = 14 * 60 + 32; // 14:32
const SPECIAL_KEYS = ['Tab', 'Ctrl+C', '|', '>', '~', '/', '-', '↑'] as const;

function formatTimer(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function buildInitialEntries(task: Task): TerminalEntry[] {
  return [
    {
      type: 'system',
      text: `[docker] Ініціалізація контейнера ctf-node-${task.id} (128MB RAM / 0.5 CPU)...`,
    },
    {
      type: 'system',
      text: `[ok] З'єднання встановлено. Введіть 'help' або 'ls -la' для початку.`,
    },
  ];
}

export function SandboxScreen({
  task,
  hintUsed,
  onOpenHint,
  onTaskSolved,
}: SandboxScreenProps) {
  const [files, setFiles] = useState<VirtualFileSystem>(() =>
    cloneFiles(task.initialFiles)
  );
  const [entries, setEntries] = useState<TerminalEntry[]>(() =>
    buildInitialEntries(task)
  );
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isLoreOpen, setIsLoreOpen] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(INITIAL_TTL_SECONDS);
  const [checkError, setCheckError] = useState<string | null>(null);

  const terminalEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const quickCommands = useMemo(() => getQuickCommands(task.id), [task.id]);

  // Reset sandbox state if task changes
  useEffect(() => {
    setFiles(cloneFiles(task.initialFiles));
    setEntries(buildInitialEntries(task));
    setInput('');
    setHistory([]);
    setHistoryIndex(-1);
    setIsLoreOpen(false);
    setSecondsLeft(INITIAL_TTL_SECONDS);
    setCheckError(null);
  }, [task]);

  // Countdown TTL timer (14:32 -> 00:00)
  useEffect(() => {
    const timer = window.setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  // Auto-scroll terminal output
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries]);

  // Auto-dismiss check error toast
  useEffect(() => {
    if (!checkError) return;
    const timeout = window.setTimeout(() => setCheckError(null), 4500);
    return () => window.clearTimeout(timeout);
  }, [checkError]);

  const runCommand = (rawCmd: string) => {
    const trimmed = rawCmd.trim();
    if (!trimmed) return;

    hapticImpact('light');
    setCheckError(null);

    const result = executeCommand(trimmed, files);
    setFiles(result.nextFiles);

    if (result.clear) {
      setEntries([]);
    } else {
      setEntries((prev) => [...prev, ...result.entries]);
    }

    setHistory((prev) => [trimmed, ...prev]);
    setHistoryIndex(-1);
    setInput('');
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    runCommand(input);
    inputRef.current?.focus();
  };

  const navigateHistoryUp = () => {
    if (history.length === 0) return;
    const nextIdx = Math.min(historyIndex + 1, history.length - 1);
    setHistoryIndex(nextIdx);
    setInput(history[nextIdx]);
  };

  const navigateHistoryDown = () => {
    if (historyIndex <= 0) {
      setHistoryIndex(-1);
      setInput('');
      return;
    }
    const nextIdx = historyIndex - 1;
    setHistoryIndex(nextIdx);
    setInput(history[nextIdx]);
  };

  const handleInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      navigateHistoryUp();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      navigateHistoryDown();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const completed = autocompleteInput(input, files);
      if (completed !== input) {
        hapticImpact('light');
        setInput(completed);
      }
    }
  };

  const handleSpecialKey = (key: (typeof SPECIAL_KEYS)[number]) => {
    if (key === 'Tab') {
      hapticImpact('light');
      const completed = autocompleteInput(input, files);
      setInput(completed);
    } else if (key === 'Ctrl+C') {
      hapticImpact('medium');
      setEntries((prev) => [
        ...prev,
        { type: 'cmd', text: `sandbox@devops:~$ ${input}^C` },
      ]);
      setInput('');
      setHistoryIndex(-1);
    } else if (key === '↑') {
      hapticImpact('light');
      navigateHistoryUp();
    } else {
      hapticImpact('light');
      setInput((prev) => prev + key);
    }
    inputRef.current?.focus();
  };

  const handleCheckSolution = () => {
    const passed = checkTaskSolution(task.id, files);
    if (passed) {
      hapticNotification('success');
      const elapsed = Math.max(1, INITIAL_TTL_SECONDS - secondsLeft);
      onTaskSolved(elapsed);
    } else {
      hapticNotification('error');
      setCheckError(
        'Умову завдання ще не виконано. Перевірте файли, права доступу або скористайтесь AI Підказкою.'
      );
    }
  };

  const handleOpenHint = () => {
    hapticImpact('light');
    onOpenHint();
  };

  const isLowTime = secondsLeft < 120;

  return (
    <div className="flex-1 flex flex-col min-h-0 relative">
      {/* Task Header & TTL Timer */}
      <div className="bg-[#090f14] border-b border-emerald-500/20 px-3.5 py-2.5 flex items-center justify-between gap-2 shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <TerminalIcon className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <h1 className="text-xs font-bold text-emerald-50 truncate">
              {task.title}
            </h1>
          </div>
          <p className="text-[10px] text-slate-400 truncate mt-0.5">
            docker://ctf-node-{task.id} • {task.category}
          </p>
        </div>

        <div
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-bold shrink-0 border transition-colors ${
            isLowTime
              ? 'bg-rose-500/15 text-rose-400 border-rose-500/50 animate-pulse'
              : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/35'
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          <span>{formatTimer(secondsLeft)}</span>
        </div>
      </div>

      {/* Collapsible Lore / Objective Accordion */}
      <div className="bg-[#0b1218] border-b border-emerald-500/20 shrink-0">
        <button
          type="button"
          onClick={() => {
            hapticImpact('light');
            setIsLoreOpen((prev) => !prev);
          }}
          className="w-full px-3.5 py-2 flex items-center justify-between text-[11px] font-semibold text-cyan-300 hover:bg-emerald-500/5 transition-colors cursor-pointer"
        >
          <span className="flex items-center gap-1.5">
            <span className="text-emerald-400">&gt;</span>
            <span>Мета завдання та опис</span>
          </span>
          {isLoreOpen ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </button>

        {isLoreOpen && (
          <div className="px-3.5 pb-3 pt-0.5 text-xs text-slate-300 leading-relaxed border-t border-emerald-500/10 animate-fadeIn">
            {task.loreDesc}
          </div>
        )}
      </div>

      {/* Check Error Toast */}
      {checkError && (
        <div
          role="alert"
          className="mx-3 mt-2 px-3 py-2 rounded-md bg-rose-950/90 border border-rose-500/50 text-rose-200 text-[11px] flex items-start gap-2 shadow-[0_0_20px_rgba(244,63,94,0.2)] animate-fadeIn shrink-0"
        >
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <p className="flex-1 leading-snug">{checkError}</p>
          <button
            type="button"
            onClick={() => setCheckError(null)}
            aria-label="Закрити сповіщення"
            className="text-rose-300 hover:text-white cursor-pointer p-0.5"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Interactive Terminal */}
      <div
        onClick={() => inputRef.current?.focus()}
        className="flex-1 flex flex-col min-h-0 bg-[#040709] border-y border-emerald-500/30 cursor-text"
      >
        <div className="flex-1 overflow-y-auto px-3 py-2.5 text-xs leading-relaxed space-y-1.5 font-mono">
          {entries.map((entry, idx) => {
            if (entry.type === 'cmd') {
              const promptPrefix = 'sandbox@devops:~$ ';
              const hasPrefix = entry.text.startsWith(promptPrefix);
              const cmdBody = hasPrefix
                ? entry.text.slice(promptPrefix.length)
                : entry.text;
              return (
                <div key={idx} className="break-all">
                  <span className="text-cyan-400 select-none">
                    sandbox@devops:~$
                  </span>{' '}
                  <span className="text-emerald-50">{cmdBody}</span>
                </div>
              );
            }
            if (entry.type === 'err') {
              return (
                <pre
                  key={idx}
                  className="text-rose-400 whitespace-pre-wrap break-words font-mono"
                >
                  {entry.text}
                </pre>
              );
            }
            if (entry.type === 'system') {
              return (
                <div
                  key={idx}
                  className="text-slate-400 text-[11px] leading-snug"
                >
                  {entry.text}
                </div>
              );
            }
            return (
              <pre
                key={idx}
                className="text-emerald-400 whitespace-pre-wrap break-words font-mono"
              >
                {entry.text}
              </pre>
            );
          })}
          <div ref={terminalEndRef} />
        </div>

        {/* Inline Prompt Form */}
        <form
          onSubmit={handleSubmit}
          className="px-3 py-2 border-t border-emerald-500/20 bg-[#060a0d] flex items-center gap-1.5 shrink-0"
        >
          <span className="text-cyan-400 text-xs shrink-0 select-none">
            sandbox@devops:~$
          </span>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="введіть команду..."
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            className="flex-1 min-w-0 bg-transparent text-emerald-50 text-xs outline-none caret-emerald-400 placeholder:text-slate-600"
          />
          <button
            type="submit"
            aria-label="Виконати команду"
            className="p-1.5 rounded bg-emerald-500/15 border border-emerald-500/35 text-emerald-300 hover:bg-emerald-500/25 active:scale-95 transition-all cursor-pointer shrink-0"
          >
            <CornerDownLeft className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>

      {/* Quick-test Command Chips */}
      {quickCommands.length > 0 && (
        <div className="bg-[#070b0e] border-b border-emerald-500/15 px-3 py-1.5 flex items-center gap-1.5 overflow-x-auto no-scrollbar shrink-0">
          <span className="text-[9px] uppercase tracking-widest text-slate-500 shrink-0 mr-0.5">
            Швидко:
          </span>
          {quickCommands.map((item) => (
            <button
              key={item.cmd}
              type="button"
              onClick={() => runCommand(item.cmd)}
              className="px-2.5 py-1 rounded bg-[#0d141a] border border-emerald-500/25 text-[11px] text-emerald-300 hover:border-emerald-400 hover:bg-emerald-500/10 whitespace-nowrap active:scale-95 transition-all cursor-pointer shrink-0"
            >
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* Mobile Special-Keys Toolbar */}
      <div className="bg-[#080d12] border-b border-emerald-500/20 px-2.5 py-1.5 flex items-center gap-1.5 overflow-x-auto no-scrollbar shrink-0">
        {SPECIAL_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => handleSpecialKey(key)}
            className="px-2.5 py-1.5 min-w-[34px] rounded bg-[#0d141a] border border-slate-700/80 text-[11px] font-bold text-cyan-300 hover:border-cyan-400/60 hover:bg-cyan-950/50 active:scale-95 transition-all cursor-pointer shrink-0"
          >
            {key}
          </button>
        ))}
      </div>

      {/* Bottom Action Bar */}
      <div className="bg-[#090f14] px-3 pt-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom))] grid grid-cols-2 gap-2.5 shrink-0">
        <button
          type="button"
          onClick={handleOpenHint}
          className="py-2.5 px-3 bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-900/60 rounded-md text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all cursor-pointer"
        >
          <Sparkles className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate">
            {hintUsed ? 'AI Підказка' : 'AI Підказка (-10%)'}
          </span>
        </button>

        <button
          type="button"
          onClick={handleCheckSolution}
          className="py-2.5 px-3 bg-emerald-500 text-black font-bold hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)] rounded-md text-xs flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all cursor-pointer"
        >
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span className="truncate">Check завдання</span>
        </button>
      </div>
    </div>
  );
}
