"use client";

import React, { useState, useCallback } from 'react';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { CheckCircle, XCircle, Upload, FileArchive, AlertCircle } from "lucide-react";
import { uploadTaskZip, ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface ValidationResult {
  valid: boolean;
  checks: {
    tests_dir_has_test_outputs: boolean;
    solution_present: boolean;
    task_yaml_present: boolean;
    docker_requirement_ok: boolean;
    dockerfiles_found: number;
    docker_compose_present: boolean;
  };
  errors: string[];
  files_seen: string[];
  uploaded_by?: {
    uid: string;
    email: string;
  };
}

export function TaskUpload() {
  const { user } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFileSelect = useCallback((selectedFile: File) => {
    if (selectedFile.type !== "application/zip" && !selectedFile.name.endsWith('.zip')) {
      setError("Please select a ZIP file");
      return;
    }

    if (selectedFile.size > 100 * 1024 * 1024) { // 100MB limit
      setError("File size must be less than 100MB");
      return;
    }

    setFile(selectedFile);
    setError(null);
    setResult(null);
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      handleFileSelect(selectedFile);
    }
  };

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setDragOver(false);

    const droppedFile = event.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  }, [handleFileSelect]);

  const handleUpload = async () => {
    if (!file || !user) return;

    setUploading(true);
    setUploadProgress(0);
    setError(null);
    setResult(null);

    try {
      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      const uploadResult = await uploadTaskZip(file);

      clearInterval(progressInterval);
      setUploadProgress(100);
      setResult(uploadResult);
    } catch (err) {
      console.error('Upload error:', err);

      if (err instanceof ApiError) {
        if (err.data?.errors) {
          setResult(err.data);
        } else {
          setError(err.message);
        }
      } else {
        setError('An unexpected error occurred during upload');
      }
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const renderValidationResults = () => {
    if (!result) return null;

    const { valid, checks, errors, files_seen } = result;

    return (
      <div className="space-y-4">
        <Alert className={valid ? "border-green-500 bg-green-50" : "border-red-500 bg-red-50"}>
          <div className="flex items-center gap-2">
            {valid ? (
              <CheckCircle className="h-4 w-4 text-green-600" />
            ) : (
              <XCircle className="h-4 w-4 text-red-600" />
            )}
            <AlertDescription className={valid ? "text-green-800" : "text-red-800"}>
              {valid ? "Task validation successful!" : "Task validation failed"}
            </AlertDescription>
          </div>
        </Alert>

        {!valid && errors.length > 0 && (
          <Card className="border-red-200">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-red-800">Validation Errors</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {errors.map((error, index) => (
                  <li key={index} className="text-sm text-red-700 flex items-start gap-2">
                    <XCircle className="h-3 w-3 mt-0.5 flex-shrink-0" />
                    {error}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Validation Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid grid-cols-1 gap-2 text-sm">
              <div className="flex items-center justify-between">
                <span>Tests directory with test_outputs.py:</span>
                {checks.tests_dir_has_test_outputs ? (
                  <CheckCircle className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span>Solution file (yaml/sh):</span>
                {checks.solution_present ? (
                  <CheckCircle className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span>Task YAML file:</span>
                {checks.task_yaml_present ? (
                  <CheckCircle className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <span>Docker configuration:</span>
                {checks.docker_requirement_ok ? (
                  <CheckCircle className="h-4 w-4 text-green-600" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-600" />
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {files_seen.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Files Found ({files_seen.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="max-h-32 overflow-y-auto">
                <ul className="space-y-1 text-xs text-gray-600">
                  {files_seen.map((file, index) => (
                    <li key={index} className="font-mono">{file}</li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Upload Task
          </CardTitle>
          <CardDescription>
            Upload a ZIP file containing your task directory. The task must include required files for validation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* File Drop Zone */}
          <div
            className={`border-2 border-dashed rounded-lg p-6 transition-colors ${
              dragOver
                ? "border-blue-400 bg-blue-50"
                : "border-gray-300 hover:border-gray-400"
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="flex flex-col items-center justify-center text-center">
              <FileArchive className="h-12 w-12 text-gray-400 mb-4" />
              <p className="text-sm text-gray-600 mb-2">
                Drag and drop your ZIP file here, or click to browse
              </p>
              <input
                type="file"
                accept=".zip"
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
              />
              <Button
                variant="outline"
                onClick={() => document.getElementById('file-upload')?.click()}
                disabled={uploading}
              >
                Choose File
              </Button>
            </div>
          </div>

          {/* Selected File Info */}
          {file && (
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <FileArchive className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="text-sm font-medium">{file.name}</p>
                  <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFile(null)}
                disabled={uploading}
              >
                Remove
              </Button>
            </div>
          )}

          {/* Upload Progress */}
          {uploading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <Progress value={uploadProgress} className="h-2" />
            </div>
          )}

          {/* Error Display */}
          {error && (
            <Alert className="border-red-500 bg-red-50">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">{error}</AlertDescription>
            </Alert>
          )}

          {/* Upload Button */}
          <Button
            onClick={handleUpload}
            disabled={!file || uploading || !user}
            className="w-full"
          >
            {uploading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Upload and Validate
              </>
            )}
          </Button>

          {!user && (
            <p className="text-sm text-gray-500 text-center">
              Please sign in to upload tasks.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Validation Results */}
      {renderValidationResults()}

      {/* Requirements Info */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Required Files</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm text-gray-600">
            <li className="flex items-start gap-2">
              <CheckCircle className="h-3 w-3 mt-0.5 text-green-600 flex-shrink-0" />
              <span><code>tests/test_outputs.py</code> or <code>test/test_outputs.py</code></span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-3 w-3 mt-0.5 text-green-600 flex-shrink-0" />
              <span><code>solution.yaml</code> or <code>solution.sh</code></span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-3 w-3 mt-0.5 text-green-600 flex-shrink-0" />
              <span><code>task.yaml</code></span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle className="h-3 w-3 mt-0.5 text-green-600 flex-shrink-0" />
              <span>Either a single <code>Dockerfile</code> or <code>docker-compose.yaml</code></span>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
