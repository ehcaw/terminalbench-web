"use client";

import { useState, useMemo } from "react";
import {
  Search,
  Copy,
  Check,
  Download,
  Maximize2,
  Minimize2,
  Eye,
  Code,
  List,
} from "lucide-react";
import { Button } from "./button";
import { Input } from "./input";
import { JsonViewer } from "./json-viewer";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./tabs";

interface JsonDocumentViewerProps {
  data: any;
  title?: string;
  className?: string;
  defaultView?: "tree" | "raw" | "table";
  maxHeight?: string;
}

export function JsonDocumentViewer({
  data,
  title = "JSON Document",
  className,
  defaultView = "tree",
  maxHeight = "500px",
}: JsonDocumentViewerProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [copied, setCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentView, setCurrentView] = useState(defaultView);

  const jsonString = useMemo(() => JSON.stringify(data, null, 2), [data]);

  const filteredData = useMemo(() => {
    if (!searchTerm) return data;

    const filterObject = (obj: any): any => {
      if (typeof obj !== "object" || obj === null) {
        return String(obj).toLowerCase().includes(searchTerm.toLowerCase())
          ? obj
          : null;
      }

      if (Array.isArray(obj)) {
        const filtered = obj.map(filterObject).filter((item) => item !== null);
        return filtered.length > 0 ? filtered : null;
      }

      const filtered: any = {};
      let hasMatch = false;

      for (const [key, value] of Object.entries(obj)) {
        if (key.toLowerCase().includes(searchTerm.toLowerCase())) {
          filtered[key] = value;
          hasMatch = true;
        } else {
          const filteredValue = filterObject(value);
          if (filteredValue !== null) {
            filtered[key] = filteredValue;
            hasMatch = true;
          }
        }
      }

      return hasMatch ? filtered : null;
    };

    return filterObject(data) || {};
  }, [data, searchTerm]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(jsonString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.toLowerCase().replace(/\s+/g, "-")}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getDataSize = () => {
    const size = new Blob([jsonString]).size;
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getObjectStats = (
    obj: any
  ): { objects: number; arrays: number; primitives: number } => {
    let objects = 0;
    let arrays = 0;
    let primitives = 0;

    const traverse = (item: any) => {
      if (typeof item === "object" && item !== null) {
        if (Array.isArray(item)) {
          arrays++;
          item.forEach(traverse);
        } else {
          objects++;
          Object.values(item).forEach(traverse);
        }
      } else {
        primitives++;
      }
    };

    traverse(obj);
    return { objects, arrays, primitives };
  };

  const stats = useMemo(() => getObjectStats(data), [data]);

  const renderTableView = () => {
    if (!Array.isArray(data)) {
      return (
        <div className="p-4 text-center text-gray-500">
          Table view is only available for array data
        </div>
      );
    }

    if (data.length === 0) {
      return (
        <div className="p-4 text-center text-gray-500">No data to display</div>
      );
    }

    // Get all unique keys from all objects
    const allKeys = Array.from(
      new Set(
        data.flatMap((item) =>
          typeof item === "object" && item !== null ? Object.keys(item) : []
        )
      )
    );

    return (
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 dark:bg-gray-800">
            <tr>
              {allKeys.map((key) => (
                <th key={key} className="px-3 py-2 text-left font-medium">
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((item, index) => (
              <tr key={index} className="border-t">
                {allKeys.map((key) => (
                  <td key={key} className="px-3 py-2 max-w-xs truncate">
                    {typeof item === "object" && item !== null
                      ? typeof item[key] === "object"
                        ? JSON.stringify(item[key])
                        : String(item[key] ?? "")
                      : String(item)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const ViewerContent = () => (
    <div
      className={cn("border rounded-lg bg-white dark:bg-gray-900", className)}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b bg-gray-50 dark:bg-gray-800">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold">{title}</h3>
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span>Size: {getDataSize()}</span>
            <span>Objects: {stats.objects}</span>
            <span>Arrays: {stats.arrays}</span>
            <span>Values: {stats.primitives}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search in JSON..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 w-48"
            />
          </div>
          <Button variant="ghost" size="sm" onClick={handleCopy}>
            {copied ? (
              <Check className="h-4 w-4" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDownload}>
            <Download className="h-4 w-4" />
          </Button>
          {!isFullscreen && (
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="ghost" size="sm">
                  <Maximize2 className="h-4 w-4" />
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-6xl h-[80vh]">
                <DialogHeader>
                  <DialogTitle>{title}</DialogTitle>
                </DialogHeader>
                <JsonDocumentViewer
                  data={data}
                  title={title}
                  defaultView={currentView}
                  maxHeight="calc(80vh - 120px)"
                />
              </DialogContent>
            </Dialog>
          )}
        </div>
      </div>

      {/* View Tabs */}
      <Tabs
        value={currentView}
        onValueChange={(value) => setCurrentView(value as any)}
      >
        <div className="border-b">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="tree" className="flex items-center gap-2">
              <List className="h-4 w-4" />
              Tree View
            </TabsTrigger>
            <TabsTrigger value="raw" className="flex items-center gap-2">
              <Code className="h-4 w-4" />
              Raw JSON
            </TabsTrigger>
            <TabsTrigger value="table" className="flex items-center gap-2">
              <Eye className="h-4 w-4" />
              Table View
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="tree" className="m-0">
          <div style={{ maxHeight }} className="overflow-auto">
            <JsonViewer
              data={filteredData}
              searchable={false}
              className="border-0 rounded-none"
            />
          </div>
        </TabsContent>

        <TabsContent value="raw" className="m-0">
          <div style={{ maxHeight }} className="overflow-auto">
            <pre className="p-4 text-sm font-mono whitespace-pre-wrap bg-gray-50 dark:bg-gray-900">
              {jsonString}
            </pre>
          </div>
        </TabsContent>

        <TabsContent value="table" className="m-0">
          <div style={{ maxHeight }} className="overflow-auto">
            {renderTableView()}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );

  return <ViewerContent />;
}
