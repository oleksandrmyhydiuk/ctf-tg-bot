import { Terminal, Trophy } from 'lucide-react';
import type { Screen } from '../types';
import { hapticImpact } from '../lib/telegram';

interface BottomNavProps {
  screen: Screen;
  onNavigate: (screen: Screen) => void;
}

export function BottomNav({ screen, onNavigate }: BottomNavProps) {
  const handleSelect = (target: Screen) => {
    if (screen === target) return;
    hapticImpact('light');
    onNavigate(target);
  };

  return (
    <nav
      aria-label="Основна навігація"
      className="bg-[#090f14] border-t border-emerald-500/30 px-4 pt-2 pb-[max(0.625rem,env(safe-area-inset-bottom))] shrink-0 z-20"
    >
      <div className="grid grid-cols-2 gap-2.5">
        <button
          type="button"
          onClick={() => handleSelect('hub')}
          className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-md text-xs font-bold tracking-wide transition-all cursor-pointer active:scale-[0.98] ${
            screen === 'hub'
              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-400/60 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
              : 'bg-[#0d141a]/60 text-slate-400 border border-slate-800/80 hover:text-emerald-200 hover:border-emerald-500/30'
          }`}
        >
          <Terminal className="w-4 h-4" />
          <span>Завдання</span>
        </button>

        <button
          type="button"
          onClick={() => handleSelect('leaderboard')}
          className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-md text-xs font-bold tracking-wide transition-all cursor-pointer active:scale-[0.98] ${
            screen === 'leaderboard'
              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-400/60 shadow-[0_0_12px_rgba(16,185,129,0.2)]'
              : 'bg-[#0d141a]/60 text-slate-400 border border-slate-800/80 hover:text-emerald-200 hover:border-emerald-500/30'
          }`}
        >
          <Trophy className="w-4 h-4" />
          <span>Рейтинг</span>
        </button>
      </div>
    </nav>
  );
}
