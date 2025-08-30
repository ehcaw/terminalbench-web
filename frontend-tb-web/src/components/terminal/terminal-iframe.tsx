import React, { useEffect, useRef, useState, useCallback } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { AttachAddon } from "xterm-addon-attach";
import "xterm/css/xterm.css";

interface TerminalIframeProps {
  userId: string;
  apiBaseUrl?: string;
}

const TerminalIframe: React.FC<TerminalIframeProps> = ({
  userId,
  apiBaseUrl = process.env.NEXT_PUBLIC_REACT_APP_API_URL || "",
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState("Loading...");
  const [error, setError] = useState<string | null>(null);
  const terminal = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);

  const ws = useRef<WebSocket | null>(null);

  const initializeTerminal = useCallback(async () => {
    try {
      if (!userId) {
        throw new Error("User ID is required");
      }

      setStatus("Connecting...");
      console.log(`Starting terminal session for user: ${userId}`);

      // Start terminal session
      const response = await fetch(`${apiBaseUrl}/terminal/start`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error("Failed to start terminal:", errorData);
        throw new Error(errorData.detail || "Failed to start terminal");
      }

      const data = await response.json();
      const sid = data.session_id;

      // Create WebSocket connection
      let wsUrl: string;
      // Handle production vs development URLs
      if (apiBaseUrl.startsWith("http")) {
        // Convert http(s) to ws(s) for the base URL
        wsUrl = apiBaseUrl.replace(/^http/, "ws");
      } else {
        // Fallback for relative URLs or protocol-relative URLs
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const cleanBaseUrl = apiBaseUrl.replace(/^\/+/, "");
        wsUrl = `${protocol}//${window.location.host}${cleanBaseUrl ? `/${cleanBaseUrl}` : ""}`;
      }

      // Add WebSocket endpoint and session ID
      wsUrl = `${wsUrl.replace(/\/+$/, "")}/terminal/ws/${sid}`.replace(
        /([^:]\/)\/+/g,
        "$1",
      );
      console.log("WebSocket URL:", wsUrl);

      console.log("Creating WebSocket with URL:", wsUrl);

      try {
        ws.current = new WebSocket(wsUrl);
        // Set binary type to arraybuffer for better binary data handling
        ws.current.binaryType = "arraybuffer";

        // Add event listeners for debugging
        ws.current!.onopen = () => {
          setStatus("Connected");
          if (terminal.current) {
            terminal.current.focus();
          }

          // tell the backend our size…
          const dimensions = fitAddon.current!.proposeDimensions() || {
            rows: 24,
            cols: 80,
          };
          const rows = Math.max(10, Math.min(50, dimensions.rows || 24));
          const cols = Math.max(20, Math.min(200, dimensions.cols || 80));
          ws.current!.send(JSON.stringify({ type: "resize", rows, cols }));

          // hook up xterm ↔ websocket (this wires both onData and onmessage)
          if (terminal.current && ws.current) {
            terminal.current!.loadAddon(new AttachAddon(ws.current!));
          }
        };

        ws.current.onerror = (error) => {
          console.error("WebSocket error:", error);
          console.error("WebSocket readyState:", ws.current?.readyState);
          setError("WebSocket connection error");
          setStatus("Error");
        };

        ws.current.onclose = (event) => {
          console.log("WebSocket closed:", {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
          });
          setStatus("Disconnected");

          if (event.code !== 1000) {
            setError(`Connection closed: ${event.reason || "Unknown reason"}`);
          }
        };
      } catch (err) {
        console.error("Failed to create WebSocket:", err);
        setError("Failed to create WebSocket connection");
        setStatus("Error");
        return;
      }
    } catch (err) {
      console.error("Terminal initialization error:", err);
      setError(
        err instanceof Error ? err.message : "Failed to initialize terminal",
      );
    }
  }, [apiBaseUrl, userId]);

  // Re-initialize terminal when userId changes
  useEffect(() => {
    if (!terminalRef.current) return;

    // Clean up previous terminal instance if it exists
    if (terminal.current) {
      terminal.current.dispose();
      terminal.current = null;
    }

    // Don't initialize if no userId
    if (!userId) return;

    // Initialize terminal
    terminal.current = new Terminal({
      cursorBlink: true,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: 14,
      theme: {
        background: "#1e1e1e",
        foreground: "#f0f0f0",
        cursor: "#f0f0f0",
        cursorAccent: "#1e1e1e",
      },
      allowTransparency: true,
      scrollback: 10000,
      convertEol: true,
      disableStdin: false,
      windowsMode: false,
      screenReaderMode: false,
      macOptionIsMeta: false,
      macOptionClickForcesSelection: false,
      rightClickSelectsWord: true,
      tabStopWidth: 8,
      drawBoldTextInBrightColors: true,
      fastScrollModifier: "alt",
      fastScrollSensitivity: 5,
      letterSpacing: 0,
      lineHeight: 1.2,
      minimumContrastRatio: 1,
      overviewRulerWidth: 10,
      scrollSensitivity: 1,
      smoothScrollDuration: 100,
      wordSeparator: " ()[]{}'\"",
    });

    fitAddon.current = new FitAddon();
    terminal.current.loadAddon(fitAddon.current);
    terminal.current.open(terminalRef.current);
    fitAddon.current.fit();

    initializeTerminal();

    // Cleanup on unmount or when userId changes
    return () => {
      // Close WebSocket connection
      if (ws.current) {
        try {
          ws.current.close();
        } catch (e) {
          console.error("Error closing WebSocket:", e);
        }
        ws.current = null;
      }

      // Clean up terminal
      if (terminal.current) {
        try {
          terminal.current.dispose();
        } catch (e) {
          console.error("Error disposing terminal:", e);
        }
        terminal.current = null;
      }

      // Clean up container if needed
      const cleanupContainer = async () => {
        if (!userId || userId === "undefined") {
          console.warn("No user ID provided for cleanup");
          return;
        }

        try {
          console.log(`Cleaning up container for user: ${userId}`);
          const response = await fetch(
            `${apiBaseUrl}/terminal/cleanup/${userId}`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
            },
          );

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error("Cleanup failed:", errorData);
            return;
          }

          const result = await response.json();
          console.log("Container cleanup result:", result);
        } catch (error) {
          console.error("Error cleaning up container:", error);
        }
      };

      cleanupContainer();
    };
  }, [apiBaseUrl, userId, initializeTerminal]);

  // Handle window resize
  useEffect(() => {
    const doResize = () => {
      if (
        !fitAddon.current ||
        !ws.current ||
        ws.current.readyState !== WebSocket.OPEN
      )
        return;
      fitAddon.current.fit();
      const { rows, cols } = fitAddon.current.proposeDimensions()!;
      ws.current.send(JSON.stringify({ type: "resize", rows, cols }));
    };

    const debounced = debounce(doResize, 100);
    window.addEventListener("resize", debounced);
    doResize(); // initial

    return () => window.removeEventListener("resize", debounced);
  }, []);

  const refreshWs = () => {
    if (ws.current) {
      ws.current.close(1000, "Manual Refresh");
    }
    initializeTerminal();
  };

  // Simple debounce function
  function debounce<T extends (...args: any[]) => void>(
    func: T,
    wait: number,
  ): (...args: Parameters<T>) => void {
    let timeout: NodeJS.Timeout;
    return function (this: ThisParameterType<T>, ...args: Parameters<T>) {
      const context = this;
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(context, args), wait);
    };
  }

  if (!userId) {
    return (
      <div className="flex items-center justify-center h-full bg-black text-gray-400 p-4">
        Please sign in to use the terminal
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-black text-red-400 p-4">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between bg-gray-800 text-white p-2 text-sm">
        <span>Terminal {status && `(${status})`}</span>
        <button
          onClick={refreshWs}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white transition-colors"
          title="Restart terminal session"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span className="text-sm">Restart</span>
        </button>
      </div>
      <div ref={terminalRef} className="h-full w-full bg-black" />
    </div>
  );
};

export default TerminalIframe;
