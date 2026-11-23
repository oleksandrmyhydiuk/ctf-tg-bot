export type AppMode = 'api' | 'demo';

export type Screen = 'hub' | 'sandbox' | 'leaderboard';

export type Difficulty = 'easy' | 'medium' | 'hard';

export type TaskCategory = string;

export interface VirtualFile {
  perms: string;
  readable: boolean;
  content: string;
  size: string;
}

export type VirtualFileSystem = Record<string, VirtualFile>;

export interface TaskStep {
  text: string;
  hint?: string;
}

export interface Task {
  id: number;
  slug: string;
  title: string;
  category: string;
  difficulty: Difficulty;
  rewardPoints: number;
  description: string;
  memLimit: string;
  pidsLimit: number;
  stepsCount: number;
  steps: TaskStep[];
  done: boolean;
}

export interface ActiveSession {
  taskId: number;
  slug: string;
  title: string;
  step: number;
  totalSteps: number;
  stepText: string;
  hasHint: boolean;
  hintUsed: boolean;
  hintText: string | null;
  hintMask: number;
  cwd: string;
  expiresIn: number;
  rewardPoints: number;
  currentReward: number;
}

export interface UserProfile {
  id: number;
  tgId: number;
  username: string | null;
  score: number;
  rank: number | null;
  solvedCount: number;
  totalTasks: number;
  maxScore: number;
}

export interface ClusterSlots {
  used: number;
  max: number;
}

export interface BootstrapData {
  user: UserProfile;
  tasks: Task[];
  activeSession: ActiveSession | null;
  slots: ClusterSlots;
  sessionTtl: number;
}

export interface LeaderboardEntry {
  rank: number;
  username: string;
  tgId?: number;
  score: number;
  isMe: boolean;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  myRank: number | null;
  myScore: number;
}

export interface ExecResult {
  output: string;
  timedOut: boolean;
  cwd: string;
}

export interface HintResult {
  hint: string;
  hintMask: number;
  currentReward: number;
  alreadyUsed: boolean;
}

export type CheckResult =
  | {
      passed: false;
      message: string;
    }
  | {
      passed: true;
      completed: false;
      session: ActiveSession;
    }
  | {
      passed: true;
      completed: true;
      awardedPoints: number;
      maxPoints: number;
      alreadySolved: boolean;
      totalScore: number;
      timeSpent: number;
    };

export interface TerminalEntry {
  type: 'system' | 'cmd' | 'out' | 'err';
  text: string;
  prompt?: string;
}

export interface VictoryData {
  task: Task;
  awardedPoints: number;
  maxPoints: number;
  alreadySolved: boolean;
  totalScore: number;
  timeSpent: string;
}

export interface TelegramUser {
  id?: number;
  firstName: string;
  lastName?: string;
  username?: string;
  initials: string;
  isTelegram: boolean;
}
