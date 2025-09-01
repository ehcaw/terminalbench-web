import { useState, useEffect } from "react";
import {
  getModelConfig,
  hasValidModelConfig,
  type ModelConfig,
} from "@/lib/model-config";

export function useModelConfig() {
  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [isValid, setIsValid] = useState(false);

  useEffect(() => {
    const loadConfig = () => {
      const modelConfig = getModelConfig();
      setConfig(modelConfig);
      setIsValid(hasValidModelConfig());
    };

    // Load initial config
    loadConfig();

    // Listen for storage changes (when config is updated in another tab or component)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "modelConfig") {
        loadConfig();
      }
    };

    window.addEventListener("storage", handleStorageChange);

    // Also listen for custom events (when config is updated in the same tab)
    const handleConfigChange = () => loadConfig();
    window.addEventListener("modelConfigChanged", handleConfigChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("modelConfigChanged", handleConfigChange);
    };
  }, []);

  const makeAIRequest = async (message: string) => {
    if (!config || !isValid) {
      throw new Error("Model configuration is not set up");
    }

    const response = await fetch("/api/ai-chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        modelConfig: config,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to make AI request");
    }

    const data = await response.json();
    return data.response;
  };

  return {
    config,
    isValid,
    makeAIRequest,
  };
}
