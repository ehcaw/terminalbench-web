"use client";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useAuth } from "../../contexts/AuthContext";

type Msg = {
  type: "status" | "output" | "complete" | "error";
  content: string;
  taskId: string;
  runId: string;
  seq: number;
  timestamp: number;
  isError?: boolean;
  result?: any; // For complete messages
};

type Subscriber = (msg: Msg) => void;

type Ctx = {
  subscribe: (key: string, fn: Subscriber) => () => void;
  startRun: (
    storagePath: string,
    taskName: string,
  ) => Promise<{ taskId: string; runId: string; streamUrl: string } | null>;
  status: "connecting" | "open" | "error" | "closed";
  lastError: string | null;
};

const LogsCtx = createContext<Ctx | null>(null);

export function LogsProvider({
  userId,
  apiBaseUrl = process.env.NODE_ENV == "development"
    ? "http://localhost:8000"
    : "https://tb-web-backend.wache.dev",
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

  const { getIdToken } = useAuth();

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

    es.onopen = () => {
      setStatus("open");
      setLastError(null); // Clear errors on successful connection
    };

    es.onerror = () => {
      setStatus("error");
      setLastError("SSE connection error");
    };

    // Listen for ping events (heartbeat)
    es.addEventListener("ping", () => {
      // Just a keepalive, no action needed
    });

    es.addEventListener("task-output", (evt: MessageEvent) => {
      try {
        const msg = JSON.parse(evt.data) as Msg;
        const key = `${msg.taskId}:${msg.runId}`;
        const set = subsRef.current.get(key);
        if (set) {
          // Pass the message directly - no need to transform
          set.forEach((fn) => fn(msg));
        }
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
    async (storagePath: string, taskName: string) => {
      try {
        // Get Firebase auth token
        const token = await getIdToken();
        if (!token) {
          throw new Error("No authentication token available");
        }

        const res = await fetch(
          `${apiBaseUrl.replace(/\/+$/, "")}/run-task-from-storage`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({
              storage_path: storagePath,
              task_name: taskName,
            }),
          },
        );

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(
            errorData.detail ||
              errorData.message ||
              `HTTP ${res.status}: Failed to start run`,
          );
        }

        const data = await res.json();
        return {
          taskId: data.task_id,
          runId: data.task_id, // Backend uses task_id as runId
          streamUrl: data.stream_url,
        };
      } catch (e: any) {
        console.error("Failed to start run:", e);
        setLastError(e.message);
        return null;
      }
    },
    [apiBaseUrl, getIdToken],
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
