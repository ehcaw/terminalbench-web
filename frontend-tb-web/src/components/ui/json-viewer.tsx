"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Copy, Check } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

interface JsonViewerProps {
  data: any;
  className?: string;
  maxHeight?: string;
  searchable?: boolean;
}

interface JsonNodeProps {
  data: any;
  keyName?: string;
  level?: number;
  isLast?: boolean;
  searchTerm?: string;
}

export function JsonViewer({
  data,
  className,
  maxHeight = "400px",
  searchable = true,
}: JsonViewerProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div
      className={cn("border rounded-lg bg-gray-50 dark:bg-gray-900", className)}
    >
      <div className="flex items-center justify-between p-3 border-b bg-gray-100 dark:bg-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">JSON Data</span>
          <span className="text-xs text-gray-500">
            {typeof data === "object" && data !== null
              ? `${Object.keys(data).length} ${
                  Array.isArray(data) ? "items" : "properties"
                }`
              : typeof data}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {searchable && (
            <input
              type="text"
              placeholder="Search..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="px-2 py-1 text-xs border rounded bg-white dark:bg-gray-700 dark:border-gray-600"
            />
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="h-7 px-2"
          >
            {copied ? (
              <Check className="h-3 w-3" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        </div>
      </div>
      <div
        className="p-3 overflow-auto font-mono text-sm"
        style={{ maxHeight }}
      >
        <JsonNode data={data} searchTerm={searchTerm} />
      </div>
    </div>
  );
}

function JsonNode({
  data,
  keyName,
  level = 0,
  isLast = true,
  searchTerm,
}: JsonNodeProps) {
  const [isExpanded, setIsExpanded] = useState(level < 2); // Auto-expand first 2 levels

  const indent = "  ".repeat(level);
  const hasChildren = typeof data === "object" && data !== null;
  const isArray = Array.isArray(data);

  // Highlight search matches
  const highlightText = (text: string) => {
    if (!searchTerm || !text.toLowerCase().includes(searchTerm.toLowerCase())) {
      return text;
    }

    const regex = new RegExp(`(${searchTerm})`, "gi");
    const parts = text.split(regex);

    return parts.map((part, index) =>
      regex.test(part) ? (
        <mark
          key={index}
          className="bg-yellow-200 dark:bg-yellow-800 px-1 rounded"
        >
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  if (!hasChildren) {
    // Leaf node (primitive value)
    const valueColor =
      typeof data === "string"
        ? "text-green-600 dark:text-green-400"
        : typeof data === "number"
        ? "text-blue-600 dark:text-blue-400"
        : typeof data === "boolean"
        ? "text-purple-600 dark:text-purple-400"
        : "text-gray-600 dark:text-gray-400";

    const displayValue = typeof data === "string" ? `"${data}"` : String(data);

    return (
      <div className="flex">
        <span className="text-gray-400">{indent}</span>
        {keyName && (
          <>
            <span className="text-blue-700 dark:text-blue-300">
              {highlightText(`"${keyName}"`)}
            </span>
            <span className="text-gray-500">: </span>
          </>
        )}
        <span className={valueColor}>{highlightText(displayValue)}</span>
        {!isLast && <span className="text-gray-500">,</span>}
      </div>
    );
  }

  // Container node (object or array)
  const entries = isArray
    ? data.map((item: any, index: number) => [index, item])
    : Object.entries(data);

  const openBracket = isArray ? "[" : "{";
  const closeBracket = isArray ? "]" : "}";

  return (
    <div>
      <div className="flex items-center">
        <span className="text-gray-400">{indent}</span>
        {hasChildren && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mr-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded p-0.5"
          >
            {isExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
        )}
        {keyName && (
          <>
            <span className="text-blue-700 dark:text-blue-300">
              {highlightText(`"${keyName}"`)}
            </span>
            <span className="text-gray-500">: </span>
          </>
        )}
        <span className="text-gray-500">{openBracket}</span>
        {!isExpanded && (
          <>
            <span className="text-gray-400 mx-1">
              {entries.length} {isArray ? "items" : "properties"}
            </span>
            <span className="text-gray-500">{closeBracket}</span>
            {!isLast && <span className="text-gray-500">,</span>}
          </>
        )}
      </div>

      {isExpanded && (
        <>
          {entries.map(([key, value], index) => (
            <JsonNode
              key={key}
              data={value}
              keyName={isArray ? undefined : String(key)}
              level={level + 1}
              isLast={index === entries.length - 1}
              searchTerm={searchTerm}
            />
          ))}
          <div className="flex">
            <span className="text-gray-400">{indent}</span>
            <span className="text-gray-500">{closeBracket}</span>
            {!isLast && <span className="text-gray-500">,</span>}
          </div>
        </>
      )}
    </div>
  );
}
