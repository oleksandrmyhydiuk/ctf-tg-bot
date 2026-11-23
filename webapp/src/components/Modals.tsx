import {
  AlertTriangle,
  Award,
  CheckCircle2,
  Clock,
  Cpu,
  Home,
  Layers,
  Loader2,
  Play,
  Sparkles,
  Terminal,
  Trophy,
  X,
  Zap,
} from 'lucide-react';
import type { ActiveSession, Difficulty, Task, VictoryData } from '../types';
import { renderSafeBotHtml } from '../lib/safeHtml';
import { hapticImpact } from '../lib/telegram';

function getDifficultyClasses(difficulty: Difficulty): string {
  switch (difficulty) {
    case 'easy':
      return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/40';
    case 'medium':
      return 'bg-amber-500/15 text-amber-400 border border-amber-500/40';
    case 'hard':
      return 'bg-rose-500/15 text-rose-400 border border-rose-500/40';
  }
}

/* -------------------------------------------------------------------------- */
/* TaskPreviewModal                                                           */
/* -------------------------------------------------------------------------- */

interface TaskPreviewModalProps {
  task: Task | null;
  activeSession: ActiveSession | null;
  sessionTtl: number;
  starting: boolean;
  startError: string | null;
  onClose: () => void;
  onStart: (task: Task) => void;
  onResume: () => void;
}

