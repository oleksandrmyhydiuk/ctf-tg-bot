import { useCallback, useEffect, useMemo, useState } from 'react';
import type { Screen, Task, TaskCategory, VictoryData } from './types';
import { INITIAL_TASKS } from './data/tasks';
import { closeMiniApp, getTelegramUser, initTelegramApp } from './lib/telegram';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import { HubScreen } from './components/HubScreen';
import { SandboxScreen } from './components/SandboxScreen';
import { LeaderboardScreen } from './components/LeaderboardScreen';
import { HintModal, TaskPreviewModal, VictoryModal } from './components/Modals';

function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export default function App() {
  const [screen, setScreen] = useState<Screen>('hub');
  const [tasks, setTasks] = useState<Task[]>(INITIAL_TASKS);
  const [selectedCategory, setSelectedCategory] = useState<TaskCategory>('Усі');
  const [previewTask, setPreviewTask] = useState<Task | null>(null);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [userXp, setUserXp] = useState<number>(450);
  const [hintUsed, setHintUsed] = useState<boolean>(false);
  const [isHintOpen, setIsHintOpen] = useState<boolean>(false);
  const [victoryData, setVictoryData] = useState<VictoryData | null>(null);

  const telegramUser = useMemo(() => getTelegramUser(), []);

  useEffect(() => {
    initTelegramApp();
  }, []);

  const handleBackToHub = useCallback(() => {
    setScreen('hub');
    setActiveTask(null);
    setIsHintOpen(false);
    setVictoryData(null);
  }, []);

  const handleStartTask = useCallback((task: Task) => {
    setPreviewTask(null);
    setActiveTask(task);
    setHintUsed(false);
    setIsHintOpen(false);
    setVictoryData(null);
    setScreen('sandbox');
  }, []);

  const handleOpenHint = useCallback(() => {
    setHintUsed(true);
    setIsHintOpen(true);
  }, []);

  const handleTaskSolved = useCallback(
    (timeSpentSeconds: number) => {
      if (!activeTask) return;

      const earnedXp = activeTask.solved
        ? 0
        : hintUsed
          ? Math.round(activeTask.xp * 0.9)
          : activeTask.xp;

      if (!activeTask.solved) {
        setUserXp((prev) => prev + earnedXp);
        setTasks((prev) =>
          prev.map((item) =>
            item.id === activeTask.id ? { ...item, solved: true } : item
          )
        );
      }

      setVictoryData({
        task: activeTask,
        earnedXp,
        timeSpent: formatElapsed(timeSpentSeconds),
      });
    },
    [activeTask, hintUsed]
  );

  const handleVictoryToHub = useCallback(() => {
    setVictoryData(null);
    setActiveTask(null);
    setScreen('hub');
  }, []);

  const handleVictoryToLeaderboard = useCallback(() => {
    setVictoryData(null);
    setActiveTask(null);
    setScreen('leaderboard');
  }, []);

  return (
    <div className="min-h-[100dvh] h-[100dvh] w-full bg-[#070b0e] text-emerald-50 font-mono flex justify-center overflow-hidden">
      <div className="w-full max-w-md h-full flex flex-col bg-[#070b0e] sm:border-x sm:border-emerald-500/20 relative overflow-hidden">
        <Header
          screen={screen}
          onBack={handleBackToHub}
          onClose={closeMiniApp}
        />

        {screen === 'hub' && (
          <HubScreen
            tasks={tasks}
            telegramUser={telegramUser}
            userXp={userXp}
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
            onSelectTask={setPreviewTask}
          />
        )}

        {screen === 'sandbox' && activeTask && (
          <SandboxScreen
            task={activeTask}
            hintUsed={hintUsed}
            onOpenHint={handleOpenHint}
            onTaskSolved={handleTaskSolved}
          />
        )}

        {screen === 'leaderboard' && (
          <LeaderboardScreen telegramUser={telegramUser} userXp={userXp} />
        )}

        {screen !== 'sandbox' && (
          <BottomNav screen={screen} onNavigate={setScreen} />
        )}

        <TaskPreviewModal
          task={previewTask}
          onClose={() => setPreviewTask(null)}
          onStart={handleStartTask}
        />

        <HintModal
          isOpen={isHintOpen}
          hint={activeTask?.hint ?? ''}
          onClose={() => setIsHintOpen(false)}
        />

        <VictoryModal
          victory={victoryData}
          onGoHub={handleVictoryToHub}
          onGoLeaderboard={handleVictoryToLeaderboard}
        />
      </div>
    </div>
  );
}
