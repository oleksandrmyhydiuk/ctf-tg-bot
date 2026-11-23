import type {
  ActiveSession,
  BootstrapData,
  CheckResult,
  Difficulty,
  ExecResult,
  HintResult,
  LeaderboardEntry,
  LeaderboardResponse,
  Task,
} from '../types';
import { getInitData } from './telegram';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface RawTask {
  id: number;
  slug: string;
  title: string;
  category: string;
  difficulty: string;
  reward_points: number;
  description: string;
  mem_limit?: string;
  pids_limit?: number;
  steps_count?: number;
  steps?: Array<{ text: string; hint?: string }>;
  done?: boolean;
}

interface RawActiveSession {
  task_id: number;
  slug: string;
  title: string;
  step: number;
  total_steps: number;
  step_text: string;
  has_hint: boolean;
  hint_used: boolean;
  hint_text: string | null;
  hint_mask: number;
  cwd: string;
  expires_in: number;
  reward_points: number;
  current_reward: number;
}

interface RawBootstrap {
  user: {
    id: number;
    tg_id: number;
    username: string | null;
    score: number;
    rank: number | null;
    solved_count: number;
    total_tasks: number;
    max_score: number;
  };
  tasks: RawTask[];
  active_session: RawActiveSession | null;
  slots: {
    used: number;
    max: number;
  };
  session_ttl: number;
}

interface RawLeaderboard {
  entries: Array<{
    rank: number;
    username: string;
    tg_id?: number;
    score: number;
    is_me: boolean;
  }>;
  my_rank: number | null;
  my_score: number;
}

function normalizeDifficulty(raw: string): Difficulty {
  const lower = raw.toLowerCase();
  if (lower === 'medium') return 'medium';
  if (lower === 'hard') return 'hard';
  return 'easy';
}

function mapTask(raw: RawTask): Task {
  const steps = Array.isArray(raw.steps) ? raw.steps : [];
  return {
    id: raw.id,
    slug: raw.slug,
    title: raw.title,
    category: raw.category,
    difficulty: normalizeDifficulty(raw.difficulty),
    rewardPoints: raw.reward_points,
    description: raw.description,
    memLimit: raw.mem_limit ?? '128m',
    pidsLimit: raw.pids_limit ?? 64,
    stepsCount: raw.steps_count ?? steps.length,
    steps,
    done: Boolean(raw.done),
  };
}

function mapActiveSession(raw: RawActiveSession): ActiveSession {
  return {
    taskId: raw.task_id,
    slug: raw.slug,
    title: raw.title,
    step: raw.step,
    totalSteps: raw.total_steps,
    stepText: raw.step_text,
    hasHint: raw.has_hint,
    hintUsed: raw.hint_used,
    hintText: raw.hint_text,
    hintMask: raw.hint_mask,
    cwd: raw.cwd,
    expiresIn: raw.expires_in,
    rewardPoints: raw.reward_points,
    currentReward: raw.current_reward,
  };
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 15000
): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  };

  const initData = getInitData();
  if (initData) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  try {
    const res = await fetch(path, {
      ...options,
      headers,
      signal: controller.signal,
    });

    const contentType = res.headers.get('content-type') ?? '';
    const isJson = contentType.includes('application/json');
    const payload = isJson ? await res.json() : null;

    if (!res.ok) {
      const msg =
        (payload && typeof payload.error === 'string' && payload.error) ||
        (payload && typeof payload.message === 'string' && payload.message) ||
        `HTTP ${res.status}`;
      throw new ApiError(msg, res.status);
    }

    if (!isJson) {
      throw new ApiError('Unexpected non-JSON response from API', res.status);
    }

    return payload as T;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function fetchBootstrap(): Promise<BootstrapData> {
  const raw = await apiRequest<RawBootstrap>('/api/bootstrap', { method: 'GET' }, 4500);
  return {
    user: {
      id: raw.user.id,
      tgId: raw.user.tg_id,
      username: raw.user.username,
      score: raw.user.score,
      rank: raw.user.rank,
      solvedCount: raw.user.solved_count,
      totalTasks: raw.user.total_tasks,
      maxScore: raw.user.max_score,
    },
    tasks: raw.tasks.map(mapTask),
    activeSession: raw.active_session ? mapActiveSession(raw.active_session) : null,
    slots: raw.slots,
    sessionTtl: raw.session_ttl,
  };
}

export async function fetchLeaderboard(): Promise<LeaderboardResponse> {
  const raw = await apiRequest<RawLeaderboard>('/api/leaderboard', { method: 'GET' }, 8000);
  const entries: LeaderboardEntry[] = raw.entries.map((e) => ({
    rank: e.rank,
    username: e.username,
    tgId: e.tg_id,
    score: e.score,
    isMe: e.is_me,
  }));
  return {
    entries,
    myRank: raw.my_rank,
    myScore: raw.my_score,
  };
}

export async function startSession(
  taskId: number,
  slug?: string
): Promise<ActiveSession> {
  const raw = await apiRequest<{ session: RawActiveSession }>(
    '/api/sessions',
    {
      method: 'POST',
      body: JSON.stringify(slug ? { task_id: taskId, slug } : { task_id: taskId }),
    },
    30000
  );
  return mapActiveSession(raw.session);
}

export async function execCommand(cmd: string): Promise<ExecResult> {
  const raw = await apiRequest<{
    output: string;
    timed_out: boolean;
    cwd: string;
  }>(
    '/api/sessions/exec',
    {
      method: 'POST',
      body: JSON.stringify({ cmd }),
    },
    20000
  );
  return {
    output: raw.output,
    timedOut: raw.timed_out,
    cwd: raw.cwd,
  };
}

export async function requestHint(): Promise<HintResult> {
  const raw = await apiRequest<{
    hint: string;
    hint_mask: number;
    current_reward: number;
    already_used: boolean;
  }>('/api/sessions/hint', { method: 'POST' }, 10000);
  return {
    hint: raw.hint,
    hintMask: raw.hint_mask,
    currentReward: raw.current_reward,
    alreadyUsed: raw.already_used,
  };
}

export async function checkStep(): Promise<CheckResult> {
  const raw = await apiRequest<
    | { passed: false; message: string }
    | { passed: true; completed: false; session: RawActiveSession }
    | {
        passed: true;
        completed: true;
        awarded_points: number;
        max_points: number;
        already_solved: boolean;
        total_score: number;
        time_spent: number;
      }
  >('/api/sessions/check', { method: 'POST' }, 20000);

  if (!raw.passed) {
    return { passed: false, message: raw.message };
  }
  if (!raw.completed) {
    return {
      passed: true,
      completed: false,
      session: mapActiveSession(raw.session),
    };
  }
  return {
    passed: true,
    completed: true,
    awardedPoints: raw.awarded_points,
    maxPoints: raw.max_points,
    alreadySolved: raw.already_solved,
    totalScore: raw.total_score,
    timeSpent: raw.time_spent,
  };
}

export async function stopSession(): Promise<void> {
  await apiRequest<{ stopped: boolean }>('/api/sessions', { method: 'DELETE' }, 10000);
}