export function TaskPreviewModal({
  task,
  activeSession,
  sessionTtl,
  starting,
  startError,
  onClose,
  onStart,
  onResume,
}: TaskPreviewModalProps) {
  if (!task) return null;

  const isSameActive = activeSession?.slug === task.slug;
  const hasOtherActive = Boolean(activeSession && !isSameActive);
  const ttlMinutes = Math.max(1, Math.round(sessionTtl / 60));

  const handleAction = () => {
    hapticImpact('medium');
    if (isSameActive) {
      onResume();
    } else {
      onStart(task);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-end justify-center"
      onClick={starting ? undefined : onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-[#0b1218] border-t border-x border-emerald-500/40 rounded-t-xl p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-[0_-10px_40px_rgba(16,185,129,0.18)] animate-slideUp space-y-4"
      >
        <div className="w-10 h-1 bg-emerald-500/30 rounded-full mx-auto -mt-1" />

        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-11 h-11 rounded-md bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center shrink-0">
              <Terminal className="w-5 h-5 text-emerald-400" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <h2 className="text-base font-bold text-emerald-50 truncate">
                  {task.title}
                </h2>
                {task.done && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                )}
              </div>
              <div className="flex items-center gap-1.5 flex-wrap mt-1">
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${getDifficultyClasses(
                    task.difficulty
                  )}`}
                >
                  {task.difficulty}
                </span>
                <span className="inline-flex items-center gap-0.5 text-[10px] text-slate-300 bg-[#090f14] border border-slate-800 px-1.5 py-0.5 rounded">
                  <Layers className="w-3 h-3 text-cyan-400" />
                  {task.stepsCount} кр.
                </span>
                <span className="text-xs font-bold text-emerald-400">
                  +{task.rewardPoints} б.
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={starting}
            aria-label="Закрити"
            className="p-1.5 rounded text-slate-400 hover:text-emerald-300 hover:bg-emerald-500/10 transition-colors cursor-pointer disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="bg-[#040709] border border-emerald-500/25 rounded-md p-3.5 text-xs text-slate-300 leading-relaxed max-h-40 overflow-y-auto">
          {renderSafeBotHtml(task.description)}
        </div>

        <div className="flex items-center justify-between px-3 py-2.5 rounded-md bg-[#090f14] border border-cyan-500/25 text-[11px]">
          <span className="flex items-center gap-1.5 text-cyan-300 font-semibold">
            <Cpu className="w-3.5 h-3.5" />
            <span>Контейнер</span>
          </span>
          <span className="text-slate-300 font-bold">
            {task.memLimit.toUpperCase()} RAM • {task.pidsLimit} PIDs • {ttlMinutes}m TTL
          </span>
        </div>

        {hasOtherActive && (
          <div className="px-3 py-2 rounded-md bg-amber-950/60 border border-amber-500/40 text-amber-200 text-[11px] flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              У вас уже активна сесія «{activeSession?.title}». Зупиніть її в терміналі, щоб запустити нове завдання.
            </span>
          </div>
        )}

        {startError && (
          <div className="px-3 py-2 rounded-md bg-rose-950/70 border border-rose-500/50 text-rose-200 text-[11px] flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{startError}</span>
          </div>
        )}

        <button
          type="button"
          onClick={handleAction}
          disabled={starting || hasOtherActive}
          className="w-full py-3 px-4 bg-emerald-500 text-black font-bold text-xs uppercase tracking-wider hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)] rounded-md flex items-center justify-center gap-2 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {starting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Готую Docker-середовище...</span>
            </>
          ) : isSameActive ? (
            <>
              <Play className="w-4 h-4 fill-black" />
              <span>Повернутися в термінал</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-black" />
              <span>Запустити пісочницю</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* HintModal                                                                  */
/* -------------------------------------------------------------------------- */

interface HintModalProps {
  isOpen: boolean;
  hint: string;
  currentReward: number;
  maxReward: number;
  onClose: () => void;
}

export function HintModal({
  isOpen,
  hint,
  currentReward,
  maxReward,
  onClose,
}: HintModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-[#0b1218] border border-cyan-500/40 rounded-md p-5 shadow-[0_0_30px_rgba(6,182,212,0.2)] animate-fadeIn space-y-4"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-cyan-300" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-cyan-200">Підказка кроку</h2>
              <span className="text-[10px] text-cyan-400/75 uppercase tracking-wider">
                Нагорода: {currentReward} / {maxReward} б.
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Закрити"
            className="p-1 text-slate-400 hover:text-cyan-300 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="bg-[#040709] border border-cyan-500/30 rounded-md p-3.5 text-xs text-emerald-100 leading-relaxed max-h-56 overflow-y-auto">
          {renderSafeBotHtml(hint)}
        </div>

        <p className="text-[10px] text-amber-400/90 text-center">
          Кожна підказка на окремому кроці зменшує нагороду на ~20% (мінімум 50% від базової).
        </p>

        <button
          type="button"
          onClick={() => {
            hapticImpact('light');
            onClose();
          }}
          className="w-full py-2.5 px-4 bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-900/60 rounded-md text-xs font-bold active:scale-[0.98] transition-all cursor-pointer"
        >
          Повернутися в термінал
        </button>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* VictoryModal                                                               */
/* -------------------------------------------------------------------------- */

interface VictoryModalProps {
  victory: VictoryData | null;
  onGoLeaderboard: () => void;
  onGoHub: () => void;
}

export function VictoryModal({
  victory,
  onGoLeaderboard,
  onGoHub,
}: VictoryModalProps) {
  if (!victory) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-[#0b1218] border border-emerald-400/60 rounded-md p-5 shadow-[0_0_40px_rgba(16,185,129,0.25)] animate-fadeIn space-y-4">
        <div className="text-center space-y-2">
          <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/15 border border-emerald-400/60 flex items-center justify-center shadow-[0_0_25px_rgba(16,185,129,0.35)]">
            <Award className="w-7 h-7 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-emerald-300 uppercase tracking-wider">
              Завдання виконано!
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">{victory.task.title}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <div className="bg-[#040709] border border-emerald-500/25 rounded-md p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-[10px] text-slate-400 uppercase tracking-wider mb-1">
              <Clock className="w-3 h-3 text-cyan-400" />
              <span>Час</span>
            </div>
            <div className="text-sm font-bold text-emerald-50">
              {victory.timeSpent}
            </div>
          </div>

          <div className="bg-[#040709] border border-emerald-500/25 rounded-md p-3 text-center">
            <div className="flex items-center justify-center gap-1 text-[10px] text-slate-400 uppercase tracking-wider mb-1">
              <Zap className="w-3 h-3 text-emerald-400" />
              <span>Нагорода</span>
            </div>
            <div className="text-sm font-bold text-emerald-400">
              +{victory.awardedPoints} б.
            </div>
          </div>
        </div>

        {victory.alreadySolved ? (
          <div className="bg-amber-950/50 border border-amber-500/40 rounded-md p-3 text-xs text-amber-200 text-center">
            Бали за неї вже були нараховані раніше. Загальний рахунок:{' '}
            <span className="font-bold text-amber-100">{victory.totalScore} б.</span>
          </div>
        ) : (
          <div className="bg-[#040709] border border-cyan-500/30 rounded-md p-3 text-xs text-slate-300 text-center">
            Нараховано{' '}
            <span className="font-bold text-emerald-400">
              +{victory.awardedPoints}
            </span>{' '}
            із {victory.maxPoints} балів. Загальний рахунок:{' '}
            <span className="font-bold text-cyan-300">{victory.totalScore} б.</span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2.5 pt-1">
          <button
            type="button"
            onClick={() => {
              hapticImpact('light');
              onGoHub();
            }}
            className="py-2.5 px-3 bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-900/60 rounded-md text-xs font-bold flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all cursor-pointer"
          >
            <Home className="w-3.5 h-3.5" />
            <span>На головну</span>
          </button>

          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              onGoLeaderboard();
            }}
            className="py-2.5 px-3 bg-emerald-500 text-black font-bold hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)] rounded-md text-xs flex items-center justify-center gap-1.5 active:scale-[0.98] transition-all cursor-pointer"
          >
            <Trophy className="w-3.5 h-3.5" />
            <span>Рейтинг</span>
          </button>
        </div>
      </div>
    </div>
  );
}
