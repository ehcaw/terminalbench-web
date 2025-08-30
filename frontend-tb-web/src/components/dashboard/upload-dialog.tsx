"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useStore } from "../../lib/store";
import { useAuth } from "../../contexts/AuthContext";
import { PlusCircle, AlertCircle, CheckCircle } from "lucide-react";
import { useState } from "react";

export function UploadDialog() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const addRunningTask = useStore((state) => state.addRunningTask);
  const { getIdToken } = useAuth();

  const backendEndpoint =
    process.env.NODE_ENV === "development"
      ? "http://localhost:8000"
      : "tb-web-backend.wache.dev";

  // Reset states when dialog opens/closes
  const handleOpenChange = (open: boolean) => {
    setIsOpen(open);
    if (!open) {
      setError(null);
      setSuccess(null);
      setFile(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0] || null;
    setFile(selectedFile);
    setError(null);
    setSuccess(null);

    // Basic client-side validation
    if (selectedFile && !selectedFile.name.toLowerCase().endsWith(".zip")) {
      setError("Please select a .zip file containing your task directory.");
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file to upload.");
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      // Get the Firebase ID token
      const token = await getIdToken();
      if (!token) {
        setError("Authentication failed. Please sign in again.");
        return;
      }

      // Create FormData for file upload
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${backendEndpoint}/upload-task`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        // Handle different types of errors from the backend
        if (result.detail && typeof result.detail === "object") {
          setError(
            result.detail.user_message ||
              result.detail.message ||
              "Upload failed",
          );
        } else if (typeof result.detail === "string") {
          setError(result.detail);
        } else {
          setError(`Upload failed: ${response.statusText}`);
        }
        return;
      }

      // Success!
      console.log("Upload successful:", result);
      setSuccess(`Task "${file.name}" uploaded and validated successfully!`);

      const newTask = {
        id: Date.now(),
        name: file.name.replace(".zip", ""),
        status: "Running" as const,
      };
      addRunningTask(newTask);

      // Close dialog after a short delay to show success message
      setTimeout(() => {
        setIsOpen(false);
      }, 2000);
    } catch (error) {
      console.error("Upload error:", error);
      setError(
        "Network error occurred. Please check your connection and try again.",
      );
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <PlusCircle className="mr-2 h-4 w-4" />
          Upload Task
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Task</DialogTitle>
          <DialogDescription>
            Select a .zip file containing your task directory. The file will be
            validated to ensure it contains the required structure.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="task-file">Task File (.zip)</Label>
            <Input
              id="task-file"
              type="file"
              accept=".zip"
              onChange={handleFileChange}
              disabled={uploading}
            />
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Success Alert */}
          {success && (
            <Alert className="border-green-200 bg-green-50 text-green-800">
              <CheckCircle className="h-4 w-4" />
              <AlertDescription>{success}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setIsOpen(false)}
            disabled={uploading}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            onClick={handleUpload}
            disabled={!file || uploading || !!error}
          >
            {uploading ? "Uploading..." : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
