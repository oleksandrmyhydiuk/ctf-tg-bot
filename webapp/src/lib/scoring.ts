/**
 * Exact port of bot/formatting.py `calc_reward(reward: int, hint_mask: int) -> int`.
 * Each hint (on a distinct step, tracked as a bit in hintMask) deducts ~20% of the reward,
 * floored at half of the base reward.
 */
export function countHintBits(hintMask: number): number {
  let mask = Math.max(0, Math.trunc(hintMask));
  let count = 0;
  while (mask > 0) {
    count += mask & 1;
    mask = Math.floor(mask / 2);
  }
  return count;
}

export function calcReward(reward: number, hintMask: number): number {
  const hints = countHintBits(hintMask);
  const penaltyPerHint = Math.max(1, Math.floor(reward / 5));
  return Math.max(Math.floor(reward / 2), reward - hints * penaltyPerHint);
}

export interface RankTier {
  title: string;
  nextTitle: string | null;
  minPercent: number;
  nextMinPercent: number | null;
  progressPercent: number;
  nextTargetScore: number | null;
}

const RANK_TIERS: Array<{ title: string; minPercent: number }> = [
  { title: 'Recruit', minPercent: 0 },
  { title: 'Junior DevOps', minPercent: 10 },
  { title: 'SysAdmin', minPercent: 25 },
  { title: 'Security Analyst', minPercent: 45 },
  { title: 'Senior SRE', minPercent: 70 },
  { title: 'Cyber Architect', minPercent: 90 },
];

export function getRankTier(score: number, maxScore: number): RankTier {
  const safeMax = Math.max(1, maxScore);
  const pct = Math.min(100, Math.max(0, (score / safeMax) * 100));

  let currentIdx = 0;
  for (let i = 0; i < RANK_TIERS.length; i++) {
    if (pct >= RANK_TIERS[i].minPercent) {
      currentIdx = i;
    }
  }

  const current = RANK_TIERS[currentIdx];
  const next = RANK_TIERS[currentIdx + 1] ?? null;

  if (!next) {
    return {
      title: current.title,
      nextTitle: null,
      minPercent: current.minPercent,
      nextMinPercent: null,
      progressPercent: 100,
      nextTargetScore: null,
    };
  }

  const nextTargetScore = Math.ceil((next.minPercent / 100) * safeMax);
  const span = Math.max(1, next.minPercent - current.minPercent);
  const progressPercent = Math.min(
    100,
    Math.max(0, Math.round(((pct - current.minPercent) / span) * 100))
  );

  return {
    title: current.title,
    nextTitle: next.title,
    minPercent: current.minPercent,
    nextMinPercent: next.minPercent,
    progressPercent,
    nextTargetScore,
  };
}

const DEMO_STORAGE_KEY = 'ctfbot_demo_progress_v1';

export interface DemoProgress {
  score: number;
  solvedSlugs: string[];
}

export function loadDemoProgress(): DemoProgress {
  if (typeof window === 'undefined') {
    return { score: 0, solvedSlugs: [] };
  }
  try {
    const raw = window.localStorage.getItem(DEMO_STORAGE_KEY);
    if (!raw) return { score: 0, solvedSlugs: [] };
    const parsed = JSON.parse(raw) as Partial<DemoProgress>;
    return {
      score: typeof parsed.score === 'number' && Number.isFinite(parsed.score) ? Math.max(0, Math.trunc(parsed.score)) : 0,
      solvedSlugs: Array.isArray(parsed.solvedSlugs)
        ? parsed.solvedSlugs.filter((s): s is string => typeof s === 'string')
        : [],
    };
  } catch {
    return { score: 0, solvedSlugs: [] };
  }
}

export function saveDemoProgress(progress: DemoProgress): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(progress));
  } catch {
    // Ignore storage quota / private mode errors
  }
}
