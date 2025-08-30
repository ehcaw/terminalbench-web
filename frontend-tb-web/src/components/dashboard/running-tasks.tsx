import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useStore } from "@/lib/store";
import Link from "next/link";

export function RunningTasks({ tasks }) {
  const removeRunningTask = useStore((state) => state.removeRunningTask);
  const addCompletedTask = useStore((state) => state.addCompletedTask);

  const handleComplete = (task) => {
    removeRunningTask(task.id);
    addCompletedTask({ ...task, status: "Completed" });
  };

  return (
    <div className="border shadow-sm rounded-lg p-4">
      <h2 className="font-semibold mb-4">Running Tasks</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tasks.map((task) => (
            <TableRow key={task.id}>
              <TableCell>{task.name}</TableCell>
              <TableCell>{task.status}</TableCell>
              <TableCell>
                <Link href={`/task/${task.id}`}>
                  <Button size="sm" className="mr-2">View</Button>
                </Link>
                <Button size="sm" onClick={() => handleComplete(task)}>Mark as Completed</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
