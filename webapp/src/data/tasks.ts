import botTasksRaw from './botTasks.json';
import type { Difficulty, Task, TaskCategory } from '../types';

interface BotTaskJson {
  id: number;
  slug: string;
  title: string;
  category: string;
  difficulty: string;
  reward_points: number;
  description: string;
  mem_limit?: string;
  pids_limit?: number;
  steps: Array<{ text: string; hint?: string }>;
}

function normalizeDifficulty(raw: string): Difficulty {
  const lower = raw.toLowerCase();
  if (lower === 'medium') return 'medium';
  if (lower === 'hard') return 'hard';
  return 'easy';
}

export const BOT_TASKS: Task[] = (botTasksRaw as BotTaskJson[]).map((raw) => ({
  id: raw.id,
  slug: raw.slug,
  title: raw.title,
  category: raw.category,
  difficulty: normalizeDifficulty(raw.difficulty),
  rewardPoints: raw.reward_points,
  description: raw.description,
  memLimit: raw.mem_limit ?? '128m',
  pidsLimit: raw.pids_limit ?? 64,
  stepsCount: raw.steps.length,
  steps: raw.steps,
  done: false,
}));

export const MAX_TOTAL_SCORE = BOT_TASKS.reduce(
  (sum, task) => sum + task.rewardPoints,
  0
);

export function getTaskCategories(tasks: Task[]): TaskCategory[] {
  const seen = new Set<string>();
  const categories: TaskCategory[] = ['Усі'];
  for (const task of tasks) {
    if (task.category && !seen.has(task.category)) {
      seen.add(task.category);
      categories.push(task.category);
    }
  }
  return categories;
}
