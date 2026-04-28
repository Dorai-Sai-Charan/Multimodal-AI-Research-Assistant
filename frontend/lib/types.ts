// Mirrors Pydantic models in src/api/routes.py

export interface LLMConfig {
  model?: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  seed?: number | null;
  reasoning_effort?: "low" | "medium" | "high";
}

export interface Citation {
  source_file: string;
  page_number: number;
  section?: string;
  relevance_score: number;
  [k: string]: unknown;
}

export interface ReasoningStep {
  step: number;
  thought: string;
  action: string;
  action_input: string | Record<string, any>;
  observation: string;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  query: string;
  intent: string;
  chunks_used: number;
}

export interface AgentQueryResponse extends QueryResponse {
  reasoning_steps: ReasoningStep[];
  total_steps: number;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  file_type: string;
  total_pages: number;
  total_chunks: number;
  status: "processing" | "completed" | "failed" | string;
  ingested_at: string;
}

export interface ModelInfo {
  id: string;
  label: string;
  family: string;
  best_for: string;
  supports_reasoning_effort: boolean;
}

export interface ModelCatalogue {
  default: string;
  models: ModelInfo[];
  defaults: {
    temperature: number;
    max_tokens: number;
    top_p: number;
    frequency_penalty: number;
    presence_penalty: number;
    reasoning_effort: "low" | "medium" | "high";
    top_k: number;
    similarity_threshold: number;
  };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  reasoning_steps?: ReasoningStep[];
  chunks_used?: number;
  total_steps?: number;
  mode?: "rag" | "agent" | "multi-doc";
  error?: boolean;
}
