"use client";

import { useState, useEffect } from "react";
import { Settings } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ModelConfig {
  provider: string;
  model: string;
  apiKey: string;
}

const PROVIDERS = [
  {
    name: "OpenAI",
    value: "openai",
    models: ["gpt-5", "gpt-4.4", "gpt-3.5-turbo"],
  },
  {
    name: "Anthropic",
    value: "anthropic",
    models: ["claude-4-sonnet", "claude-3-7-sonnet-latest", "claude-opus-4"],
  },
  {
    name: "Google",
    value: "google",
    models: ["gemini-2.5-pro", "gemini-2.0-flash-exp"],
  },
];

export function ModelSelectorDialog() {
  const [open, setOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("openai");
  const [selectedModel, setSelectedModel] = useState("gpt-4");
  const [apiKey, setApiKey] = useState("");

  // Load saved configuration on mount
  useEffect(() => {
    const savedConfig = localStorage.getItem("modelConfig");
    if (savedConfig) {
      try {
        const config: ModelConfig = JSON.parse(savedConfig);
        setSelectedProvider(config.provider);
        setSelectedModel(config.model);
        setApiKey(config.apiKey);
      } catch (error) {
        console.error("Failed to parse saved model config:", error);
      }
    }
  }, []);

  const handleSave = () => {
    const config: ModelConfig = {
      provider: selectedProvider,
      model: selectedModel,
      apiKey,
    };

    localStorage.setItem("modelConfig", JSON.stringify(config));

    // Dispatch custom event to notify other components
    window.dispatchEvent(new CustomEvent("modelConfigChanged"));

    setOpen(false);
  };

  const selectedProviderData = PROVIDERS.find(
    (p) => p.value === selectedProvider,
  );
  const availableModels = selectedProviderData?.models || [];

  // Update model when provider changes
  useEffect(() => {
    if (selectedProviderData && !availableModels.includes(selectedModel)) {
      setSelectedModel(availableModels[0] || "");
    }
  }, [selectedProvider, selectedProviderData, availableModels, selectedModel]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="icon">
          <Settings className="h-4 w-4" />
          <span className="sr-only">Model Settings</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Model Configuration</DialogTitle>
          <DialogDescription>
            Configure your AI model provider and API key. Your API key is stored
            locally and sent securely.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="provider">Provider</Label>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="justify-between">
                  {selectedProviderData?.name || "Select Provider"}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                {PROVIDERS.map((provider) => (
                  <DropdownMenuItem
                    key={provider.value}
                    onClick={() => setSelectedProvider(provider.value)}
                  >
                    {provider.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="model">Model</Label>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="justify-between">
                  {selectedModel || "Select Model"}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                {availableModels.map((model) => (
                  <DropdownMenuItem
                    key={model}
                    onClick={() => setSelectedModel(model)}
                  >
                    {model}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="apiKey">API Key</Label>
            <Input
              id="apiKey"
              type="password"
              placeholder="Enter your API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button type="submit" onClick={handleSave}>
            Save Configuration
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
