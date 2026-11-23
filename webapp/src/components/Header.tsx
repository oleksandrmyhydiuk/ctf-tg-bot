import { useEffect } from 'react';
import { ChevronLeft, Terminal, X } from 'lucide-react';
import type { AppMode, Screen } from '../types';
import { hapticImpact, setBackButton } from '../lib/telegram';

interface HeaderProps {
  screen: Screen;
  mode: AppMode;
  onBack: () => void;
  onClose: () => void;
}

export function Header({ screen, mode, onBack, onClose }: HeaderProps) {
  useEffect(() => {
    return setBackButton(screen === 'sandbox', onBack);
  }, [screen, onBack]);

  const handleBack = () => {
    hapticImpact('light');
    onBack();
  };

  const handleClose = () => {
    hapticImpact('light');
    onClose();
  };

  const isLive = mode === 'api';

  return (
    <header className="bg-[#090f14]/95 backdrop-blur-md border-b border-emerald-500/20 px-3 py-2.5 flex items-center justify-between gap-2 shrink-0 z-20">
      <div className="w-20 flex items-center">
        {screen === 'sandbox' ? (
          <button
            type="button"
            onClick={handleBack}
            className="inline-flex items-center gap-0.5 text-xs font-semibold text-emerald-400 hover:text-emerald-300 active:scale-95 transition-all py-1 pr-1 cursor-pointer"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Назад</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={handleClose}
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-emerald-300 active:scale-95 transition-all py-1 pr-1 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
            <span>Закрити</span>
          </button>
        )}
      </div>

      <div className="flex flex-col items-center text-center min-w-0">
        <div className="flex items-center gap-1.5 text-sm font-bold tracking-wider text-emerald-50">
          <Terminal className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span className="truncate">DevOps Sandbox</span>
        </div>
        <span className="text-[9px] tracking-[0.18em] text-emerald-500/75 uppercase leading-tight">
          cyberpunk // tma
        </span>
      </div>

      <div className="w-28 flex items-center justify-end">
        <div
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border ${
            isLive
              ? 'bg-emerald-500/10 border-emerald-500/35'
              : 'bg-amber-500/10 border-amber-500/35'
          }`}
        >
          <span className="relative flex h-1.5 w-1.5 shrink-0">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isLive ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-1.5 w-1.5 ${
                isLive ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
          </span>
          <span
            className={`text-[8px] font-bold tracking-wider whitespace-nowrap ${
              isLive ? 'text-emerald-400' : 'text-amber-300'
            }`}
          >
            {isLive ? 'LIVE // DOCKER' : 'DEMO // LOCAL'}
          </span>
        </div>
      </div>
    </header>
  );
}
