import { useMemo, useState } from 'react';
import {
  CheckCircle2,
  ChevronRight,
  Cpu,
  Database,
  Globe,
  KeyRound,
  Layers,
  Play,
  Search,
  Shield,
  ShieldCheck,
  Terminal,
  Users,
  X,
  Zap,
} from 'lucide-react';
import type {
  ActiveSession,
  AppMode,
  ClusterSlots,
  Difficulty,
  Task,
  TaskCategory,
  TelegramUser,
} from '../types';
import { getRankTier } from '../lib/scoring';
import { stripBotHtml } from '../lib/safeHtml';
import { hapticImpact } from '../lib/telegram';

interface HubScreenProps {
  mode: AppMode;
  tasks: Task[];
  categories: TaskCategory[];
  telegramUser: TelegramUser;
  userScore: number;
  maxScore: number;
  userRank: number | null;
  slots: ClusterSlots;
  activeSession: ActiveSession | null;
  selectedCategory: TaskCategory;
  onSelectCategory: (category: TaskCategory) => void;
  onSelectTask: (task: Task) => void;
  onResumeSession: () => void;
}

type DifficultyFilter = 'all' | Difficulty;

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

function getDifficultyLabel(difficulty: Difficulty): string {
  switch (difficulty) {
    case 'easy':
      return 'EASY';
    case 'medium':
      return 'MEDIUM';
    case 'hard':
      return 'HARD';
  }
}

function renderCategoryIcon(category: string, done: boolean) {
  const cls = `w-5 h-5 ${done ? 'text-emerald-400' : 'text-cyan-400'}`;
  const lower = category.toLowerCase();
  if (lower.includes('баз') || lower.includes('db') || lower.includes('sql')) {
    return <Database className={cls} />;
  }
  if (lower.includes('веб') || lower.includes('web') || lower.includes('мереж') || lower.includes('net')) {
    return <Globe className={cls} />;
  }
  if (lower.includes('крипт') || lower.includes('crypto') || lower.includes('секрет')) {
    return <KeyRound className={cls} />;
  }
  if (lower.includes('груп') || lower.includes('coop') || lower.includes('team')) {
    return <Users className={cls} />;
  }
  if (lower.includes('безпек') || lower.includes('sec') || lower.includes('forensic') || lower.includes('привіл')) {
    return <Shield className={cls} />;
  }
  return <Terminal className={cls} />;
}

