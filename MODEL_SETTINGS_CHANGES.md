# Model & Parameter Configuration — Change Log

This document describes the changes made to add a **user-facing model selection
and parameter tuning panel** to the Multimodal AI Research Assistant.

Before this change, the backend was hardcoded to use `llama-3.3-70b-versatile`
with fixed generation parameters. After this change, users can pick from a
curated list of Groq models and tune all important generation/retrieval
parameters from a sidebar settings panel in the Streamlit UI.

---

## 1. High-level summary

| Area | Before | After |
|---|---|---|
| Model | Hardcoded `llama-3.3-70b-versatile` in `llm_client.py` | 7 curated models, user-selectable |
| Generation params | Fixed `temperature=0.2`, `max_tokens=2048` | Temperature, max_tokens, top_p, frequency/presence penalty, seed, reasoning_effort — all tunable |
| Retrieval params | Fixed `top_k=10`, no threshold filtering | `top_k` and `similarity_threshold` tunable |
| Presets | None | 🎯 Precise / ⚖️ Balanced / 🎨 Creative one-click buttons |
| Model guidance | None | Every model has a "Best for" hint shown under the dropdown |
| Parameter help | None | Every slider has a one-sentence tooltip explaining what it does |

---

## 2. Files changed

### 2.1 `src/config.py`

Added default values for model and generation parameters to the `Settings`
class so they can be overridden from `.env` or the frontend.

```python
# LLM generation defaults (overridable per request from the UI)
llm_model: str = "llama-3.3-70b-versatile"
llm_temperature: float = 0.2
llm_max_tokens: int = 2048
llm_top_p: float = 1.0
llm_frequency_penalty: float = 0.0
llm_presence_penalty: float = 0.0
llm_reasoning_effort: str = "medium"  # low | medium | high
```

---

### 2.2 `src/generation/llm_client.py`

- **Removed** the hardcoded `GROQ_MODEL = "llama-3.3-70b-versatile"` constant.
- Added a `REASONING_MODELS` whitelist — the `reasoning_effort` parameter is
  only sent to models that support it (GPT-OSS, Qwen3, Groq Compound).
- `LLMClient.generate()` now accepts an `llm_config: dict | None` override:

  ```python
  def generate(
      self,
      prompt: str,
      temperature: float | None = None,
      max_tokens: int | None = None,
      llm_config: dict | None = None,
  ) -> str:
  ```

- Added a `_resolve_config()` helper that merges user overrides with the
  `Settings` defaults. User-supplied values win; unset fields fall back to defaults.
- All supported params are now forwarded to the Groq API:
  `model`, `temperature`, `max_tokens`, `top_p`, `frequency_penalty`,
  `presence_penalty`, `seed`, `reasoning_effort`.
- `generate_with_context()` now also accepts `llm_config` and forwards it.

---

### 2.3 `src/retrieval/retriever.py`

Added a `similarity_threshold` parameter to `Retriever.retrieve()`. After the
vector store returns the top-k chunks, results below the threshold are filtered
out, so the LLM only sees chunks the user considers "relevant enough".

```python
def retrieve(
    self,
    query: str,
    top_k: int = 10,
    filter_source: str | None = None,
    filter_type: str | None = None,
    similarity_threshold: float | None = None,
) -> list[QueryResult]:
```

---

### 2.4 `src/retrieval/rag_pipeline.py`

**Every public method** now accepts two optional kwargs:

- `llm_config: dict | None` — forwarded to `llm_client.generate_with_context()`
- `similarity_threshold: float | None` — forwarded to `retriever.retrieve()`

Methods updated:

| Method | Feature |
|---|---|
| `query` | Single-shot RAG Q&A |
| `summarize` | Document summarization |
| `compare` | Two-paper comparison |
| `literature_survey` | Literature survey generation |
| `identify_gaps` | Research gap identification |
| `explain` | Concept / diagram / table explanation |
| `recommend` | Paper recommendation |
| `analyze_trends` | Research trend analysis |
| `multi_doc_query` | Multi-document reasoning |

---

