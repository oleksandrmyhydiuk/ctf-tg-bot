import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  ActiveSession,
  AppMode,
  ClusterSlots,
  LeaderboardEntry,
  Screen,
  Task,
  TaskCategory,
  TerminalEntry,
  VictoryData,
  VirtualFileSystem,
} from './types';
import { BOT_TASKS, getTaskCategories, MAX_TOTAL_SCORE } from './data/tasks';
import {
  checkStep as apiCheckStep,
  execCommand as apiExecCommand,
  fetchBootstrap,
  fetchLeaderboard,
  requestHint as apiRequestHint,
  startSession as apiStartSession,
  stopSession as apiStopSession,
} from './lib/api';
import {
  calcReward,
  loadDemoProgress,
  saveDemoProgress,
} from './lib/scoring';
import {
  checkDemoStep,
  executeCommand as execDemoCommand,
  FULL_DEMO_SLUGS,
  getInitialDemoFiles,
} from './lib/simulator';
import {
  closeMiniApp,
  getTelegramUser,
  hapticNotification,
  initTelegramApp,
} from './lib/telegram';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import { HubScreen } from './components/HubScreen';
import { SandboxScreen } from './components/SandboxScreen';
import { LeaderboardScreen } from './components/LeaderboardScreen';
import { HintModal, TaskPreviewModal, VictoryModal } from './components/Modals';

const DEFAULT_TTL = 900;

