"use client";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

type Msg = {
  taskId: string;
  runId: string;
  seq: number;
  stream: "stdout" | "stderr" | "status";
  data: string;
};
type Subscriber = (msg: Msg) => void;

type Ctx = {
  subscribe: (key: string, fn: Subscriber) => () => void;
  startRun: (
    taskId: string,
    runIndex: number,
  ) => Promise<{ runId: string } | null>;
  status: "connecting" | "open" | "error" | "closed";
  lastError: string | null;
};

const LogsCtx = createContext<Ctx | null>(null);

export function LogsProvider({
  userId,
  apiBaseUrl = process.env.NEXT_PUBLIC_REACT_APP_API_URL || "",
  children,
}: {
  userId: string;
  apiBaseUrl?: string;
  children: React.ReactNode;
}) {
  const subsRef = useRef(new Map<string, Set<Subscriber>>());
  const esRef = useRef<EventSource | null>(null);
  const [status, setStatus] = useState<Ctx["status"]>("connecting");
  const [lastError, setLastError] = useState<string | null>(null);

  // Open ONE SSE per user
  useEffect(() => {
    if (!userId) return;
    esRef.current?.close();
    const base = apiBaseUrl.replace(/\/+$/, "");
    const es = new EventSource(
      `${base}/stream?user_id=${encodeURIComponent(userId)}`,
      { withCredentials: true },
    );
    esRef.current = es;

    es.onopen = () => setStatus("open");
    es.onerror = () => {
      setStatus("error");
      setLastError("SSE connection error");
    };

    es.addEventListener("task-output", (evt: MessageEvent) => {
      try {
        const msg = JSON.parse(evt.data) as Msg;
        const key = `${msg.taskId}:${msg.runId}`;
        const set = subsRef.current.get(key);
        if (set) set.forEach((fn) => fn(msg));
      } catch (e) {
        console.error("Bad SSE payload", e, evt.data);
      }
    });

    return () => {
      es.close();
      setStatus("closed");
    };
  }, [apiBaseUrl, userId]);

  const subscribe = useCallback((key: string, fn: Subscriber) => {
    let set = subsRef.current.get(key);
    if (!set) {
      set = new Set();
      subsRef.current.set(key, set);
    }
    set.add(fn);
    return () => {
      set!.delete(fn);
      if (set!.size === 0) subsRef.current.delete(key);
    };
  }, []);

  const startRun = useCallback(
    async (taskId: string, runIndex: number) => {
      try {
        const res = await fetch(
          `${apiBaseUrl.replace(/\/+$/, "")}/tasks/start`,
          {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              user_id: userId,
              task_id: taskId,
              run_index: runIndex,
            }),
          },
        );
        if (!res.ok)
          throw new Error(
            (await res.json().catch(() => ({}) as any)).detail ||
              "Failed to start run",
          );
        const data = await res.json();
        return { runId: data.run_id as string };
      } catch (e: any) {
        console.error(e);
        setLastError(e.message);
        return null;
      }
    },
    [apiBaseUrl, userId],
  );

  return (
    <LogsCtx.Provider value={{ subscribe, startRun, status, lastError }}>
      {children}
    </LogsCtx.Provider>
  );
}

export function useLogs() {
  const ctx = useContext(LogsCtx);
  if (!ctx) throw new Error("useLogs must be used within LogsProvider");
  return ctx;
}
