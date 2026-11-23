import {
  CheckCircle2,
  ChevronRight,
  Cpu,
  EyeOff,
  Lock,
  Search,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import type {
  Difficulty,
  Task,
  TaskCategory,
  TaskIconName,
  TelegramUser,
} from '../types';
import { TASK_CATEGORIES } from '../data/tasks';
import { hapticImpact } from '../lib/telegram';

interface HubScreenProps {
  tasks: Task[];
  telegramUser: TelegramUser;
  userXp: number;
  selectedCategory: TaskCategory;
  onSelectCategory: (category: TaskCategory) => void;
  onSelectTask: (task: Task) => void;
}

const RANK_GOAL_XP = 1000;

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

function renderTaskIcon(icon: TaskIconName, solved: boolean) {
  const iconClass = `w-5 h-5 ${solved ? 'text-emerald-400' : 'text-cyan-400'}`;
  switch (icon) {
    case 'lock':
      return <Lock className={iconClass} />;
    case 'search':
      return <Search className={iconClass} />;
    case 'eye-off':
      return <EyeOff className={iconClass} />;
  }
}

export function HubScreen({
  tasks,
  telegramUser,
  userXp,
  selectedCategory,
  onSelectCategory,
  onSelectTask,
}: HubScreenProps) {
  const solvedCount = tasks.filter((task) => task.solved).length;
  const progressPercent = Math.min(100, Math.round((userXp / RANK_GOAL_XP) * 100));
  const filteredTasks =
    selectedCategory === 'Усі'
      ? tasks
      : tasks.filter((task) => task.category === selectedCategory);

  const handleCategoryClick = (category: TaskCategory) => {
    if (category === selectedCategory) return;
    hapticImpact('light');
    onSelectCategory(category);
  };

  const handleTaskClick = (task: Task) => {
    hapticImpact('light');
    onSelectTask(task);
  };

  return (
    <main className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {/* User Profile Card */}
      <section className="bg-[#0d141a]/90 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.08)] rounded-md p-4 relative overflow-hidden">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-11 h-11 rounded-md bg-emerald-500/15 border border-emerald-400/50 text-emerald-300 font-bold text-sm flex items-center justify-center shrink-0 shadow-[0_0_12px_rgba(16,185,129,0.2)]">
              {telegramUser.initials}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <h1 className="text-sm font-bold text-emerald-50 truncate">
                  {telegramUser.firstName}
                </h1>
                <span className="text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-500/30 shrink-0">
                  {telegramUser.isTelegram ? 'TG' : 'DEV'}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate">
                {telegramUser.username ? `@${telegramUser.username}` : 'Junior DevOps Engineer'}
              </p>
            </div>
          </div>

          <div className="text-right shrink-0">
            <div className="inline-flex items-center gap-1 text-sm font-bold text-emerald-400">
              <Zap className="w-4 h-4 fill-emerald-400/20" />
              <span>{userXp} XP</span>
            </div>
            <div className="text-[11px] text-slate-400">
              {solvedCount}/{tasks.length} вирішено
            </div>
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[10px] tracking-wider uppercase">
            <span className="text-emerald-400/80 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Прогрес до Middle DevOps</span>
            </span>
            <span className="text-slate-300 font-semibold">
              {Math.min(userXp, RANK_GOAL_XP)} / {RANK_GOAL_XP} XP
            </span>
          </div>
          <div className="h-2 w-full bg-[#040709] border border-emerald-500/25 rounded-sm overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 shadow-[0_0_10px_rgba(16,185,129,0.6)] transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </section>

      {/* Cluster Slots Telemetry Bar */}
      <section className="flex items-center justify-between px-3 py-2 rounded-md bg-[#090f14] border border-emerald-500/20 text-[11px]">
        <div className="flex items-center gap-2 text-slate-300">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>Активні контейнери</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-emerald-500/60 tracking-widest hidden sm:inline">
            NEON // MATRIX
          </span>
          <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/35 font-bold">
            18/20
          </span>
        </div>
      </section>

      {/* Category Filter Pills */}
      <section aria-label="Фільтр категорій">
        <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
          {TASK_CATEGORIES.map((category) => {
            const isActive = category === selectedCategory;
            return (
              <button
                key={category}
                type="button"
                onClick={() => handleCategoryClick(category)}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all cursor-pointer active:scale-95 ${
                  isActive
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                    : 'bg-[#0d141a] text-slate-400 border border-slate-800 hover:border-emerald-500/40 hover:text-emerald-200'
                }`}
              >
                {category}
              </button>
            );
          })}
        </div>
      </section>

      {/* Task Cards */}
      <section className="space-y-3 pb-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-widest text-emerald-400/80">
            Доступні сценарії ({filteredTasks.length})
          </h2>
          <span className="text-[10px] text-slate-500">Linux // Docker</span>
        </div>

        {filteredTasks.map((task) => (
          <button
            key={task.id}
            type="button"
            onClick={() => handleTaskClick(task)}
            className="w-full text-left bg-[#0d141a]/90 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.08)] rounded-md p-3.5 transition-all hover:border-emerald-400 hover:shadow-[0_0_20px_rgba(16,185,129,0.2)] active:scale-[0.99] cursor-pointer group"
          >
            <div className="flex items-start gap-3">
              <div
                className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 border ${
                  task.solved
                    ? 'bg-emerald-500/15 border-emerald-500/40'
                    : 'bg-cyan-950/50 border-cyan-500/30'
                }`}
              >
                {renderTaskIcon(task.icon, task.solved)}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <h3 className="text-sm font-bold text-emerald-50 group-hover:text-emerald-300 transition-colors truncate">
                    {task.title}
                  </h3>
                  {task.solved && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-400 shrink-0">
                      <CheckCircle2 className="w-4 h-4" />
                    </span>
                  )}
                </div>

                <p className="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-3">
                  {task.shortDesc}
                </p>

                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded ${getDifficultyClasses(
                        task.difficulty
                      )}`}
                    >
                      {task.difficulty}
                    </span>
                    <span className="text-[10px] text-cyan-400/80 bg-cyan-950/40 border border-cyan-500/20 px-2 py-0.5 rounded">
                      {task.category}
                    </span>
                  </div>

                  <div className="flex items-center gap-1 text-xs font-bold text-emerald-400 shrink-0">
                    <span>+{task.xp} XP</span>
                    <ChevronRight className="w-4 h-4 text-emerald-500/70 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </div>
              </div>
            </div>
          </button>
        ))}
      </section>
    </main>
  );
}
