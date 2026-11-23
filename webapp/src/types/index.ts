export type Screen = 'hub' | 'sandbox' | 'leaderboard';

export type Difficulty = 'Easy' | 'Medium' | 'Hard';

export type TaskCategory = 'Усі' | 'Permissions' | 'Logs & Text' | 'Filesystem';

export type TaskIconName = 'lock' | 'search' | 'eye-off';

export interface VirtualFile {
  perms: string;
  readable: boolean;
  content: string;
  size: string;
}

export type VirtualFileSystem = Record<string, VirtualFile>;

export interface Task {
  id: number;
  title: string;
  category: Exclude<TaskCategory, 'Усі'>;
  difficulty: Difficulty;
  xp: number;
  solved: boolean;
  icon: TaskIconName;
  shortDesc: string;
  loreDesc: string;
  hint: string;
  review: string;
  initialFiles: VirtualFileSystem;
}

export interface LeaderboardEntry {
  rank: number;
  name: string;
  role: string;
  xp: number;
  time: string;
  avatar: string;
  isMe?: boolean;
}

export interface TerminalEntry {
  type: 'system' | 'cmd' | 'out' | 'err';
  text: string;
}

export interface VictoryData {
  task: Task;
  earnedXp: number;
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