### 2.5 `src/agents/research_agent.py`

`ResearchAgent.run()` now accepts `llm_config` and forwards it to **both**
`llm.generate()` calls inside the ReAct loop (the per-iteration
Thought/Action generation and the final synthesis call when `MAX_ITERATIONS`
is reached).

---

### 2.6 `src/api/routes.py`

#### New pydantic models

```python
class LLMConfig(BaseModel):
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    seed: int | None = None
    reasoning_effort: str | None = None  # "low" | "medium" | "high"


class TunableRequest(BaseModel):
    """Shared base for requests that allow LLM + retrieval overrides."""
    llm_config: LLMConfig | None = None
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
```

All feature request classes (`QueryRequest`, `AgentQueryRequest`,
`SummarizeRequest`, `CompareRequest`, `LiteratureSurveyRequest`,
`ResearchGapsRequest`, `ExplainRequest`, `RecommendRequest`, `TrendsRequest`,
`MultiDocRequest`) now inherit from `TunableRequest`, so they all accept these
fields automatically.

#### Helper

```python
def _llm_kwargs(req: TunableRequest) -> dict:
    return {
        "llm_config": req.llm_config.model_dump(exclude_none=True) if req.llm_config else None,
        "similarity_threshold": req.similarity_threshold,
    }
```

Every route that calls the RAG pipeline now passes `**_llm_kwargs(request)`.
The `/trends` route was updated to accept a body (`TrendsRequest`) so it can
also honour model settings.

#### New endpoint — `GET /api/models`

Returns the curated model catalogue with usage guidance plus server-side
defaults:

```json
{
  "default": "llama-3.3-70b-versatile",
  "models": [
    {
      "id": "openai/gpt-oss-120b",
      "label": "GPT-OSS 120B — Highest quality",
      "family": "OpenAI",
      "best_for": "Deep reasoning, literature surveys, complex multi-hop questions",
      "supports_reasoning_effort": true
    },
    ...
  ],
  "defaults": {
    "temperature": 0.2, "max_tokens": 2048, "top_p": 1.0,
    "frequency_penalty": 0.0, "presence_penalty": 0.0,
    "reasoning_effort": "medium", "top_k": 10, "similarity_threshold": 0.3
  }
}
```

**Curated model shortlist:**

| ID | Label | Best for | Reasoning effort? |
|---|---|---|---|
| `openai/gpt-oss-120b` | GPT-OSS 120B — Highest quality | Deep reasoning, literature surveys, complex multi-hop questions | ✅ |
| `openai/gpt-oss-20b` | GPT-OSS 20B — Fast & capable | Quick Q&A with good reasoning when latency matters | ✅ |
| `llama-3.3-70b-versatile` | Llama 3.3 70B — Balanced default | General research Q&A, summarization, everyday RAG | ❌ |
| `llama-3.1-8b-instant` | Llama 3.1 8B — Ultra-fast | Low-latency lookups, simple factual questions, drafts | ❌ |
| `qwen/qwen3-32b` | Qwen3 32B — Strong reasoning (multilingual) | Technical reasoning, math-heavy papers, non-English content | ✅ |
| `groq/compound` | Groq Compound — Agentic / tool-use | Agent Mode multi-hop workflows and tool calling | ✅ |
| `groq/compound-mini` | Groq Compound Mini — Fast agent | Faster agent runs when quality tradeoff is acceptable | ✅ |

---

### 2.7 `src/ui/app.py`

#### Model catalogue fetching

On startup, the UI calls `GET /api/models` (cached for 5 minutes). If the
backend is unreachable, it falls back to a minimal catalogue containing just
`llama-3.3-70b-versatile`.

#### New session state

```python
st.session_state.llm_settings = _default_settings()
```

Holds the current model and all generation/retrieval parameters.

#### Automatic injection into every request

`api_post()` now automatically attaches `llm_config` and `similarity_threshold`
to every POST body, so **all tabs** (Chat, Compare, Survey, Gaps, Search,
Explain, Trends, Recommend, Summarize, Multi-doc) honour the settings panel
with zero per-call wiring.

