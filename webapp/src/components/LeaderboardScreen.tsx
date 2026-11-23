import { useMemo } from 'react';
import { Clock, Share2, Trophy, Zap } from 'lucide-react';
import type { LeaderboardEntry, TelegramUser } from '../types';
import { LEADERBOARD_DATA } from '../data/leaderboard';
import { hapticImpact, shareChallenge } from '../lib/telegram';

interface LeaderboardScreenProps {
  telegramUser: TelegramUser;
  userXp: number;
}

function getRankBadgeStyle(rank: number): string {
  switch (rank) {
    case 1:
      return 'bg-amber-500/20 text-amber-300 border border-amber-400/60 shadow-[0_0_10px_rgba(245,158,11,0.25)]';
    case 2:
      return 'bg-slate-300/15 text-slate-200 border border-slate-400/50';
    case 3:
      return 'bg-orange-500/15 text-orange-300 border border-orange-500/50';
    default:
      return 'bg-[#090f14] text-slate-400 border border-slate-800';
  }
}

export function LeaderboardScreen({
  telegramUser,
  userXp,
}: LeaderboardScreenProps) {
  const entries = useMemo<LeaderboardEntry[]>(() => {
    const updated = LEADERBOARD_DATA.map((entry) =>
      entry.isMe
        ? {
            ...entry,
            name: `${telegramUser.firstName} (Ви)`,
            avatar: telegramUser.initials,
            xp: userXp,
          }
        : entry
    );

    return [...updated]
      .sort((a, b) => b.xp - a.xp)
      .map((entry, idx) => ({
        ...entry,
        rank: idx + 1,
      }));
  }, [telegramUser.firstName, telegramUser.initials, userXp]);

  const myEntry = entries.find((entry) => entry.isMe);

  const handleShareChallenge = () => {
    hapticImpact('medium');
    const rankText = myEntry ? `#${myEntry.rank}` : 'у топі';
    shareChallenge(
      `⚡ Я вже ${rankText} у DevOps Sandbox з ${userXp} XP! Спробуй обігнати мене в Linux CTF-пісочниці!`
    );
  };

  return (
    <main className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
      {/* Banner */}
      <section className="bg-[#0d141a]/90 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.08)] rounded-md p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md bg-emerald-500/15 border border-emerald-400/50 flex items-center justify-center shadow-[0_0_12px_rgba(16,185,129,0.25)]">
              <Trophy className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-emerald-50">
                Рейтинг групового чату
              </h1>
              <p className="text-[11px] text-emerald-400/75 uppercase tracking-wider">
                DevOps Squad // Live Sync
              </p>
            </div>
          </div>

          {myEntry && (
            <div className="text-right">
              <div className="text-xs font-bold text-cyan-300">
                Позиція #{myEntry.rank}
              </div>
              <div className="text-[11px] text-emerald-400 font-semibold">
                {myEntry.xp} XP
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Leaderboard List */}
      <section className="space-y-2.5">
        {entries.map((entry) => (
          <div
            key={`${entry.name}-${entry.rank}`}
            className={`rounded-md p-3 transition-all flex items-center gap-3 ${
              entry.isMe
                ? 'bg-emerald-500/10 border border-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.18)]'
                : 'bg-[#0d141a]/90 border border-emerald-500/25 shadow-[0_0_12px_rgba(16,185,129,0.05)]'
            }`}
          >
            <div
              className={`w-7 h-7 rounded flex items-center justify-center text-xs font-bold shrink-0 ${getRankBadgeStyle(
                entry.rank
              )}`}
            >
              {entry.rank}
            </div>

            <div
              className={`w-9 h-9 rounded-md flex items-center justify-center text-xs font-bold shrink-0 border ${
                entry.isMe
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400/60'
                  : 'bg-[#090f14] text-cyan-300 border-cyan-500/30'
              }`}
            >
              {entry.avatar}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold text-emerald-50 truncate">
                  {entry.name}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-0.5">
                <span className="truncate">{entry.role}</span>
                <span className="text-slate-600">•</span>
                <span className="inline-flex items-center gap-1 shrink-0">
                  <Clock className="w-3 h-3 text-slate-500" />
                  {entry.time}
                </span>
              </div>
            </div>

            <div className="text-right shrink-0">
              <div className="inline-flex items-center gap-1 text-xs font-bold text-emerald-400">
                <Zap className="w-3.5 h-3.5 fill-emerald-400/20" />
                <span>{entry.xp}</span>
              </div>
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">
                XP
              </div>
            </div>
          </div>
        ))}
      </section>

      {/* Share Challenge CTA */}
      <section className="pt-1 pb-2">
        <button
          type="button"
          onClick={handleShareChallenge}
          className="w-full py-3 px-4 bg-emerald-500 text-black font-bold text-xs uppercase tracking-wider hover:bg-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.4)] rounded-md flex items-center justify-center gap-2 transition-all active:scale-[0.98] cursor-pointer"
        >
          <Share2 className="w-4 h-4" />
          <span>Кинути виклик у груповий чат</span>
        </button>
      </section>
    </main>
  );
}
