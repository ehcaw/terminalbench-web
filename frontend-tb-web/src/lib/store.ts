import { create } from 'zustand'

export const useStore = create((set) => ({
  runningTasks: [],
  completedTasks: [],
  setRunningTasks: (tasks) => set({ runningTasks: tasks }),
  setCompletedTasks: (tasks) => set({ completedTasks: tasks }),
  addRunningTask: (task) => set((state) => ({ runningTasks: [...state.runningTasks, task] })),
  addCompletedTask: (task) => set((state) => ({ completedTasks: [...state.completedTasks, task] })),
  removeRunningTask: (id) => set((state) => ({ runningTasks: state.runningTasks.filter((t) => t.id !== id) })),
}))