```python
def api_post(endpoint: str, payload: dict, timeout: int = 300):
    payload = {
        **payload,
        "llm_config": _build_llm_config(),
        "similarity_threshold": st.session_state.llm_settings["similarity_threshold"],
    }
    ...
```

The Chat tab's previously-hardcoded `top_k=10` was replaced with
`st.session_state.llm_settings["top_k"]`.

#### ⚙️ Model Settings panel (sidebar expander)

Added a collapsible **⚙️ Model Settings** expander at the top of the sidebar.

**Layout:**

1. **Quick presets** (3 buttons, one-click):
   - 🎯 **Precise** — temp 0.1, top_p 1.0 — for RAG, extraction, citations
   - ⚖️ **Balanced** — temp 0.5, top_p 1.0 — default Q&A
   - 🎨 **Creative** — temp 0.9, top_p 0.95 — brainstorming, summaries

2. **Model dropdown** — shows each model's label (e.g. *"GPT-OSS 120B — Highest
   quality"*), and under the dropdown a dynamically-updated
   **💡 Best for: …** caption from the catalogue.

3. **Core sliders** (always visible):
   | Parameter | Range | Tooltip |
   |---|---|---|
   | Temperature | 0.0 – 1.5 | *Higher = more creative and varied; lower = more deterministic and factual.* |
   | Max tokens | 256 – 8192 | *Hard cap on the length of the model's response in tokens.* |
   | Retrieval top-k | 1 – 30 | *How many document chunks to retrieve and feed to the model as context.* |

4. **🔧 Advanced** (nested expander):
   | Parameter | Range | Tooltip |
   |---|---|---|
   | Top-p (nucleus) | 0.0 – 1.0 | *Keeps the smallest set of tokens whose probabilities sum to p; 1.0 disables it.* |
   | Frequency penalty | -2.0 – 2.0 | *Positive values reduce verbatim repetition of tokens already used.* |
   | Presence penalty | -2.0 – 2.0 | *Positive values push the model toward introducing new topics.* |
   | Similarity threshold | 0.0 – 1.0 | *Minimum relevance score a retrieved chunk must have to be used.* |
   | Seed | int (0 = random) | *Fixed seed makes outputs reproducible for the same prompt.* |
   | Reasoning effort | low / medium / high | *Only shown when the selected model supports it. Controls how much internal reasoning the model does — higher is slower but more thorough.* |

5. **↩️ Reset to defaults** button — restores the server-side defaults fetched
   from `/api/models`.

---

## 3. Data flow

```
Streamlit sidebar (⚙️ Model Settings)
        │
        ▼
st.session_state.llm_settings  ──►  api_post() auto-injection
        │
        ▼
POST /api/<endpoint>  { ...payload, llm_config, similarity_threshold }
        │
        ▼
FastAPI route (TunableRequest)
        │
        ▼
_llm_kwargs(request)  ──►  RAGPipeline / ResearchAgent method
                                    │
                                    ├──►  Retriever.retrieve(similarity_threshold=…)
                                    └──►  LLMClient.generate(llm_config=…)
                                                    │
                                                    ▼
                                    Groq API call with merged params
```

---

## 4. How to try it

1. Restart the FastAPI backend: `python -m src.main`
2. Restart the Streamlit UI: `streamlit run src/ui/app.py`
3. In the sidebar, open **⚙️ Model Settings**.
4. Try switching the model to **GPT-OSS 120B — Highest quality** and running a
   complex question in the Chat tab.
5. Click the **🎯 Precise** preset and run a citation-heavy RAG query.
6. Toggle **Reasoning effort** to *high* (only visible with reasoning-capable
   models) for tougher questions.

---

## 5. Files touched

- `src/config.py`
- `src/generation/llm_client.py`
- `src/retrieval/retriever.py`
- `src/retrieval/rag_pipeline.py`
- `src/agents/research_agent.py`
- `src/api/routes.py`
- `src/ui/app.py`

No schema/database changes. Fully backwards-compatible — requests without
`llm_config` fall back to the defaults in `src/config.py`.
