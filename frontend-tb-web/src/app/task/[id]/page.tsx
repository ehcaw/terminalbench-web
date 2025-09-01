"use client";

import { useEffect, useState, use } from "react";
import dynamic from "next/dynamic";
import { withAuth } from "@/components/withAuth";
import { UserNav } from "@/components/dashboard/user-nav";
import { useAuth } from "../../../contexts/AuthContext";
import { LogsProvider } from "../../../components/terminal/logs-provider";
import { apiGet } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "../../../components/ui/badge";
import { Loader2, AlertCircle } from "lucide-react";

// Dynamically import TerminalLog to avoid SSR issues with xterm
const TerminalLog = dynamic(
  () => import("../../../components/terminal/terminal-log"),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-80 bg-gray-900 rounded-lg">
        <Loader2 className="h-6 w-6 animate-spin text-white" />
        <span className="ml-2 text-white">Loading terminal...</span>
      </div>
    ),
  },
);

interface TaskInfo {
  id: string;
  name: string;
  status: string;
  description?: string;
  created_at?: string;
}

function TaskDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { user } = useAuth();
  const userId = user?.uid || "";
  const resolvedParams = use(params);
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTaskInfo = async () => {
      try {
        setLoading(true);
        setError(null);

        // Try to fetch task information
        // This endpoint might need to be adjusted based on your actual API
        const data = await apiGet(`/tasks/${resolvedParams.id}`);
        setTaskInfo(data);
      } catch (err: unknown) {
        console.error("Failed to fetch task info:", err);
        // If API call fails, create a basic task info object
        setTaskInfo({
          id: resolvedParams.id,
          name: `Task ${resolvedParams.id}`,
          status: "unknown",
        });
        const errorMessage =
          err instanceof Error ? err.message : "Could not load task details";
        setError(errorMessage);
      } finally {
        setLoading(false);
      }
    };

    if (userId && resolvedParams.id) {
      fetchTaskInfo();
    }
  }, [resolvedParams.id, userId]);

  const getStatusBadgeVariant = (status: string) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "success":
        return "default";
      case "running":
      case "active":
        return "secondary";
      case "failed":
      case "error":
        return "destructive";
      default:
        return "outline";
    }
  };

  return (
    <LogsProvider userId={userId}>
      <div className="flex flex-col h-screen">
        <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
          <h1 className="font-semibold text-lg">
            {taskInfo?.name || `Task ${resolvedParams.id}`}
          </h1>
          <div className="ml-auto">
            <UserNav />
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6 space-y-6">
          {/* Task Information Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-xl">Task Details</CardTitle>
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              </div>
              {error && (
                <CardDescription className="flex items-center gap-2 text-amber-600">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-500">
                    Task ID
                  </label>
                  <p className="text-sm font-mono">{resolvedParams.id}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-500">
                    Status
                  </label>
                  <div className="mt-1">
                    <Badge
                      variant={getStatusBadgeVariant(
                        taskInfo?.status || "unknown",
                      )}
                    >
                      {taskInfo?.status || "Unknown"}
                    </Badge>
                  </div>
                </div>
                {taskInfo?.created_at && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">
                      Created
                    </label>
                    <p className="text-sm">
                      {new Date(taskInfo.created_at).toLocaleString()}
                    </p>
                  </div>
                )}
                {taskInfo?.description && (
                  <div className="md:col-span-2">
                    <label className="text-sm font-medium text-gray-500">
                      Description
                    </label>
                    <p className="text-sm text-gray-700">
                      {taskInfo.description}
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Task Logs */}
          <Card>
            <CardHeader>
              <CardTitle>Task Logs</CardTitle>
              <CardDescription>
                Real-time output and logs for this task
              </CardDescription>
            </CardHeader>
            <CardContent>
              {userId ? (
                <TerminalLog
                  userId={userId}
                  taskId={resolvedParams.id}
                  runIndex={1} // Using run index 1 as default for simplified view
                />
              ) : (
                <div className="flex items-center justify-center h-32 text-gray-500">
                  <Loader2 className="h-6 w-6 animate-spin mr-2" />
                  Loading...
                </div>
              )}
            </CardContent>
          </Card>
        </main>
      </div>
    </LogsProvider>
  );
}

export default withAuth(TaskDetailsPage);