function formatTtlShort(seconds: number): string {
  const clamped = Math.max(0, seconds);
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function HubScreen({
  mode,
  tasks,
  categories,
  telegramUser,
  userScore,
  maxScore,
  userRank,
  slots,
  activeSession,
  selectedCategory,
  onSelectCategory,
  onSelectTask,
  onResumeSession,
}: HubScreenProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [difficultyFilter, setDifficultyFilter] = useState<DifficultyFilter>('all');

  const solvedCount = useMemo(
    () => tasks.filter((task) => task.done).length,
    [tasks]
  );

  const rankTier = useMemo(
    () => getRankTier(userScore, maxScore),
    [userScore, maxScore]
  );

  const filteredTasks = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return tasks.filter((task) => {
      if (selectedCategory !== 'Усі' && task.category !== selectedCategory) {
        return false;
      }
      if (difficultyFilter !== 'all' && task.difficulty !== difficultyFilter) {
        return false;
      }
      if (q) {
        const plainDesc = stripBotHtml(task.description).toLowerCase();
        return (
          task.title.toLowerCase().includes(q) ||
          task.slug.toLowerCase().includes(q) ||
          task.category.toLowerCase().includes(q) ||
          plainDesc.includes(q)
        );
      }
      return true;
    });
  }, [tasks, selectedCategory, difficultyFilter, searchQuery]);

  const handleCategoryClick = (category: TaskCategory) => {
    if (category === selectedCategory) return;
    hapticImpact('light');
    onSelectCategory(category);
  };

  const handleDifficultyClick = (diff: DifficultyFilter) => {
    if (diff === difficultyFilter) return;
    hapticImpact('light');
    setDifficultyFilter(diff);
  };

  const handleTaskClick = (task: Task) => {
    hapticImpact('light');
    onSelectTask(task);
  };

  return (
    <main className="flex-1 overflow-y-auto px-4 py-4 space-y-3.5">
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
                {userRank !== null && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/35 shrink-0">
                    #{userRank}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 truncate">
                {rankTier.title}
                {telegramUser.username ? ` • @${telegramUser.username}` : ''}
              </p>
            </div>
          </div>

          <div className="text-right shrink-0">
            <div className="inline-flex items-center gap-1 text-sm font-bold text-emerald-400">
              <Zap className="w-4 h-4 fill-emerald-400/20" />
              <span>{userScore} б.</span>
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
              <span>
                {rankTier.nextTitle
                  ? `До ${rankTier.nextTitle}`
                  : 'Максимальний ранг'}
              </span>
            </span>
            <span className="text-slate-300 font-semibold">
              {userScore} / {rankTier.nextTargetScore ?? maxScore} б.
            </span>
          </div>
          <div className="h-2 w-full bg-[#040709] border border-emerald-500/25 rounded-sm overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 shadow-[0_0_10px_rgba(16,185,129,0.6)] transition-all duration-500"
              style={{ width: `${rankTier.progressPercent}%` }}
            />
          </div>
        </div>
      </section>

      {/* Active Session Resume Banner */}
      {activeSession && (
        <section className="bg-emerald-950/40 border border-emerald-400/60 shadow-[0_0_18px_rgba(16,185,129,0.18)] rounded-md p-3 flex items-center justify-between gap-3 animate-fadeIn">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-emerald-400">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Активна сесія</span>
            </div>
            <p className="text-xs font-bold text-emerald-50 truncate mt-0.5">
              {activeSession.title}
            </p>
            <p className="text-[10px] text-cyan-300/90 mt-0.5">
              Крок {activeSession.step + 1}/{activeSession.totalSteps} • TTL{' '}
              {formatTtlShort(activeSession.expiresIn)}
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              hapticImpact('medium');
              onResumeSession();
            }}
            className="px-3 py-2 rounded-md bg-emerald-500 text-black font-bold text-xs flex items-center gap-1.5 hover:bg-emerald-400 active:scale-95 transition-all shrink-0 cursor-pointer shadow-[0_0_12px_rgba(16,185,129,0.35)]"
          >
            <Play className="w-3.5 h-3.5 fill-black" />
            <span>Термінал</span>
          </button>
        </section>
      )}

      {/* Cluster Slots Telemetry Bar */}
      <section className="flex items-center justify-between px-3 py-2 rounded-md bg-[#090f14] border border-emerald-500/20 text-[11px]">
        <div className="flex items-center gap-2 text-slate-300">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>Активні контейнери</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-emerald-500/60 tracking-widest hidden sm:inline">
            {mode === 'api' ? 'DOCKER // LIVE' : 'LOCAL // SIM'}
          </span>
          <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/35 font-bold">
            {slots.used}/{slots.max}
          </span>
        </div>
      </section>

      {/* Search & Difficulty Filter */}
      <section className="space-y-2">
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Пошук сценарію (назва, slug, тема)..."
            className="w-full pl-8 pr-8 py-2 rounded-md bg-[#090f14] border border-emerald-500/25 focus:border-emerald-400 text-xs text-emerald-50 placeholder:text-slate-500 outline-none transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              aria-label="Очистити пошук"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-emerald-300 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5">
          {(
            [
              { id: 'all', label: 'Всі рівні' },
              { id: 'easy', label: 'EASY' },
              { id: 'medium', label: 'MEDIUM' },
              { id: 'hard', label: 'HARD' },
            ] as const
          ).map((item) => {
            const active = difficultyFilter === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleDifficultyClick(item.id)}
                className={`px-2.5 py-1 rounded text-[10px] font-bold tracking-wider transition-all cursor-pointer active:scale-95 ${
                  active
                    ? item.id === 'easy'
                      ? 'bg-emerald-500/25 text-emerald-300 border border-emerald-400'
                      : item.id === 'medium'
                        ? 'bg-amber-500/25 text-amber-300 border border-amber-400'
                        : item.id === 'hard'
                          ? 'bg-rose-500/25 text-rose-300 border border-rose-400'
                          : 'bg-cyan-500/20 text-cyan-300 border border-cyan-400'
                    : 'bg-[#0d141a] text-slate-400 border border-slate-800 hover:border-emerald-500/30'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </section>

      {/* Dynamic Category Filter Pills */}
      <section aria-label="Фільтр категорій">
        <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
          {categories.map((category) => {
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
      <section className="space-y-2.5 pb-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold uppercase tracking-widest text-emerald-400/80">
            Сценарії ({filteredTasks.length}/{tasks.length})
          </h2>
          <span className="text-[10px] text-slate-500">Linux // Docker CTF</span>
        </div>

        {filteredTasks.length === 0 ? (
          <div className="bg-[#0d141a]/80 border border-emerald-500/20 rounded-md p-6 text-center space-y-2">
            <p className="text-xs text-slate-400">
              За вашим запитом сценаріїв не знайдено.
            </p>
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setDifficultyFilter('all');
                onSelectCategory('Усі');
              }}
              className="text-xs text-emerald-400 hover:text-emerald-300 underline cursor-pointer"
            >
              Скинути фільтри
            </button>
          </div>
        ) : (
          filteredTasks.map((task) => {
            const isActiveTask = activeSession?.slug === task.slug;
            return (
              <button
                key={task.id}
                type="button"
                onClick={() => handleTaskClick(task)}
                className={`w-full text-left bg-[#0d141a]/90 rounded-md p-3.5 transition-all active:scale-[0.99] cursor-pointer group border ${
                  isActiveTask
                    ? 'border-cyan-400/70 shadow-[0_0_16px_rgba(6,182,212,0.18)]'
                    : 'border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.06)] hover:border-emerald-400 hover:shadow-[0_0_20px_rgba(16,185,129,0.18)]'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 border ${
                      task.done
                        ? 'bg-emerald-500/15 border-emerald-500/40'
                        : 'bg-cyan-950/50 border-cyan-500/30'
                    }`}
                  >
                    {renderCategoryIcon(task.category, task.done)}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <h3 className="text-sm font-bold text-emerald-50 group-hover:text-emerald-300 transition-colors truncate">
                        {task.title}
                      </h3>
                      {task.done && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-400 shrink-0">
                          <CheckCircle2 className="w-4 h-4" />
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-2.5">
                      {stripBotHtml(task.description)}
                    </p>

                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span
                          className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${getDifficultyClasses(
                            task.difficulty
                          )}`}
                        >
                          {getDifficultyLabel(task.difficulty)}
                        </span>
                        <span className="text-[10px] text-cyan-400/85 bg-cyan-950/40 border border-cyan-500/20 px-1.5 py-0.5 rounded truncate max-w-[120px]">
                          {task.category}
                        </span>
                        <span className="inline-flex items-center gap-0.5 text-[10px] text-slate-300 bg-[#090f14] border border-slate-800 px-1.5 py-0.5 rounded">
                          <Layers className="w-2.5 h-2.5 text-slate-400" />
                          {task.stepsCount} кр.
                        </span>
                      </div>

                      <div className="flex items-center gap-1 text-xs font-bold text-emerald-400 shrink-0">
                        <span>+{task.rewardPoints} б.</span>
                        <ChevronRight className="w-4 h-4 text-emerald-500/70 group-hover:translate-x-0.5 transition-transform" />
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </section>
    </main>
  );
}
