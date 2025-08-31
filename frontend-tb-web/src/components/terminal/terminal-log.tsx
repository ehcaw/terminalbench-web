"use client";
import React, { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import { useLogs } from "./logs-provider";

export default function TerminalLog({
  userId,
  storagePath,
  taskId,
}: {
  userId: string;
  storagePath?: string;
  taskId: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const { subscribe, startRun, status: sseStatus, lastError } = useLogs();
  const [status, setStatus] = useState("starting…");
  const [runId, setRunId] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Add timeout to ensure container is properly rendered
    const timer = setTimeout(() => {
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

      // Add safety check before fitting
      const tryFit = () => {
        try {
          if (containerRef.current && containerRef.current.offsetWidth > 0) {
            fit.fit();
          }
        } catch (err) {
          console.warn("Terminal fit failed:", err);
        }
      };

      // Try fitting after a short delay
      setTimeout(tryFit, 100);

      termRef.current = term;
      fitRef.current = fit;

      const onResize = () => {
        setTimeout(tryFit, 100); // Add delay for resize too
      };

      window.addEventListener("resize", onResize);

      // Cleanup function
      return () => {
        window.removeEventListener("resize", onResize);
        term.dispose();
        termRef.current = null;
        fitRef.current = null;
      };
    }, 100);

    return () => {
      clearTimeout(timer);
    };
  }, []);

  // Start this run and subscribe to its updates
  useEffect(() => {
    if (!storagePath) {
      setStatus("No storage path provided");
      return;
    }

    let unsub: (() => void) | undefined;

    (async () => {
      setStatus("starting…");
      const result = await startRun(storagePath, taskId);
      if (!result) {
        setStatus("failed to start");
        return;
      }

      setRunId(result.runId);
      const key = `${result.taskId}:${result.runId}`;
      setStatus("streaming…");

      unsub = subscribe(key, (msg) => {
        if (!termRef.current) return;

        // Handle different message types
        if (msg.type === "complete") {
          const result = msg.result;
          if (result.status === "success") {
            setStatus("✅ completed successfully");
          } else {
            setStatus(`❌ failed (exit ${result.exit_code})`);
          }
          return;
        }

        if (msg.type === "status" && msg.content.includes("completed")) {
          setStatus("✅ completed");
        } else if (msg.type === "status" && msg.content.includes("failed")) {
          setStatus("❌ failed");
        }

        // Write output to terminal
        termRef.current.write(msg.content + "\n");
      });
    })();

    return () => {
      if (unsub) unsub();
    };
  }, [startRun, subscribe, storagePath, taskId]);

  return (
    <div className="rounded-lg border bg-black">
      <div className="flex items-center justify-between text-xs text-gray-300 bg-gray-800/70 px-2 py-1">
        <span>
          {taskId} • {status} • SSE: {sseStatus}
          {lastError ? ` • ${lastError}` : ""}
        </span>
      </div>
      <div
        ref={containerRef}
        className="h-[400px] w-full"
        style={{ minHeight: "400px", minWidth: "100%" }} // Add explicit sizing
      />
    </div>
  );
}
