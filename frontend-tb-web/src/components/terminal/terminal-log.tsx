"use client";
import React, { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { useLogs } from "./logs-provider";

export default function TerminalLog({
  userId,
  taskId,
  runIndex,
}: {
  userId: string;
  taskId: string; // from route param (e.g., params.id)
  runIndex: number; // 1..10
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const { subscribe, startRun, status: sseStatus, lastError } = useLogs();
  const [status, setStatus] = useState("starting…");

  useEffect(() => {
    if (!containerRef.current) return;
    const term = new Terminal({
      convertEol: true,
      cursorBlink: false,
      fontSize: 13,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: "#111111",
        foreground: "#E6E6E6",
        cursor: "#E6E6E6",
      },
      scrollback: 10000,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();
    termRef.current = term;
    fitRef.current = fit;

    const onResize = () => fitRef.current?.fit();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      term.dispose();
      termRef.current = null;
    };
  }, []);

  // Start this run and subscribe to its updates
  useEffect(() => {
    let unsub: (() => void) | undefined;
    let closed = false;

    (async () => {
      setStatus("starting…");
      const started = await startRun(taskId, runIndex);
      if (!started) {
        setStatus("failed");
        return;
      }
      const key = `${taskId}:${started.runId}`;
      setStatus("streaming…");

      unsub = subscribe(key, (msg) => {
        if (!termRef.current) return;
        if (msg.stream === "status" && msg.data.includes("[done]"))
          setStatus("completed");
        termRef.current.write(msg.data);
      });
    })();

    return () => {
      closed = true;
      if (unsub) unsub();
    };
  }, [taskId, runIndex, startRun, subscribe]);

  return (
    <div className="rounded-lg border bg-black">
      <div className="flex items-center justify-between text-xs text-gray-300 bg-gray-800/70 px-2 py-1">
        <span>
          {taskId} • run {runIndex} • {status} • SSE: {sseStatus}
          {lastError ? ` • ${lastError}` : ""}
        </span>
      </div>
      <div ref={containerRef} className="h-[320px] w-full" />
    </div>
  );
}