function formatElapsed(seconds: number): string {
  const clamped = Math.max(1, Math.trunc(seconds));
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function buildDemoTasks(): { tasks: Task[]; score: number } {
  const saved = loadDemoProgress();
  const solvedSet = new Set(saved.solvedSlugs);
  const tasks = BOT_TASKS.map((t) => ({
    ...t,
    done: solvedSet.has(t.slug),
  }));
  return { tasks, score: saved.score };
}

function buildInitialEntries(mode: AppMode, session: ActiveSession): TerminalEntry[] {
  if (mode === 'api') {
    return [
      {
        type: 'system',
        text: `[docker] Підключено до контейнера ${session.slug} (Крок ${session.step + 1}/${session.totalSteps}).`,
      },
      {
        type: 'system',
        text: `[ok] Робоча директорія: ${session.cwd}. Введіть команду Linux.`,
      },
    ];
  }

  const lines: TerminalEntry[] = [
    {
      type: 'system',
      text: `[demo] Локальна пісочниця ${session.slug} (Крок ${session.step + 1}/${session.totalSteps}).`,
    },
  ];
  if (!FULL_DEMO_SLUGS.has(session.slug)) {
    lines.push({
      type: 'system',
      text: `[info] Повноцінна перевірка цього сценарію потребує Docker-бекенд бота. У DEMO-режимі повністю працюють: perms, needle, hidden.`,
    });
  } else {
    lines.push({
      type: 'system',
      text: `[ok] Введіть 'help' або 'ls -la' для початку.`,
    });
  }
  return lines;
}

export default function App() {
  const [mode, setMode] = useState<AppMode>('demo');
  const [screen, setScreen] = useState<Screen>('hub');

  const initialDemo = useMemo(() => buildDemoTasks(), []);
  const [tasks, setTasks] = useState<Task[]>(initialDemo.tasks);
  const [userScore, setUserScore] = useState<number>(initialDemo.score);
  const [maxScore, setMaxScore] = useState<number>(MAX_TOTAL_SCORE);
  const [userRank, setUserRank] = useState<number | null>(null);
  const [slots, setSlots] = useState<ClusterSlots>({ used: 0, max: 20 });
  const [sessionTtl, setSessionTtl] = useState<number>(DEFAULT_TTL);

  const [selectedCategory, setSelectedCategory] = useState<TaskCategory>('Усі');
  const [previewTask, setPreviewTask] = useState<Task | null>(null);
  const [startingSession, setStartingSession] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);
  const [terminalEntries, setTerminalEntries] = useState<TerminalEntry[]>([]);
  const [demoFiles, setDemoFiles] = useState<VirtualFileSystem>({});
  const demoStartedAtRef = useRef<number>(Date.now());

  const [isExecuting, setIsExecuting] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [isHintLoading, setIsHintLoading] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  const [checkError, setCheckError] = useState<string | null>(null);
  const [stepBanner, setStepBanner] = useState<string | null>(null);

  const [isHintOpen, setIsHintOpen] = useState(false);
  const [modalHintText, setModalHintText] = useState('');
  const [victoryData, setVictoryData] = useState<VictoryData | null>(null);

  const [leaderboardEntries, setLeaderboardEntries] = useState<LeaderboardEntry[]>([]);
  const [leaderboardMyRank, setLeaderboardMyRank] = useState<number | null>(null);
  const [leaderboardLoading, setLeaderboardLoading] = useState(false);

  const telegramUser = useMemo(() => getTelegramUser(), []);
  const categories = useMemo(() => getTaskCategories(tasks), [tasks]);

  const activeTask = useMemo(() => {
    if (!activeSession) return null;
    return (
      tasks.find((t) => t.id === activeSession.taskId || t.slug === activeSession.slug) ??
      null
    );
  }, [activeSession, tasks]);

  // Initialize Telegram WebApp SDK & bootstrap from backend API (with seamless demo fallback)
  useEffect(() => {
    initTelegramApp();

    let cancelled = false;
    (async () => {
      try {
        const data = await fetchBootstrap();
        if (cancelled) return;
        setMode('api');
        setTasks(data.tasks);
        setUserScore(data.user.score);
        setMaxScore(data.user.maxScore || MAX_TOTAL_SCORE);
        setUserRank(data.user.rank);
        setSlots(data.slots);
        setSessionTtl(data.sessionTtl || DEFAULT_TTL);
        if (data.activeSession) {
          setActiveSession(data.activeSession);
          setTerminalEntries(buildInitialEntries('api', data.activeSession));
        }
      } catch {
        // Backend unreachable -> stay cleanly in offline DEMO mode
        if (cancelled) return;
        setMode('demo');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-dismiss check error toast
  useEffect(() => {
    if (!checkError) return;
    const t = window.setTimeout(() => setCheckError(null), 5000);
    return () => window.clearTimeout(t);
  }, [checkError]);

  // Auto-dismiss step banner
  useEffect(() => {
    if (!stepBanner) return;
    const t = window.setTimeout(() => setStepBanner(null), 4000);
    return () => window.clearTimeout(t);
  }, [stepBanner]);

  const refreshLeaderboard = useCallback(async () => {
    if (mode !== 'api') return;
    setLeaderboardLoading(true);
    try {
      const res = await fetchLeaderboard();
      setLeaderboardEntries(res.entries);
      setLeaderboardMyRank(res.myRank);
      setUserRank(res.myRank);
      setUserScore(res.myScore);
    } catch {
      // Keep previous entries on transient error
    } finally {
      setLeaderboardLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    if (screen === 'leaderboard' && mode === 'api') {
      void refreshLeaderboard();
    }
  }, [screen, mode, refreshLeaderboard]);

  const refreshBootstrapQuiet = useCallback(async () => {
    if (mode !== 'api') return;
    try {
      const data = await fetchBootstrap();
      setTasks(data.tasks);
      setUserScore(data.user.score);
      setMaxScore(data.user.maxScore || MAX_TOTAL_SCORE);
      setUserRank(data.user.rank);
      setSlots(data.slots);
      setSessionTtl(data.sessionTtl || DEFAULT_TTL);
      if (!data.activeSession) {
        setActiveSession(null);
      }
    } catch {
      // Ignore silent refresh error
    }
  }, [mode]);

  const handleBackToHub = useCallback(() => {
    setScreen('hub');
    setIsHintOpen(false);
    setCheckError(null);
    setStepBanner(null);
  }, []);

  const handleResumeSession = useCallback(() => {
    if (!activeSession) return;
    setPreviewTask(null);
    setStartError(null);
    setScreen('sandbox');
  }, [activeSession]);

  const handleStartTask = useCallback(
    async (task: Task) => {
      setStartError(null);
      setCheckError(null);
      setStepBanner(null);
      setVictoryData(null);

      if (mode === 'api') {
        setStartingSession(true);
        try {
          const session = await apiStartSession(task.id, task.slug);
          setActiveSession(session);
          setTerminalEntries(buildInitialEntries('api', session));
          setSlots((prev) => ({ ...prev, used: Math.min(prev.max, prev.used + 1) }));
          setPreviewTask(null);
          setScreen('sandbox');
        } catch (err) {
          hapticNotification('error');
          const msg =
            err instanceof Error
              ? err.message
              : 'Не вдалося запустити Docker-контейнер.';
          setStartError(msg);
        } finally {
          setStartingSession(false);
        }
        return;
      }

      // Demo mode start
      const firstStep = task.steps[0] ?? { text: task.description };
      const demoSession: ActiveSession = {
        taskId: task.id,
        slug: task.slug,
        title: task.title,
        step: 0,
        totalSteps: Math.max(1, task.steps.length),
        stepText: firstStep.text,
        hasHint: Boolean(firstStep.hint),
        hintUsed: false,
        hintText: null,
        hintMask: 0,
        cwd: '/home/student',
        expiresIn: sessionTtl,
        rewardPoints: task.rewardPoints,
        currentReward: task.rewardPoints,
      };
      demoStartedAtRef.current = Date.now();
      setDemoFiles(getInitialDemoFiles(task.slug));
      setActiveSession(demoSession);
      setTerminalEntries(buildInitialEntries('demo', demoSession));
      setSlots((prev) => ({ ...prev, used: 1 }));
      setPreviewTask(null);
      setScreen('sandbox');
    },
    [mode, sessionTtl]
  );

  const handleRunCommand = useCallback(
    async (cmd: string) => {
      if (!activeSession) return;
      setCheckError(null);

      if (mode === 'api') {
        const prompt = `student@sandbox:${activeSession.cwd}$`;
        setTerminalEntries((prev) => [...prev, { type: 'cmd', prompt, text: cmd }]);
        setIsExecuting(true);
        try {
          const res = await apiExecCommand(cmd);
          const nextEntries: TerminalEntry[] = [];
          if (res.output) {
            nextEntries.push({ type: 'out', text: res.output });
          } else {
            nextEntries.push({ type: 'system', text: '(порожній вивід)' });
          }
          if (res.timedOut) {
            nextEntries.push({
              type: 'err',
              text: '⏱ Команду перервано через таймаут.',
            });
          }
          setTerminalEntries((prev) => [...prev, ...nextEntries]);
          setActiveSession((prev) => (prev ? { ...prev, cwd: res.cwd } : prev));
        } catch (err) {
          const msg = err instanceof Error ? err.message : 'Помилка виконання команди';
          setTerminalEntries((prev) => [...prev, { type: 'err', text: msg }]);
        } finally {
          setIsExecuting(false);
        }
        return;
      }

      // Demo mode execution
      const result = execDemoCommand(cmd, demoFiles, activeSession.cwd);
      setDemoFiles(result.nextFiles);
      if (result.clear) {
        setTerminalEntries([]);
      } else {
        setTerminalEntries((prev) => [...prev, ...result.entries]);
      }
    },
    [activeSession, mode, demoFiles]
  );

  const handleInterrupt = useCallback(
    (currentInput: string) => {
      if (!activeSession) return;
      const prompt = `student@sandbox:${activeSession.cwd}$`;
      setTerminalEntries((prev) => [
        ...prev,
        { type: 'cmd', prompt, text: `${currentInput}^C` },
      ]);
    },
    [activeSession]
  );

  const handleOpenHint = useCallback(async () => {
    if (!activeSession || !activeSession.hasHint) return;

    if (activeSession.hintUsed && activeSession.hintText) {
      setModalHintText(activeSession.hintText);
      setIsHintOpen(true);
      return;
    }

    if (mode === 'api') {
      setIsHintLoading(true);
      try {
        const res = await apiRequestHint();
        setActiveSession((prev) =>
          prev
            ? {
                ...prev,
                hintUsed: true,
                hintText: res.hint,
                hintMask: res.hintMask,
                currentReward: res.currentReward,
              }
            : prev
        );
        setModalHintText(res.hint);
        setIsHintOpen(true);
      } catch (err) {
        hapticNotification('error');
        setCheckError(
          err instanceof Error ? err.message : 'Не вдалося отримати підказку.'
        );
      } finally {
        setIsHintLoading(false);
      }
      return;
    }

    // Demo mode hint
    const stepObj = activeTask?.steps[activeSession.step];
    const hintText = stepObj?.hint ?? 'Підказка для цього кроку відсутня.';
    const nextMask = activeSession.hintMask | (1 << activeSession.step);
    const nextReward = calcReward(activeSession.rewardPoints, nextMask);

    setActiveSession((prev) =>
      prev
        ? {
            ...prev,
            hintUsed: true,
            hintText,
            hintMask: nextMask,
            currentReward: nextReward,
          }
        : prev
    );
    setModalHintText(hintText);
    setIsHintOpen(true);
  }, [activeSession, activeTask, mode]);

  const handleCheckStep = useCallback(async () => {
    if (!activeSession || !activeTask) return;
    setCheckError(null);

    if (mode === 'api') {
      setIsChecking(true);
      try {
        const res = await apiCheckStep();
        if (!res.passed) {
          hapticNotification('error');
          setCheckError(res.message);
          return;
        }

        hapticNotification('success');
        if (!res.completed) {
          setActiveSession(res.session);
          setStepBanner(
            `Крок ${res.session.step}/${res.session.totalSteps} виконано! Переходимо до наступного.`
          );
          setTerminalEntries((prev) => [
            ...prev,
            {
              type: 'system',
              text: `[ok] Крок ${res.session.step} зараховано! Поточний крок: ${res.session.step + 1}/${res.session.totalSteps}.`,
            },
          ]);
          return;
        }

        // Final step completed!
        setActiveSession(null);
        setUserScore(res.totalScore);
        setTasks((prev) =>
          prev.map((t) => (t.id === activeTask.id ? { ...t, done: true } : t))
        );
        setSlots((prev) => ({ ...prev, used: Math.max(0, prev.used - 1) }));
        setVictoryData({
          task: activeTask,
          awardedPoints: res.awardedPoints,
          maxPoints: res.maxPoints,
          alreadySolved: res.alreadySolved,
          totalScore: res.totalScore,
          timeSpent: formatElapsed(res.timeSpent),
        });
        void refreshBootstrapQuiet();
      } catch (err) {
        hapticNotification('error');
        setCheckError(
          err instanceof Error ? err.message : 'Помилка перевірки кроку.'
        );
      } finally {
        setIsChecking(false);
      }
      return;
    }

    // Demo mode check
    const checkRes = checkDemoStep(activeSession.slug, activeSession.step, demoFiles);
    if (!checkRes.passed) {
      hapticNotification('error');
      setCheckError(checkRes.message ?? 'Крок ще не виконано, спробуй ще.');
      return;
    }

    hapticNotification('success');
    const nextStepIdx = activeSession.step + 1;

    if (nextStepIdx < activeSession.totalSteps) {
      const nextStepObj = activeTask.steps[nextStepIdx] ?? { text: '' };
      const nextHintUsed = Boolean(activeSession.hintMask & (1 << nextStepIdx));
      setActiveSession((prev) =>
        prev
          ? {
              ...prev,
              step: nextStepIdx,
              stepText: nextStepObj.text,
              hasHint: Boolean(nextStepObj.hint),
              hintUsed: nextHintUsed,
              hintText: nextHintUsed ? nextStepObj.hint ?? null : null,
            }
          : prev
      );
      setStepBanner(
        `Крок ${nextStepIdx}/${activeSession.totalSteps} виконано! Переходимо до наступного.`
      );
      setTerminalEntries((prev) => [
        ...prev,
        {
          type: 'system',
          text: `[ok] Крок ${nextStepIdx} зараховано! Поточний крок: ${nextStepIdx + 1}/${activeSession.totalSteps}.`,
        },
      ]);
      return;
    }

    // Final step solved in demo mode
    const alreadySolved = activeTask.done;
    const reward = calcReward(activeSession.rewardPoints, activeSession.hintMask);
    const awardedPoints = alreadySolved ? 0 : reward;
    const nextTotalScore = userScore + awardedPoints;
    const elapsedSeconds = Math.max(
      1,
      Math.round((Date.now() - demoStartedAtRef.current) / 1000)
    );

    if (!alreadySolved) {
      setUserScore(nextTotalScore);
      setTasks((prev) => {
        const updated = prev.map((t) =>
          t.slug === activeTask.slug ? { ...t, done: true } : t
        );
        saveDemoProgress({
          score: nextTotalScore,
          solvedSlugs: updated.filter((t) => t.done).map((t) => t.slug),
        });
        return updated;
      });
    }

    setActiveSession(null);
    setSlots((prev) => ({ ...prev, used: 0 }));
    setVictoryData({
      task: activeTask,
      awardedPoints,
      maxPoints: activeSession.rewardPoints,
      alreadySolved,
      totalScore: nextTotalScore,
      timeSpent: formatElapsed(elapsedSeconds),
    });
  }, [activeSession, activeTask, mode, demoFiles, userScore, refreshBootstrapQuiet]);

  const handleStopSession = useCallback(async () => {
    if (!activeSession) return;

    if (mode === 'api') {
      setIsStopping(true);
      try {
        await apiStopSession();
        setActiveSession(null);
        setSlots((prev) => ({ ...prev, used: Math.max(0, prev.used - 1) }));
        setScreen('hub');
        setIsHintOpen(false);
        setCheckError(null);
      } catch (err) {
        hapticNotification('error');
        setCheckError(
          err instanceof Error ? err.message : 'Не вдалося зупинити контейнер.'
        );
      } finally {
        setIsStopping(false);
      }
      return;
    }

    setActiveSession(null);
    setSlots((prev) => ({ ...prev, used: 0 }));
    setScreen('hub');
    setIsHintOpen(false);
    setCheckError(null);
  }, [activeSession, mode]);

  const handleVictoryToHub = useCallback(() => {
    setVictoryData(null);
    setScreen('hub');
  }, []);

  const handleVictoryToLeaderboard = useCallback(() => {
    setVictoryData(null);
    setScreen('leaderboard');
  }, []);

  return (
    <div className="min-h-[100dvh] h-[100dvh] w-full bg-[#070b0e] text-emerald-50 font-mono flex justify-center overflow-hidden">
      <div className="w-full max-w-md h-full flex flex-col bg-[#070b0e] sm:border-x sm:border-emerald-500/20 relative overflow-hidden">
        <Header
          screen={screen}
          mode={mode}
          onBack={handleBackToHub}
          onClose={closeMiniApp}
        />

        {screen === 'hub' && (
          <HubScreen
            mode={mode}
            tasks={tasks}
            categories={categories}
            telegramUser={telegramUser}
            userScore={userScore}
            maxScore={maxScore}
            userRank={userRank}
            slots={slots}
            activeSession={activeSession}
            selectedCategory={selectedCategory}
            onSelectCategory={setSelectedCategory}
            onSelectTask={(task) => {
              setStartError(null);
              setPreviewTask(task);
            }}
            onResumeSession={handleResumeSession}
          />
        )}

        {screen === 'sandbox' && activeSession && activeTask && (
          <SandboxScreen
            mode={mode}
            task={activeTask}
            session={activeSession}
            entries={terminalEntries}
            demoFiles={demoFiles}
            isExecuting={isExecuting}
            isChecking={isChecking}
            isHintLoading={isHintLoading}
            isStopping={isStopping}
            checkError={checkError}
            stepBanner={stepBanner}
            onDismissCheckError={() => setCheckError(null)}
            onDismissStepBanner={() => setStepBanner(null)}
            onRunCommand={handleRunCommand}
            onClearTerminal={() => setTerminalEntries([])}
            onInterrupt={handleInterrupt}
            onOpenHint={handleOpenHint}
            onCheckStep={handleCheckStep}
            onStopSession={handleStopSession}
          />
        )}

        {screen === 'leaderboard' && (
          <LeaderboardScreen
            mode={mode}
            telegramUser={telegramUser}
            userScore={userScore}
            maxScore={maxScore}
            apiEntries={leaderboardEntries}
            apiMyRank={leaderboardMyRank}
            loading={leaderboardLoading}
            onRefresh={refreshLeaderboard}
          />
        )}

        {screen !== 'sandbox' && (
          <BottomNav screen={screen} onNavigate={setScreen} />
        )}

        <TaskPreviewModal
          task={previewTask}
          activeSession={activeSession}
          sessionTtl={sessionTtl}
          starting={startingSession}
          startError={startError}
          onClose={() => {
            setPreviewTask(null);
            setStartError(null);
          }}
          onStart={handleStartTask}
          onResume={handleResumeSession}
        />

        <HintModal
          isOpen={isHintOpen}
          hint={modalHintText}
          currentReward={activeSession?.currentReward ?? 0}
          maxReward={activeSession?.rewardPoints ?? 0}
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
