import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  CornerDownLeft,
  Loader2,
  Sparkles,
  Square,
  Terminal as TerminalIcon,
  X,
} from 'lucide-react';
import type {
  ActiveSession,
  AppMode,
  Task,
  TerminalEntry,
  VirtualFileSystem,
} from '../types';
import { autocompleteInput, getQuickCommands } from '../lib/simulator';
import { renderSafeBotHtml } from '../lib/safeHtml';
import { hapticImpact } from '../lib/telegram';

interface SandboxScreenProps {
  mode: AppMode;
  task: Task;
  session: ActiveSession;
  entries: TerminalEntry[];
  demoFiles: VirtualFileSystem;
  isExecuting: boolean;
  isChecking: boolean;
  isHintLoading: boolean;
  isStopping: boolean;
  checkError: string | null;
  stepBanner: string | null;
  onDismissCheckError: () => void;
  onDismissStepBanner: () => void;
  onRunCommand: (cmd: string) => void;
  onClearTerminal: () => void;
  onInterrupt: (currentInput: string) => void;
  onOpenHint: () => void;
  onCheckStep: () => void;
  onStopSession: () => void;
}

const SPECIAL_KEYS = ['Tab', 'Ctrl+C', '|', '>', '~', '/', '-', '↑'] as const;

function formatTimer(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function SandboxScreen({
  mode,
  task,
  session,
  entries,
  demoFiles,
  isExecuting,
  isChecking,
  isHintLoading,
  isStopping,
  checkError,
  stepBanner,
  onDismissCheckError,
  onDismissStepBanner,
  onRunCommand,
  onClearTerminal,
  onInterrupt,
  onOpenHint,
  onCheckStep,
  onStopSession,
}: SandboxScreenProps) {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isStepOpen, setIsStepOpen] = useState(true);
  const [secondsLeft, setSecondsLeft] = useState(session.expiresIn);

  const terminalEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const quickCommands = useMemo(
    () => getQuickCommands(session.slug, session.step),
    [session.slug, session.step]
  );

  // Sync TTL when session updates
  useEffect(() => {
    setSecondsLeft(session.expiresIn);
  }, [session.expiresIn, session.slug]);

  // Expand step box automatically when advancing to a new step
  useEffect(() => {
    setIsStepOpen(true);
  }, [session.step, session.slug]);

  // Countdown TTL timer
  useEffect(() => {
    const timer = window.setInterval(() => {
      setSecondsLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  // Auto-scroll terminal output
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries, isExecuting]);

  const submitCommand = (rawCmd: string) => {
    const trimmed = rawCmd.trim();
    if (!trimmed || isExecuting || isStopping) return;

    hapticImpact('light');

    if (trimmed === 'clear') {
      onClearTerminal();
      setHistory((prev) => [trimmed, ...prev]);
      setHistoryIndex(-1);
      setInput('');
      return;
    }

    onRunCommand(trimmed);
    setHistory((prev) => [trimmed, ...prev]);
    setHistoryIndex(-1);
    setInput('');
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    submitCommand(input);
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
      const completed = autocompleteInput(input, demoFiles);
      if (completed !== input) {
        hapticImpact('light');
        setInput(completed);
      }
    }
  };

  const handleSpecialKey = (key: (typeof SPECIAL_KEYS)[number]) => {
    if (key === 'Tab') {
      hapticImpact('light');
      const completed = autocompleteInput(input, demoFiles);
      setInput(completed);
    } else if (key === 'Ctrl+C') {
      hapticImpact('medium');
      onInterrupt(input);
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

  const isLowTime = secondsLeft < 120;
  const promptText = `student@sandbox:${session.cwd}$`;

  return (
    <div className="flex-1 flex flex-col min-h-0 relative">
      {/* Task Header, TTL Timer & Stop Button */}
      <div className="bg-[#090f14] border-b border-emerald-500/20 px-3 py-2 flex items-center justify-between gap-2 shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <TerminalIcon className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <h1 className="text-xs font-bold text-emerald-50 truncate">
              {session.title}
            </h1>
          </div>
          <p className="text-[10px] text-slate-400 truncate mt-0.5">
            {mode === 'api' ? 'docker' : 'local'}://{session.slug} • {task.category} •{' '}
            <span className="text-emerald-400 font-semibold">
              {session.currentReward}/{session.rewardPoints} б.
            </span>
          </p>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <div
            className={`inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-bold border transition-colors ${
              isLowTime
                ? 'bg-rose-500/15 text-rose-400 border-rose-500/50 animate-pulse'
                : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/35'
            }`}
          >
            <Clock className="w-3 h-3" />
            <span>{formatTimer(secondsLeft)}</span>
          </div>

          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              onStopSession();
            }}
            disabled={isStopping}
            title="Зупинити контейнер (/stop)"
            className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-bold bg-rose-500/10 text-rose-300 border border-rose-500/40 hover:bg-rose-500/20 active:scale-95 transition-all cursor-pointer disabled:opacity-50"
          >
            {isStopping ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Square className="w-2.5 h-2.5 fill-rose-300" />
            )}
            <span>Stop</span>
          </button>
        </div>
      </div>

      {/* Multi-Step Progress Bar & Current Step Instructions */}
      <div className="bg-[#0b1218] border-b border-emerald-500/20 shrink-0">
        <button
          type="button"
          onClick={() => {
            hapticImpact('light');
            setIsStepOpen((prev) => !prev);
          }}
          className="w-full px-3 py-2 flex items-center justify-between gap-2 text-[11px] font-semibold text-cyan-300 hover:bg-emerald-500/5 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span className="text-emerald-400 font-bold shrink-0">
              Крок {session.step + 1}/{session.totalSteps}
            </span>
            <div className="flex items-center gap-1 flex-1 max-w-[140px]">
              {Array.from({ length: session.totalSteps }, (_, idx) => (
                <span
                  key={idx}
                  className={`h-1.5 flex-1 rounded-full transition-all ${
                    idx < session.step
                      ? 'bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)]'
                      : idx === session.step
                        ? 'bg-cyan-400 shadow-[0_0_6px_rgba(34,211,238,0.6)]'
                        : 'bg-slate-800'
                  }`}
                />
              ))}
            </div>
          </div>

          <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 shrink-0">
            <span>{isStepOpen ? 'Сховати' : 'Умова'}</span>
            {isStepOpen ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </span>
        </button>

        {isStepOpen && (
          <div className="px-3 pb-2.5 pt-1 text-xs text-slate-200 leading-relaxed border-t border-emerald-500/10 max-h-36 overflow-y-auto animate-fadeIn">
            {renderSafeBotHtml(session.stepText)}
          </div>
        )}
      </div>

      {/* Step Passed Banner */}
      {stepBanner && (
        <div
          role="status"
          className="mx-3 mt-2 px-3 py-2 rounded-md bg-emerald-950/90 border border-emerald-400/60 text-emerald-200 text-[11px] flex items-center gap-2 shadow-[0_0_18px_rgba(16,185,129,0.2)] animate-fadeIn shrink-0"
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <p className="flex-1 leading-snug">{stepBanner}</p>
          <button
            type="button"
            onClick={onDismissStepBanner}
            aria-label="Закрити"
            className="text-emerald-300 hover:text-white cursor-pointer p-0.5"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

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
            onClick={onDismissCheckError}
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
              return (
                <div key={idx} className="break-all">
                  <span className="text-cyan-400 select-none">
                    {entry.prompt ?? promptText}
                  </span>{' '}
                  <span className="text-emerald-50">{entry.text}</span>
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

          {isExecuting && (
            <div className="inline-flex items-center gap-1.5 text-cyan-400/80 text-[11px]">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Виконую команду...</span>
            </div>
          )}

          <div ref={terminalEndRef} />
        </div>

        {/* Inline Prompt Form */}
        <form
          onSubmit={handleSubmit}
          className="px-3 py-2 border-t border-emerald-500/20 bg-[#060a0d] flex items-center gap-1.5 shrink-0"
        >
          <span className="text-cyan-400 text-[11px] shrink-0 select-none max-w-[45%] truncate">
            {promptText}
          </span>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleInputKeyDown}
            disabled={isExecuting || isStopping}
            placeholder="введіть команду..."
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            className="flex-1 min-w-0 bg-transparent text-emerald-50 text-xs outline-none caret-emerald-400 placeholder:text-slate-600 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isExecuting || isStopping}
            aria-label="Виконати команду"
            className="p-1.5 rounded bg-emerald-500/15 border border-emerald-500/35 text-emerald-300 hover:bg-emerald-500/25 active:scale-95 transition-all cursor-pointer shrink-0 disabled:opacity-50"
          >
            {isExecuting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <CornerDownLeft className="w-3.5 h-3.5" />
            )}
          </button>
        </form>
      </div>

      {/* Quick Command Chips */}
      {quickCommands.length > 0 && (
        <div className="bg-[#070b0e] border-b border-emerald-500/15 px-3 py-1.5 flex items-center gap-1.5 overflow-x-auto no-scrollbar shrink-0">
          <span className="text-[9px] uppercase tracking-widest text-slate-500 shrink-0 mr-0.5">
            Швидко:
          </span>
          {quickCommands.map((item) => (
            <button
              key={item.cmd}
              type="button"
              disabled={isExecuting || isStopping}
              onClick={() => submitCommand(item.cmd)}
              className="px-2.5 py-1 rounded bg-[#0d141a] border border-emerald-500/25 text-[11px] text-emerald-300 hover:border-emerald-400 hover:bg-emerald-500/10 whitespace-nowrap active:scale-95 transition-all cursor-pointer shrink-0 disabled:opacity-40"
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
          onClick={() => {
            hapticImpact('light');
            onOpenHint();
          }}
          disabled={!session.hasHint || isHintLoading || isStopping}
          className="py-2.5 px-3 bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-900/60 rounded-md text-xs font-semibold flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed"
        >
          {isHintLoading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
          ) : (
            <Sparkles className="w-3.5 h-3.5 shrink-0" />
          )}
          <span className="truncate">
            {!session.hasHint
              ? 'Без підказки'
              : session.hintUsed
                ? 'Підказка (відкрито)'
                : 'Підказка (-20%)'}
          </span>
        </button>

        <button
          type="button"
          onClick={() => {
            hapticImpact('medium');
            onCheckStep();
          }}
          disabled={isChecking || isExecuting || isStopping}
          className="py-2.5 px-3 bg-emerald-500 text-black font-bold hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)] rounded-md text-xs flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50"
        >
          {isChecking ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
              <span className="truncate">Перевіряю...</span>
            </>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span className="truncate">
                Перевірити ({session.step + 1}/{session.totalSteps})
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
