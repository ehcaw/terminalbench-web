"use client";

import { RunningTasks } from "@/components/dashboard/running-tasks";
import { UploadDialog } from "@/components/dashboard/upload-dialog";
import { useStore } from "@/lib/store";
import Link from "next/link";

import { withAuth } from "@/components/withAuth";

import { UserNav } from "@/components/dashboard/user-nav";

function Home() {
  const runningTasks = useStore((state) => state.runningTasks);

  return (
    <div className="grid min-h-screen w-full lg:grid-cols-[280px_1fr]">
      <div className="hidden border-r bg-gray-100/40 lg:block dark:bg-gray-800/40">
        <div className="flex h-full max-h-screen flex-col gap-2">
          <div className="flex h-[60px] items-center border-b px-6">
            <Link className="flex items-center gap-2 font-semibold" href="/">
              <span className="">TerminalBench</span>
            </Link>
          </div>
          <div className="flex-1 overflow-auto py-2">
            <nav className="grid items-start px-4 text-sm font-medium">
              <Link
                className="flex items-center gap-3 rounded-lg bg-gray-100 px-3 py-2 text-gray-900 transition-all hover:text-gray-900 dark:bg-gray-800 dark:text-gray-50"
                href="/"
              >
                Tasks
              </Link>
              <a
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-gray-500 transition-all hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-50"
                href="/completed"
              >
                Completed
              </a>
            </nav>
          </div>
        </div>
      </div>
      <div className="flex flex-col">
        <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
          <div className="flex-1">
            <h1 className="font-semibold text-lg">Tasks</h1>
          </div>
          <UploadDialog />
          <UserNav />
        </header>
        <main className="flex flex-1 flex-col gap-4 p-4 md:gap-8 md:p-6">
          <RunningTasks tasks={runningTasks} />
        </main>
      </div>
    </div>
  );
}

export default withAuth(Home);
