"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { JsonDocumentViewer } from "@/components/ui/json-document-viewer";
import { useModelConfig } from "@/hooks/use-model-config";

export function AIChatDemo() {
  const [message, setMessage] = useState("");
  const [response, setResponse] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const { config, isValid, makeAIRequest } = useModelConfig();

  const handleSendMessage = async () => {
    if (!message.trim() || !isValid) return;

    setLoading(true);
    try {
      const aiResponse = await makeAIRequest(message);

      // Try to parse as JSON, otherwise treat as string
      let parsedResponse;
      try {
        parsedResponse = JSON.parse(aiResponse);
      } catch {
        parsedResponse = {
          type: "text_response",
          content: aiResponse,
          timestamp: new Date().toISOString(),
          model: `${config?.provider}/${config?.model}`,
        };
      }

      setResponse(parsedResponse);
    } catch (error) {
      setResponse({
        type: "error",
        message: error instanceof Error ? error.message : "Unknown error",
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  if (!isValid) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Terminal Bench Runner</CardTitle>
          <CardDescription>
            Configure your AI model settings using the settings button in the
            header to try this demo.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Terminal Bench Runner</CardTitle>
        <CardDescription>
          Using {config?.provider} - {config?.model}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Ask the AI something..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
          />
          <Button
            onClick={handleSendMessage}
            disabled={loading || !message.trim()}
          >
            {loading ? "Sending..." : "Send"}
          </Button>
        </div>
        {response && (
          <JsonDocumentViewer
            data={response}
            title="AI Response"
            defaultView="tree"
            maxHeight="300px"
          />
        )}
      </CardContent>
    </Card>
  );
}
