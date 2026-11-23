import {
  Award,
  Bot,
  Clock,
  Cpu,
  EyeOff,
  Home,
  Lock,
  Play,
  Search,
  Sparkles,
  Trophy,
  X,
  Zap,
} from 'lucide-react';
import type { Difficulty, Task, TaskIconName, VictoryData } from '../types';
import { hapticImpact } from '../lib/telegram';

function getDifficultyClasses(difficulty: Difficulty): string {
  switch (difficulty) {
    case 'Easy':
      return 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/40';
    case 'Medium':
      return 'bg-amber-500/15 text-amber-400 border border-amber-500/40';
    case 'Hard':
      return 'bg-rose-500/15 text-rose-400 border border-rose-500/40';
  }
}

function renderTaskIcon(icon: TaskIconName) {
  const cls = 'w-5 h-5 text-emerald-400';
  switch (icon) {
    case 'lock':
      return <Lock className={cls} />;
    case 'search':
      return <Search className={cls} />;
    case 'eye-off':
      return <EyeOff className={cls} />;
  }
}

/* -------------------------------------------------------------------------- */
/* TaskPreviewModal                                                           */
/* -------------------------------------------------------------------------- */

interface TaskPreviewModalProps {
  task: Task | null;
  onClose: () => void;
  onStart: (task: Task) => void;
}

export function TaskPreviewModal({
  task,
  onClose,
  onStart,
}: TaskPreviewModalProps) {
  if (!task) return null;

  const handleStart = () => {
    hapticImpact('medium');
    onStart(task);
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-end justify-center"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md bg-[#0b1218] border-t border-x border-emerald-500/40 rounded-t-xl p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-[0_-10px_40px_rgba(16,185,129,0.18)] animate-slideUp space-y-4"
      >
        <div className="w-10 h-1 bg-emerald-500/30 rounded-full mx-auto -mt-1" />

        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-11 h-11 rounded-md bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center shrink-0">
              {renderTaskIcon(task.icon)}
            </div>
            <div className="min-w-0">
              <h2 className="text-base font-bold text-emerald-50 truncate">
                {task.title}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded ${getDifficultyClasses(
                    task.difficulty
                  )}`}
                >
                  {task.difficulty}
                </span>
                <span className="text-xs font-bold text-emerald-400">
                  +{task.xp} XP
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Закрити"
            className="p-1.5 rounded text-slate-400 hover:text-emerald-300 hover:bg-emerald-500/10 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="bg-[#040709] border border-emerald-500/25 rounded-md p-3.5 text-xs text-slate-300 leading-relaxed">
          {task.loreDesc}
        </div>

        <div className="flex items-center justify-between px-3 py-2.5 rounded-md bg-[#090f14] border border-cyan-500/25 text-[11px]">
          <span className="flex items-center gap-1.5 text-cyan-300 font-semibold">
            <Cpu className="w-3.5 h-3.5" />
            <span>Ресурси контейнера</span>
          </span>
          <span className="text-slate-300 font-bold">
            128MB RAM • 0.5 CPU • 15m TTL
          </span>
        </div>

        <button
          type="button"
          onClick={handleStart}
          className="w-full py-3 px-4 bg-emerald-500 text-black font-bold text-xs uppercase tracking-wider hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)] rounded-md flex items-center justify-center gap-2 active:scale-[0.98] transition-all cursor-pointer"
        >
          <Play className="w-4 h-4 fill-black" />
          <span>Запустити пісочницю</span>
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
  onClose: () => void;
}

export function HintModal({ isOpen, hint, onClose }: HintModalProps) {
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
              <h2 className="text-sm font-bold text-cyan-200">AI-Ментор</h2>
              <span className="text-[10px] text-cyan-400/75 uppercase tracking-wider">
                Gemini Flash // Підказка
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

        <div className="bg-[#040709] border border-cyan-500/30 rounded-md p-3.5 text-xs text-emerald-100 leading-relaxed">
          {hint}
        </div>

        <p className="text-[10px] text-amber-400/90 text-center">
          Активовано штраф -10% XP до нагороди за це завдання.
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
              +{victory.earnedXp} XP
            </div>
          </div>
        </div>

        <div className="bg-[#040709] border border-cyan-500/30 rounded-md p-3.5 space-y-1.5">
          <div className="flex items-center gap-1.5 text-[11px] font-bold text-cyan-300 uppercase tracking-wider">
            <Bot className="w-3.5 h-3.5" />
            <span>AI Code Review</span>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed">
            {victory.task.review}
          </p>
        </div>

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
