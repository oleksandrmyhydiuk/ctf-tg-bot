import type { LeaderboardEntry } from '../types';

export const LEADERBOARD_DATA: LeaderboardEntry[] = [
  {
    rank: 1,
    name: 'Олена К.',
    role: 'Senior SRE',
    xp: 920,
    time: '01:14',
    avatar: 'ОК',
  },
  {
    rank: 2,
    name: 'Максим В.',
    role: 'DevOps Engineer',
    xp: 780,
    time: '01:42',
    avatar: 'МВ',
  },
  {
    rank: 3,
    name: 'Андрій С.',
    role: 'Cloud Architect',
    xp: 610,
    time: '02:05',
    avatar: 'АС',
  },
  {
    rank: 4,
    name: 'Олександр',
    role: 'Junior DevOps',
    xp: 450,
    time: '02:38',
    avatar: 'ОЛ',
    isMe: true,
  },
  {
    rank: 5,
    name: 'Дмитро П.',
    role: 'Linux Admin',
    xp: 310,
    time: '03:19',
    avatar: 'ДП',
  },
];
