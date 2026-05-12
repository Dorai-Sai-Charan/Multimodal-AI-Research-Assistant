/**
 * Typed client for the FastAPI backend.
 * All calls go through the Next.js proxy at /api/* which forwards to
 * BACKEND_API_URL (default http://localhost:8000/api).
 * The backend is unchanged from the original Streamlit project.
 */

import type {
  AgentQueryResponse,
  AIDetectionResponse,
  DocumentInfo,
  HumanizationResponse,
  LLMConfig,
  ModelCatalogue,
  QueryResponse,
} from "./types";

const BASE = "/api";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 300_000,
): Promise<T> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctl.signal,
      headers: {
        ...(init.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        detail = data.detail ?? detail;
      } catch {}
      throw new ApiError(detail, res.status);
    }
    return (await res.json()) as T;
  } catch (e: unknown) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(
        "Request timed out. The server may be rate-limited — please wait and try again.",
        408,
      );
    }
    const msg = e instanceof Error ? e.message : String(e);
    if (msg.includes("fetch")) {
      throw new ApiError(
        "Cannot connect to the API server. Start it with `python -m src.main`.",
        503,
      );
    }
    throw new ApiError(msg, 500);
  } finally {
    clearTimeout(t);
  }
}

export interface TunablePayload {
  llm_config?: LLMConfig;
  similarity_threshold?: number;
}

// ---------------- Documents ----------------

export async function listDocuments(): Promise<DocumentInfo[]> {
  return request<DocumentInfo[]>("/documents", { method: "GET" }, 30_000);
}

export async function uploadDocument(file: File): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  return request<DocumentInfo>(
    "/upload",
    { method: "POST", body: form },
    60_000,
  );
}

export async function deleteDocument(id: string): Promise<{ message: string }> {
  return request<{ message: string }>(
    `/documents/${encodeURIComponent(id)}`,
    { method: "DELETE" },
    30_000,
  );
}

// ---------------- Models ----------------

export async function fetchModels(): Promise<ModelCatalogue> {
  return request<ModelCatalogue>("/models", { method: "GET" }, 10_000);
}

// ---------------- RAG features ----------------

export async function query(
  payload: TunablePayload & {
    question: string;
    top_k?: number;
    filter_source?: string | null;
  },
): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function agentQuery(
  payload: TunablePayload & {
    question: string;
    chat_history: { role: string; content: string }[];
    filter_source?: string | null;
  },
): Promise<AgentQueryResponse> {
  return request<AgentQueryResponse>(
    "/agent",
    { method: "POST", body: JSON.stringify(payload) },
    180_000,
  );
}

export async function multiDocQuery(
  payload: TunablePayload & { question: string; top_k?: number },
): Promise<QueryResponse> {
  return request<QueryResponse>("/multi-doc", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function comparePapers(
  payload: TunablePayload & { paper1: string; paper2: string },
): Promise<QueryResponse> {
  return request<QueryResponse>(
    "/compare",
    { method: "POST", body: JSON.stringify(payload) },
    120_000,
  );
}

export async function literatureSurvey(
  payload: TunablePayload & { topic: string; top_k?: number },
): Promise<QueryResponse> {
  return request<QueryResponse>(
    "/literature-survey",
    { method: "POST", body: JSON.stringify(payload) },
    180_000,
  );
}

export async function researchGaps(
  payload: TunablePayload & { source_file?: string | null },
): Promise<QueryResponse> {
  return request<QueryResponse>(
    "/research-gaps",
    { method: "POST", body: JSON.stringify(payload) },
    120_000,
  );
}

export async function explainConcept(
  payload: TunablePayload & { concept: string; source_file?: string | null },
): Promise<QueryResponse> {
  return request<QueryResponse>("/explain", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function recommendPapers(
  payload: TunablePayload & { interest: string; top_k?: number },
): Promise<QueryResponse> {
  return request<QueryResponse>("/recommend", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function researchTrends(
  payload: TunablePayload,
): Promise<QueryResponse> {
  return request<QueryResponse>(
    "/trends",
    { method: "POST", body: JSON.stringify(payload) },
    180_000,
  );
}

export async function summarize(
  payload: TunablePayload & {
    source_file?: string | null;
    top_k?: number;
  },
): Promise<QueryResponse> {
  return request<QueryResponse>(
    "/summarize",
    { method: "POST", body: JSON.stringify(payload) },
    180_000,
  );
}

// ---------------- Humanizer ----------------

export async function detectAI(
  payload: { text: string },
): Promise<AIDetectionResponse> {
  return request<AIDetectionResponse>(
    "/detect-ai",
    { method: "POST", body: JSON.stringify(payload) },
    60_000,
  );
}

export async function humanizeText(
  payload: { text: string },
): Promise<HumanizationResponse> {
  return request<HumanizationResponse>(
    "/humanize",
    { method: "POST", body: JSON.stringify(payload) },
    180_000,
  );
}

export { ApiError };
