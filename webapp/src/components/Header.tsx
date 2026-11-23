import { useEffect } from 'react';
import { ChevronLeft, Terminal, X } from 'lucide-react';
import type { Screen } from '../types';
import { hapticImpact, setBackButton } from '../lib/telegram';

interface HeaderProps {
  screen: Screen;
  onBack: () => void;
  onClose: () => void;
}

export function Header({ screen, onBack, onClose }: HeaderProps) {
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

  return (
    <header className="bg-[#090f14]/95 backdrop-blur-md border-b border-emerald-500/20 px-3.5 py-2.5 flex items-center justify-between shrink-0 z-20">
      <div className="w-24 flex items-center">
        {screen === 'sandbox' ? (
          <button
            type="button"
            onClick={handleBack}
            className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 hover:text-emerald-300 active:scale-95 transition-all py-1 pr-2 cursor-pointer"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Назад</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={handleClose}
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-emerald-300 active:scale-95 transition-all py-1 pr-2 cursor-pointer"
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
        <span className="text-[10px] tracking-[0.2em] text-emerald-500/75 uppercase leading-tight">
          cyberpunk // tma
        </span>
      </div>

      <div className="w-24 flex items-center justify-end">
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
          </span>
          <span className="text-[9px] font-bold tracking-widest text-emerald-400">
            ONLINE
          </span>
        </div>
      </div>
    </header>
  );
}
