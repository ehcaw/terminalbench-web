"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { withAuth } from "@/components/withAuth";
import { UserNav } from "@/components/dashboard/user-nav";
import TerminalLog from "../../../components/terminal/terminal-log";
import { useAuth } from "../../../contexts/AuthContext";
import { LogsProvider } from "../../../components/terminal/logs-provider";
import { useState, useEffect, use } from "react"; // Add 'use' import
import { useStore } from "../../../lib/store";

interface RunningTask {
  id: string;
  name: string;
  status: string;
  startedAt: string;
  originalTaskId?: string;
  storagePath?: string;
  streamUrl?: string;
}

function TaskDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  // Change params type
  // Unwrap params using React.use()
  const unwrappedParams = use(params);
  const taskId = unwrappedParams.id;

  const { user, getIdToken } = useAuth();
  const userId = user?.uid || "";
  const [activeTab, setActiveTab] = useState("run-1");
  const [startedRuns, setStartedRuns] = useState<Set<string>>(new Set());
  const [currentRunningTask, setCurrentRunningTask] =
    useState<RunningTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runningTasks = useStore((state) => state.runningTasks);
  const addRunningTask = useStore((state) => state.addRunningTask);

  const backendUrl =
    process.env.NODE_ENV === "development"
      ? "http://localhost:8000"
      : "https://tb-web-backend.wache.dev";

  // Construct storage path - fix the leading slash issue
  const storagePath = `tasks/${userId}/${taskId}.zip`;

  useEffect(() => {
    if (user?.uid) {
      checkForExistingRun();
    }
  }, [user?.uid, taskId]);

  const checkForExistingRun = async () => {
    try {
      setIsLoading(true);

      // First check if there's a running task in our store
      const existingTask = runningTasks.find(
        (task) => task.id === taskId || task.originalTaskId === taskId,
      );

      if (existingTask) {
        console.log("Found existing task in store:", existingTask);
        setCurrentRunningTask(existingTask);
        setStartedRuns(new Set(["run-1"]));
        setActiveTab("run-1");
        return;
      }

      // Check with backend for running tasks
      const response = await fetch(
        `${backendUrl}/check-running-tasks?user_id=${userId}&task_id=${taskId}`,
      );

      if (response.ok) {
        const data = await response.json();
        if (data.isRunning) {
          // Task is running, create a task object for it
          const runningTask: RunningTask = {
            id: taskId,
            name: taskId, // We might not have the full name
            status: "running",
            startedAt: new Date().toISOString(),
            streamUrl: `/stream?user_id=${userId}&task_id=${taskId}`,
          };

          setCurrentRunningTask(runningTask);
          setStartedRuns(new Set(["run-1"]));
          setActiveTab("run-1");
          return;
        }
      }

      // No running task found, we'll need to start one
      await startNewTask();
    } catch (err) {
      console.error("Error checking for existing run:", err);
      setError("Failed to check for existing task");
    } finally {
      setIsLoading(false);
    }
  };

  const startNewTask = async () => {
    try {
      const token = await getIdToken();

      const actualStoragePath = storagePath;

      console.log("Starting new task:", { actualStoragePath, taskId });

      const response = await fetch(`${backendUrl}/run-task-from-storage`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          storage_path: actualStoragePath,
          task_name: taskId,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to start task: ${errorText}`);
      }

      const result = await response.json();
      console.log("Task started successfully:", result);

      const newRunningTask: RunningTask = {
        id: result.task_id,
        name: taskId,
        status: "running",
        startedAt: new Date().toISOString(),
        originalTaskId: taskId,
        storagePath: actualStoragePath,
        streamUrl: result.stream_url,
      };

      setCurrentRunningTask(newRunningTask);
      addRunningTask(newRunningTask);
      setStartedRuns(new Set(["run-1"]));
      setActiveTab("run-1");
    } catch (err) {
      console.error("Error starting task:", err);
      setError(err instanceof Error ? err.message : "Failed to start task");
    }
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    if (!startedRuns.has(value)) {
      setStartedRuns((prev) => new Set([...prev, value]));
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
          <h1 className="font-semibold text-lg">Task {taskId}</h1>
          <div className="ml-auto">
            <UserNav />
          </div>
        </header>
        <main className="flex-1 flex items-center justify-center">
          <div className="text-gray-500">Loading task...</div>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-screen">
        <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
          <h1 className="font-semibold text-lg">Task {taskId}</h1>
          <div className="ml-auto">
            <UserNav />
          </div>
        </header>
        <main className="flex-1 flex items-center justify-center">
          <div className="text-red-500">Error: {error}</div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
        <h1 className="font-semibold text-lg">
          Task {currentRunningTask?.name || taskId}
          {currentRunningTask && (
            <span className="ml-2 px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
              {currentRunningTask.status}
            </span>
          )}
        </h1>
        <div className="ml-auto">
          <UserNav />
        </div>
      </header>
      <main className="flex-1 overflow-auto p-4">
        <LogsProvider userId={userId}>
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList>
              {[...Array(10)].map((_, i) => {
                const runValue = `run-${i + 1}`;
                const isStarted = startedRuns.has(runValue);
                const isActive = runValue === "run-1" && currentRunningTask;

                return (
                  <TabsTrigger
                    key={i}
                    value={runValue}
                    className={
                      isStarted || isActive
                        ? "data-[state=active]:bg-green-100 dark:data-[state=active]:bg-green-900"
                        : ""
                    }
                  >
                    Run {i + 1} {(isStarted || isActive) && "●"}
                  </TabsTrigger>
                );
              })}
            </TabsList>

            {[...Array(10)].map((_, i) => {
              const runValue = `run-${i + 1}`;
              const isStarted = startedRuns.has(runValue);
              const isActive = runValue === "run-1" && currentRunningTask;

              return (
                <TabsContent key={i} value={runValue} className="mt-4">
                  {isStarted || isActive ? (
                    <div className="h-96">
                      {" "}
                      {/* Add fixed height container */}
                      <TerminalLog
                        userId={userId}
                        taskId={currentRunningTask?.id || taskId}
                        storagePath={currentRunningTask?.storagePath}
                      />
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-gray-300 rounded-lg text-gray-500">
                      <div className="text-lg font-medium">Run {i + 1}</div>
                      <div className="text-sm mt-2">
                        Click this tab to start a new task execution
                      </div>
                      <div className="text-xs mt-1 text-gray-400">
                        Task: {taskId}
                      </div>
                    </div>
                  )}
                </TabsContent>
              );
            })}
          </Tabs>
        </LogsProvider>
      </main>
    </div>
  );
}

export default withAuth(TaskDetailsPage);
