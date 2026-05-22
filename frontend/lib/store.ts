"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  ChatMessage,
  DocumentInfo,
  LLMConfig,
  ModelCatalogue,
} from "./types";

export interface LLMSettings {
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  seed: number | null;
  reasoning_effort: "low" | "medium" | "high";
  top_k: number;
  similarity_threshold: number;
}

export const FALLBACK_CATALOGUE: ModelCatalogue = {
  default: "llama-3.3-70b-versatile",
  models: [
    {
      id: "llama-3.3-70b-versatile",
      label: "Llama 3.3 70B — Balanced default",
      family: "Meta",
      best_for: "General research Q&A, summarization, everyday RAG",
      supports_reasoning_effort: false,
    },
  ],
  defaults: {
    temperature: 0.2,
    max_tokens: 2048,
    top_p: 1.0,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    reasoning_effort: "medium",
    top_k: 10,
    similarity_threshold: 0.3,
  },
};

function defaultSettings(cat: ModelCatalogue): LLMSettings {
  return {
    model: cat.default,
    temperature: cat.defaults.temperature,
    max_tokens: cat.defaults.max_tokens,
    top_p: cat.defaults.top_p,
    frequency_penalty: cat.defaults.frequency_penalty,
    presence_penalty: cat.defaults.presence_penalty,
    seed: null,
    reasoning_effort: cat.defaults.reasoning_effort,
    top_k: cat.defaults.top_k,
    similarity_threshold: cat.defaults.similarity_threshold,
  };
}

interface AppState {
  // Model catalogue
  catalogue: ModelCatalogue;
  catalogueLoaded: boolean;
  setCatalogue: (c: ModelCatalogue) => void;

  // LLM settings
  settings: LLMSettings;
  setSetting: <K extends keyof LLMSettings>(key: K, value: LLMSettings[K]) => void;
  resetSettings: () => void;
  applyPreset: (preset: "precise" | "balanced" | "creative") => void;

  // Documents
  documents: DocumentInfo[];
  setDocuments: (docs: DocumentInfo[]) => void;

  // Chat
  messages: ChatMessage[];
  pushMessage: (m: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  clearMessages: () => void;

  // Chat mode
  agentMode: boolean;
  multiDocMode: boolean;
  setAgentMode: (v: boolean) => void;
  setMultiDocMode: (v: boolean) => void;

  // Chat filter
  chatFilter: string;
  setChatFilter: (filter: string) => void;

  // Theme
  theme: "dark" | "light";
  toggleTheme: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      catalogue: FALLBACK_CATALOGUE,
      catalogueLoaded: false,
      setCatalogue: (c) =>
        set((s) => {
          const keepSettings =
            s.catalogueLoaded &&
            c.models.some((m) => m.id === s.settings.model);
          return {
            catalogue: c,
            catalogueLoaded: true,
            settings: keepSettings ? s.settings : defaultSettings(c),
          };
        }),

      settings: defaultSettings(FALLBACK_CATALOGUE),
      setSetting: (key, value) =>
        set((s) => ({ settings: { ...s.settings, [key]: value } })),
      resetSettings: () =>
        set((s) => ({ settings: defaultSettings(s.catalogue) })),
      applyPreset: (preset) =>
        set((s) => {
          const next = { ...s.settings };
          if (preset === "precise") {
            next.temperature = 0.1;
            next.top_p = 1.0;
          } else if (preset === "balanced") {
            next.temperature = 0.5;
            next.top_p = 1.0;
          } else {
            next.temperature = 0.9;
            next.top_p = 0.95;
          }
          return { settings: next };
        }),

      documents: [],
      setDocuments: (docs) => set({ documents: docs }),

      messages: [],
      pushMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
      updateMessage: (id, patch) =>
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === id ? { ...m, ...patch } : m,
          ),
        })),
      clearMessages: () => set({ messages: [] }),

      agentMode: false,
      multiDocMode: false,
      setAgentMode: (v) => set({ agentMode: v }),
      setMultiDocMode: (v) => set({ multiDocMode: v }),

      chatFilter: "__all__",
      setChatFilter: (filter) => set({ chatFilter: filter }),

      theme: "dark",
      toggleTheme: () =>
        set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),
    }),
    {
      name: "research-assistant-state",
      partialize: (state) => ({
        settings: state.settings,
        messages: state.messages.slice(-50),
        agentMode: state.agentMode,
        chatFilter: state.chatFilter,
        theme: state.theme,
      }),
    },
  ),
);

export function buildLLMConfig(settings: LLMSettings, modelSupportsReasoning: boolean): LLMConfig {
  const cfg: LLMConfig = {
    model: settings.model,
    temperature: settings.temperature,
    max_tokens: settings.max_tokens,
    top_p: settings.top_p,
    frequency_penalty: settings.frequency_penalty,
    presence_penalty: settings.presence_penalty,
  };
  if (settings.seed != null) cfg.seed = settings.seed;
  if (modelSupportsReasoning) cfg.reasoning_effort = settings.reasoning_effort;
  return cfg;
}
