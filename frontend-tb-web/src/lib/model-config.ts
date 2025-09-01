export interface ModelConfig {
  provider: string;
  model: string;
  apiKey: string;
}

export function getModelConfig(): ModelConfig | null {
  if (typeof window === "undefined") return null;

  try {
    const savedConfig = localStorage.getItem("modelConfig");
    if (!savedConfig) return null;

    return JSON.parse(savedConfig) as ModelConfig;
  } catch (error) {
    console.error("Failed to parse model config:", error);
    return null;
  }
}

export function hasValidModelConfig(): boolean {
  const config = getModelConfig();
  return !!(config?.provider && config?.model && config?.apiKey);
}
