"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { withAuth } from "@/components/withAuth";
import { UserNav } from "@/components/dashboard/user-nav";
import TerminalLog from "../../../components/terminal/terminal-log";
import { useAuth } from "../../../contexts/AuthContext";

function TaskDetailsPage({ params }: { params: { id: string } }) {
  const { user } = useAuth();
  const userId = user?.uid || "";
  return (
    <div className="flex flex-col h-screen">
      <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
        <h1 className="font-semibold text-lg">Task {params.id}</h1>
        <div className="ml-auto">
          <UserNav />
        </div>
      </header>
      <main className="flex-1 overflow-auto p-4">
        <Tabs defaultValue="run-1">
          <TabsList>
            {[...Array(10)].map((_, i) => (
              <TabsTrigger key={i} value={`run-${i + 1}`}>
                Run {i + 1}
              </TabsTrigger>
            ))}
          </TabsList>
          {[...Array(10)].map((_, i) => (
            <TabsContent key={i} value={`run-${i + 1}`}>
              {/*<div className="bg-gray-900 text-white font-mono text-sm p-4 rounded-lg">
                <p>Run {i + 1} output...</p>
              </div>*/}
              <TerminalLog
                userId={userId}
                taskId={params.id}
                runIndex={i + 1}
              />
            </TabsContent>
          ))}
        </Tabs>
      </main>
    </div>
  );
}

export default withAuth(TaskDetailsPage);
