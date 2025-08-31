import { create } from "zustand";

interface Task {
  id: string;
  name: string;
  status: string;
  startedAt: string;
  originalTaskId?: string;
  storagePath?: string;
  streamUrl?: string;
}

interface Store {
  runningTasks: Task[];
  completedTasks: Task[];
  setRunningTasks: (tasks: Task[]) => void;
  setCompletedTasks: (tasks: Task[]) => void;
  addRunningTask: (task: Task) => void;
  addCompletedTask: (task: Task) => void;
  removeRunningTask: (id: string) => void;
}

export const useStore = create<Store>((set) => ({
  runningTasks: [],
  completedTasks: [],
  setRunningTasks: (tasks) => set({ runningTasks: tasks }),
  setCompletedTasks: (tasks) => set({ completedTasks: tasks }),
  addRunningTask: (task) =>
    set((state) => ({ runningTasks: [...state.runningTasks, task] })),
  addCompletedTask: (task) =>
    set((state) => ({ completedTasks: [...state.completedTasks, task] })),
  removeRunningTask: (id) =>
    set((state) => ({
      runningTasks: state.runningTasks.filter((t) => t.id !== id),
    })),
}));
