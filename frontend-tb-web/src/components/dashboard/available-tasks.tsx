"use client";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEffect, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";

interface AvailableTask {
  id: string;
  name: string;
  description?: string;
  difficulty?: string;
  category?: string;
  createdAt?: string;
}

export function AvailableTasks() {
  const [tasks, setTasks] = useState<AvailableTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user, getIdToken } = useAuth();

  const apiUrl =
    process.env.NODE_ENV == "development"
      ? "http://localhost:8000"
      : "https://tb-web-backend.wache.dev";

  useEffect(() => {
    if (user?.uid) {
      fetchAvailableTasks();
    }
  }, [user?.uid]);

  const fetchAvailableTasks = async () => {
    if (!user?.uid) {
      setError("User not authenticated");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);

      const response = await fetch(
        `/api/tb-tasks/available?userId=${user.uid}`,
      );

      if (!response.ok) {
        throw new Error("Failed to fetch available tasks");
      }
      const data = await response.json();
      setTasks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleStartTask = async (taskName: string) => {
    if (!user?.uid) {
      setError("User not authenticated");
      return;
    }

    const token = await getIdToken();
    try {
      const response = await fetch(`${apiUrl}/run-task-from-storage`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          task_name: taskName,
          storage_path: `tasks/${user.uid}/${taskName}.zip`,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to start task");
      }

      // Refresh the available tasks list
      fetchAvailableTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start task");
    }
  };

  if (loading) {
    return (
      <div className="border shadow-sm rounded-lg p-4">
        <h2 className="font-semibold mb-4">Available Tasks</h2>
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">Loading tasks...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border shadow-sm rounded-lg p-4">
        <h2 className="font-semibold mb-4">Available Tasks</h2>
        <div className="flex items-center justify-center py-8">
          <div className="text-red-500">Error: {error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="border shadow-sm rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-semibold">Available Tasks</h2>
        <Button variant="outline" size="sm" onClick={fetchAvailableTasks}>
          Refresh
        </Button>
      </div>

      {tasks.length === 0 ? (
        <div className="flex items-center justify-center py-8">
          <div className="text-gray-500">No available tasks found</div>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Difficulty</TableHead>
              <TableHead>Category</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.map((task) => (
              <TableRow key={task.id}>
                <TableCell className="font-medium">{task.name}</TableCell>
                <TableCell className="max-w-xs truncate">
                  {task.description || "No description"}
                </TableCell>
                <TableCell>
                  <span
                    className={`px-2 py-1 rounded-full text-xs ${
                      task.difficulty === "Easy"
                        ? "bg-green-100 text-green-800"
                        : task.difficulty === "Medium"
                          ? "bg-yellow-100 text-yellow-800"
                          : task.difficulty === "Hard"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {task.difficulty || "Unknown"}
                  </span>
                </TableCell>
                <TableCell>{task.category || "General"}</TableCell>
                <TableCell>
                  <Button size="sm" onClick={() => handleStartTask(task.name)}>
                    Start Task
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
