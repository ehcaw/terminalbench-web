"use client";

import { useEffect, useState } from "react";
import {
  collection,
  query,
  where,
  getDocs,
  orderBy,
  doc,
  getDoc,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import { useAuth } from "../../contexts/AuthContext";
import { withAuth } from "../../components/withAuth";
import { UserNav } from "@/components/dashboard/user-nav";
import { Button } from "@/components/ui/button";
import { JsonDocumentViewer } from "@/components/ui/json-document-viewer";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Eye, Loader2, AlertCircle } from "lucide-react";

interface UserRun {
  id: string;
  user_id: string;
  task_name?: string;
  status?: string;
  created_at?: any;
  updated_at?: any;
  data?: any;
  [key: string]: any;
}

function CompletedPage() {
  const { user } = useAuth();
  const [userRuns, setUserRuns] = useState<UserRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUserRuns = async () => {
      if (!user?.uid) {
        setError("User not authenticated");
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        console.log("=== DEBUGGING USER RUNS QUERY ===");
        console.log("Current user UID:", user.uid);
        console.log(
          "Expected user_id from Google Studio: CpM5cHrqQseTnFjo5x0NH44rzRI3"
        );
        console.log("Database instance:", db);

        // First, let's get all documents to see what's actually in the collection
        console.log(
          "Step 1: Fetching all documents in user_runs collection..."
        );
        const allDocsQuery = collection(db, "user_runs");
        const allDocsSnapshot = await getDocs(allDocsQuery);

        console.log("Total documents in collection:", allDocsSnapshot.size);

        const allDocs: any[] = [];
        allDocsSnapshot.forEach((doc) => {
          const data = doc.data();
          allDocs.push({ id: doc.id, ...data });
          console.log(`Doc ${doc.id}:`, {
            user_id: data.user_id,
            task_name: data.task_name,
            status: data.status,
          });
        });

        // Now try the filtered query
        console.log("Step 2: Trying filtered query...");
        const filteredQuery = query(
          collection(db, "user_runs"),
          where("user_id", "==", user.uid)
        );

        const querySnapshot = await getDocs(filteredQuery);
        console.log("Filtered query results:", querySnapshot.size);

        const runs: UserRun[] = [];
        querySnapshot.forEach((doc) => {
          console.log("Filtered result:", doc.id, doc.data());
          runs.push({
            id: doc.id,
            ...doc.data(),
          } as UserRun);
        });

        // If no results with current user.uid, let's check if any docs match the expected ID
        if (runs.length === 0) {
          console.log(
            "No results for current user.uid, checking for expected ID..."
          );
          const expectedQuery = query(
            collection(db, "user_runs"),
            where("user_id", "==", "CpM5cHrqQseTnFjo5x0NH44rzRI3")
          );

          const expectedSnapshot = await getDocs(expectedQuery);
          console.log("Results for expected ID:", expectedSnapshot.size);

          if (expectedSnapshot.size > 0) {
            setError(
              `User ID mismatch! Current: ${user.uid}, Expected: CpM5cHrqQseTnFjo5x0NH44rzRI3`
            );
          } else {
            setError(
              `No documents found for either current user (${user.uid}) or expected user (CpM5cHrqQseTnFjo5x0NH44rzRI3)`
            );
          }
        }

        // Sort by created_at if we have results
        runs.sort((a, b) => {
          const aTime = a.created_at?.toDate?.() || new Date(a.created_at || 0);
          const bTime = b.created_at?.toDate?.() || new Date(b.created_at || 0);
          return bTime.getTime() - aTime.getTime();
        });

        setUserRuns(runs);
        console.log("Final runs:", runs);
      } catch (err) {
        console.error("Error fetching user runs:", err);
        setError(
          `Database error: ${
            err instanceof Error ? err.message : "Failed to fetch runs"
          }`
        );
      } finally {
        setLoading(false);
      }
    };

    fetchUserRuns();
  }, [user?.uid]);

  const formatDate = (timestamp: any) => {
    if (!timestamp) return "N/A";

    // Handle Firestore Timestamp
    if (timestamp.toDate) {
      return timestamp.toDate().toLocaleString();
    }

    // Handle regular Date or string
    return new Date(timestamp).toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    const variant =
      status === "completed"
        ? "default"
        : status === "running"
        ? "secondary"
        : status === "failed"
        ? "destructive"
        : "outline";

    return <Badge variant={variant}>{status || "unknown"}</Badge>;
  };

  return (
    <div className="grid min-h-screen w-full lg:grid-cols-[280px_1fr]">
      <div className="hidden border-r bg-gray-100/40 lg:block dark:bg-gray-800/40">
        <div className="flex h-full max-h-screen flex-col gap-2">
          <div className="flex h-[60px] items-center border-b px-6">
            <a className="flex items-center gap-2 font-semibold" href="/">
              <span className="">TerminalBench</span>
            </a>
          </div>
          <div className="flex-1 overflow-auto py-2">
            <nav className="grid items-start px-4 text-sm font-medium">
              <a
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-gray-500 transition-all hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-50"
                href="/"
              >
                Tasks
              </a>
              <a
                className="flex items-center gap-3 rounded-lg bg-gray-100 px-3 py-2 text-gray-900 transition-all hover:text-gray-900 dark:bg-gray-800 dark:text-gray-50"
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
            <h1 className="font-semibold text-lg">Completed Tasks</h1>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
          >
            Refresh
          </Button>
          <UserNav />
        </header>
        <main className="flex flex-1 flex-col gap-4 p-4 md:gap-8 md:p-6">
          <div className="border shadow-sm rounded-lg">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                <span>Loading runs...</span>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center py-8 text-red-500">
                <AlertCircle className="h-5 w-5 mr-2" />
                <span>Error: {error}</span>
              </div>
            ) : userRuns.length === 0 ? (
              <div className="flex items-center justify-center py-8 text-gray-500">
                <span>No completed runs found</span>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Task Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {userRuns.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="font-medium">
                        {run.task_name || run.id}
                      </TableCell>
                      <TableCell>{getStatusBadge(run.status)}</TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {formatDate(run.created_at)}
                      </TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {formatDate(run.updated_at)}
                      </TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button variant="outline" size="sm">
                              <Eye className="h-4 w-4 mr-1" />
                              View Data
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-none w-screen h-screen max-h-screen m-0 rounded-none flex flex-col p-6">
                            <DialogHeader className="pb-4 flex-shrink-0">
                              <DialogTitle className="text-xl">
                                Run Data: {run.task_name || run.id}
                              </DialogTitle>
                            </DialogHeader>
                            <div className="flex-1 min-h-0 overflow-hidden">
                              <JsonDocumentViewer
                                data={run}
                                title={`Run ${run.id}`}
                                defaultView="tree"
                                maxHeight="calc(100vh - 120px)"
                                className="h-full border-0"
                              />
                            </div>
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default withAuth(CompletedPage);
