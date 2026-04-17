"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listDocuments, fetchModels, type TunablePayload } from "./api";
import { useAppStore } from "./store";
import type { LLMSettings } from "./store";
import type { LLMConfig, ModelInfo } from "./types";
import { buildLLMConfig } from "./store";

export function useDocumentsPolling(intervalMs = 4000) {
  const setDocuments = useAppStore((s) => s.setDocuments);
  const documents = useAppStore((s) => s.documents);

  const refresh = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch {
      /* ignore — backend may be offline */
    }
  }, [setDocuments]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { documents, refresh };
}

export function useInitModels() {
  const setCatalogue = useAppStore((s) => s.setCatalogue);
  const loaded = useAppStore((s) => s.catalogueLoaded);
  useEffect(() => {
    if (loaded) return;
    fetchModels()
      .then(setCatalogue)
      .catch(() => {
        /* keep fallback */
      });
  }, [loaded, setCatalogue]);
}

export function useTunablePayload(): TunablePayload {
  const settings = useAppStore((s) => s.settings);
  const catalogue = useAppStore((s) => s.catalogue);
  const modelInfo = catalogue.models.find((m: ModelInfo) => m.id === settings.model);
  const supportsReasoning = !!modelInfo?.supports_reasoning_effort;
  return {
    llm_config: buildLLMConfig(settings, supportsReasoning),
    similarity_threshold: settings.similarity_threshold,
  };
}

export function useAsync<T, Args extends unknown[]>(
  fn: (...args: Args) => Promise<T>,
): {
  data: T | null;
  error: string | null;
  loading: boolean;
  run: (...args: Args) => Promise<T | null>;
  reset: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async (...args: Args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fnRef.current(...args);
      setData(result);
      return result;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, run, reset };
}

export type { LLMSettings, LLMConfig };
