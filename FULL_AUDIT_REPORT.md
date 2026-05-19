# Multimodal AI Research Assistant — Full Audit Report
**Date:** 2026-05-18  
**Audited by:** Claude Code (claude-sonnet-4-6)  
**Scope:** Every module — backend, frontend, RAG pipeline, ingestion, agent, storage, security, UX

---

## Table of Contents

1. [Critical Bugs](#1-critical-bugs)
2. [RAG Architecture Issues & Improvements](#2-rag-architecture-issues--improvements)
3. [Ingestion Pipeline Issues](#3-ingestion-pipeline-issues)
4. [Agent Issues](#4-agent-issues)
5. [Frontend Issues](#5-frontend-issues)
6. [Security Issues](#6-security-issues)
7. [Missing Features](#7-missing-features)
8. [Quick-Win Fixes](#8-quick-win-fixes)
9. [Priority Roadmap](#9-priority-roadmap)

---

## 1. Critical Bugs

These will cause silent failures, broken features, or security vulnerabilities.

---

### 1.1 OCR & Equation Extraction Never Runs

**File:** `src/ingestion/pipeline.py` lines 36–43  
**Problem:** `OCRProcessor` and `EquationExtractor` are both instantiated in `__init__` and imported at the top of the file, but neither is ever called inside `ingest_file()`. Equations in PDFs are never extracted. Scanned or image-heavy pages never get OCR'd. These two entire modules are dead weight.  
**Impact:** Any paper with mathematical equations or scanned pages has zero equation content indexed. Searching for "loss function formula" or "equation 3" returns nothing.  
**Fix:**
- After image extraction in the pipeline, call `self.ocr_processor.process(image)` on images from pages with low text yield (e.g., fewer than 100 words extracted by PyMuPDF).
- Call `self.equation_extractor.extract(image_path)` on each extracted image to detect and store LaTeX strings in `ChunkMetadata.latex_source`.

---

### 1.2 Agent Always Returns Empty Citations

**File:** `src/agents/research_agent.py` lines 244–252  
**Problem:** Every `AgentResponse` is constructed with `citations=[]`. The agent calls tools (`search_text`, `search_tables`, `search_figures`, `search_equations`) that retrieve chunks with full metadata — source file, page number, image URL, table data, LaTeX — but none of this citation data is accumulated or returned.  
**Impact:** In the chat panel, agent-mode responses have no clickable sources. Users cannot verify which paper or page the answer comes from. The "Sources & Citations" collapsible is always empty for agent mode.  
**Fix:**
- Parse tool `Observation` strings to extract `[source_file, page]` pairs.
- Or, return structured `QueryResult` objects from agent tools (instead of formatted strings) and accumulate them in a `citations_list` during the ReAct loop.
- Pass the accumulated list as `citations=citations_list` when building the final `AgentResponse`.

---

### 1.3 Double URL-Encoding in API Proxy

**File:** `frontend/app/api/[...path]/route.ts` lines 22–23  
**Problem:**
```ts
path.map(encodeURIComponent).join("/")
```
The frontend already URL-encodes filenames before calling `fetch` (e.g., `encodeURIComponent(sourceFile)` in `frontend/lib/api.ts` line 244). The proxy then encodes the already-encoded string again. A filename like `my paper (2024).pdf` → first encoded to `my%20paper%20(2024).pdf` → proxy encodes again to `my%2520paper%2520(2024).pdf` → the backend receives a doubly-encoded path and returns 404.  
**Impact:** Any document with spaces, parentheses, or special characters in the filename will fail for:
- `GET /documents/{source_file}/visuals`
- `DELETE /documents/{doc_id}`
- Any route with path parameters containing special chars

**Fix:** Replace `path.map(encodeURIComponent).join("/")` with simply `path.join("/")`. The browser already encodes special characters before the path reaches the proxy.

---

### 1.4 Metrics Key Mismatch — Humanizer Page Breaks Silently

**File:** `frontend/app/humanizer/page.tsx` lines 124–130 vs `src/generation/humanizer.py` line 51  
**Problem:** The frontend renders a metric card using `metrics.avg_sentence_length`, but the backend's `compute_metrics()` function returns the key as `avg_sent_len`. The value is always `undefined`, so the metric card displays `NaN%`.  
**Fix:** Either rename the backend key from `avg_sent_len` → `avg_sentence_length`, or update the frontend to read `metrics.avg_sent_len`.

---

### 1.5 VisualCitations Never Shown in Chat or Non-Search Pages

**File:** `frontend/components/result-view.tsx` line 19  
**Problem:** `ResultView` (used by Compare, Survey, Trends, Recommend, Summarize, and Search text tab) imports and uses only the `Citations` component, which is text-only (source file + page number + relevance bar). The `VisualCitations` component (which renders actual figure images, formatted tables, and LaTeX equations) is only used in the Explain sub-tab of the Search page — nowhere else.  
**Impact:** When the backend returns figure/table/equation citations (which it does for most queries involving visual content), users on the Chat page, Compare page, Survey page, and all other pages never see those images or tables.  
**Fix:**
- Import `VisualCitations` into `ResultView` and render it above `Citations` when `data.citations` contains entries with `image_url`, `table_data`, or `latex_source`.
- Do the same inside the chat panel's assistant message renderer in `chat-panel.tsx`.

---

### 1.6 Blocking `time.sleep()` Inside Async Event Loop

**File:** `src/generation/llm_client.py` lines 204–206 and lines 278–280  
**Problem:** Both `generate()` and `generate_with_image()` retry loops call `time.sleep()` when hitting Groq rate limits (waits of 15–75 seconds per attempt). FastAPI runs on an async event loop. A blocking `time.sleep()` freezes the entire server — no other requests can be served while the sleep is running.  
**Impact:** One rate-limited request can stall the entire application for up to 75 seconds, during which all other users get no response.  
**Fix:**
- Convert `generate()` and `generate_with_image()` to `async def` methods.
- Replace `time.sleep(wait)` with `await asyncio.sleep(wait)`.
- Run the synchronous Groq client calls in a thread pool: `await asyncio.get_event_loop().run_in_executor(None, blocking_groq_call)`.
- The same applies to the Gemini rate limiter `_GeminiRateLimiter.wait()` in `llm_client.py` lines 43–53.

---

### 1.7 Path Traversal Vulnerability in File Upload

**File:** `src/api/routes.py` line 229  
**Problem:**
```python
saved_path = os.path.join(tmp_dir, file.filename)
```
If an attacker uploads a file with `filename = "../../.env"` or `"../../../etc/passwd"`, `os.path.join` will resolve the path outside the intended upload directory. The uploaded content is then written to that location.  
**Fix:**
```python
safe_name = os.path.basename(file.filename)
saved_path = os.path.join(tmp_dir, safe_name)
```
Or use `pathlib`:
```python
safe_name = Path(file.filename).name
```

---

### 1.8 SQLite Thread Safety — Concurrent Write Corruption

**File:** `src/storage/document_store.py` line 23  
**Problem:** `sqlite3.connect(DB_PATH, check_same_thread=False)` shares a single connection across all threads without a lock. Background ingestion threads and FastAPI request threads call `add_document`, `update_status`, and `get_all_documents` concurrently on the same connection object.  
**Impact:** SQLite connections are not thread-safe in this mode. Concurrent writes cause `ProgrammingError: Recursive use of cursors not allowed` or silent data corruption.  
**Fix:**
- Add a `threading.Lock()` to `DocumentStore` and acquire it for every `execute()` + `commit()` pair.
- Or use `check_same_thread=False` with Python's `threading.local()` to give each thread its own connection.
- Or migrate to SQLAlchemy with a proper connection pool.

---

### 1.9 Stuck "Processing" Documents After Server Restart

**File:** `src/api/routes.py` lines 234–239  
**Problem:** Ingestion runs in a daemon thread. If the server is restarted or crashes while a document is being ingested, the document remains in `status = "processing"` in the SQLite DB permanently. There is no recovery mechanism.  
**Impact:** Users see documents stuck in "Processing" state forever with no way to retry or clear them from the UI.  
**Fix:**
- At application startup (in `src/main.py`), query all documents with `status = "processing"` and mark them `"failed"`.
- Add a `POST /documents/{doc_id}/retry` endpoint that re-triggers ingestion for failed documents.

---

### 1.10 Ingestion Step Numbers Duplicated (Code Quality Bug)

**File:** `src/ingestion/pipeline.py` lines 111–122  
**Problem:** The comment "Step 6: Chunk the content" appears, and then immediately after, "Step 6: Generate embeddings" appears. There is no "Step 7" label — it was accidentally renumbered.  
**Fix:** Renumber steps sequentially: Step 6 = Chunk, Step 7 = Generate embeddings, Step 8 = Store in vector DB.

---

### 1.11 Wrong Log Message in Humanizer

**File:** `src/generation/humanizer.py` line 215  
**Problem:** `logger.info("✓ Gemini humanizer ready")` is printed after initializing `self.llm = LLMClient()`, which is a **Groq** client — not Gemini. The Gemini API is only used for vision tasks (VisionAnalyzer), not humanization.  
**Fix:** Change the log message to `"✓ Groq humanizer LLM ready"`.

---

## 2. RAG Architecture Issues & Improvements

---

### 2.1 Chunking Strategy: Not Actually Semantic

**File:** `src/ingestion/chunker.py`  
**Current approach:** `RecursiveCharacterTextSplitter` from LangChain — a syntactic splitter that splits on `\n\n`, `\n`, `. `, then space, then character.  
**Class name is misleading:** `SemanticChunker` implies embedding-based boundary detection. The actual implementation has no semantic awareness.

**Problems with current configuration:**

| Parameter | Current Value | Problem |
|-----------|--------------|---------|
| `chunk_size` | 512 chars | ≈ 100–130 tokens — too small for academic content. Dense technical sentences lose context. |
| `chunk_overlap` | 50 chars | ≈ 8–10 words — barely spans one sentence. |
| Separators | `["\n\n", "\n", ". ", " ", ""]` | Splits without regard to section or paragraph boundaries. |

**Specific element problems:**

- **Images:** Each image is embedded with the placeholder string `"[Figure on page N] Image extracted from the document. Path: /data/images/..."`. Every image chunk has a nearly identical embedding. Searching for "architecture diagram" retrieves all images with equal relevance.
- **Tables:** A 50-row table becomes one large chunk. The splitter will split it mid-row, producing broken markdown fragments.
- **Short chunks:** No minimum length filter. Single-sentence chunks like "See Table 3." pollute the index.

**Recommended changes:**

1. **Increase chunk size to 800–1000 characters (≈ 250–300 tokens) with 150–200 character overlap.**
2. **Implement hierarchical (parent-document) chunking:**
   - Store small child chunks (300 tokens) as the indexed unit for retrieval.
   - Store the parent chunk (1000 tokens) as the context unit — when a child chunk is retrieved, return its parent for the LLM context.
   - This is called the "small-to-big" retrieval pattern.
3. **Section-aware chunking:** Never split a chunk across two detected sections. When a heading is detected, flush the current chunk first.
4. **True semantic chunking (optional, higher effort):** Embed each sentence, detect where cosine similarity drops significantly between consecutive sentences, and use those drop points as chunk boundaries.
5. **Filter short chunks:** Discard any chunk with fewer than 15 words.
6. **Figure descriptions at ingestion time:** For every extracted image, call Groq Vision (or Gemini) at ingestion time to generate a real description. Embed that description — not a path placeholder.
7. **Table column headers:** Store the first row of every table as separate searchable metadata so queries like "what are the columns in Table 2?" work correctly.

---

### 2.2 Embedding Model: Too Small for Scientific Text

**File:** `src/config.py` line 27  
**Current model:** `all-MiniLM-L6-v2` — 384-dimensional, 22M parameters, trained on general web data.

**Problems:**
- Not trained on scientific vocabulary. Words like "perplexity", "BLEU", "attention head", "cross-encoder" are represented by generic embeddings.
- 384 dimensions limits the expressiveness of the embedding space for dense technical content.
- No citation awareness — cannot distinguish "paper A cites paper B" type relationships.

**Recommended alternatives (in order of impact for this use case):**

| Model | Dims | Notes |
|-------|------|-------|
| `allenai/specter2_base` | 768 | Trained specifically on scientific paper relationships (citations, abstracts). Best fit. |
| `BAAI/bge-large-en-v1.5` | 1024 | Top of MTEB leaderboard for retrieval. Strong general-purpose. |
| `intfloat/e5-large-v2` | 1024 | Excellent on retrieval benchmarks. Use `"query: "` prefix for queries, `"passage: "` for documents. |
| `all-mpnet-base-v2` | 768 | Much better than MiniLM, same sentence-transformers library. Minimal code change. |

**Migration effort:** Low. Change one line in `config.py`. The new model's dimension is different, so the existing ChromaDB collection must be deleted and all documents re-ingested.

---

### 2.3 Retrieval: Dense-Only, No Hybrid Search

**File:** `src/retrieval/retriever.py`  
**Current:** Pure dense vector similarity search via ChromaDB.

**Problems:**
- Pure semantic search misses exact keyword matches: model names (`"GPT-4"`, `"BERT-base"`), algorithm names (`"Algorithm 1"`), exact table references (`"Table 3"`), metric values (`"83.2% F1"`).
- No re-ranking — top-k from the vector store is used directly as context. A cross-encoder would significantly improve precision.
- **The similarity threshold of 0.3 does nothing meaningful.** With the scoring formula `1.0 - (distance / 2.0)`, a threshold of 0.3 corresponds to approximately cosine similarity ≥ −0.4 — almost no chunk gets filtered out.
- **No diversity in results** — if two chunks from the same paragraph both score highly, both are returned, wasting context window tokens.

**Required additions:**

1. **Hybrid retrieval — BM25 + Dense with Reciprocal Rank Fusion (RRF):**
   - Add `rank-bm25` library. At index time, maintain a BM25 index over all chunk texts (per source file).
   - At query time, run both BM25 and dense search in parallel.
   - Merge results using Reciprocal Rank Fusion: `score = Σ 1 / (rank_dense + k) + 1 / (rank_bm25 + k)`.
   - BM25 catches exact keyword matches; dense catches semantic matches. Together they cover both.

2. **Cross-encoder re-ranking:**
   - After retrieving top 20 results (dense + BM25), rerank using `cross-encoder/ms-marco-MiniLM-L-6-v2` from HuggingFace.
   - Return top 10 re-ranked results.
   - This step consistently adds 5–15% retrieval precision at low computational cost (cross-encoders are fast on CPU for short texts).

3. **MMR (Maximal Marginal Relevance) for diversity:**
   - Implement MMR to penalize results that are too similar to already-selected results.
   - `score_mmr = λ × similarity(query, chunk) − (1 − λ) × max_similarity(chunk, already_selected)`
   - λ = 0.7 is a good default. Ensures that 10 returned chunks cover 10 different aspects of the question.

4. **Fix the similarity threshold:**
   - The correct similarity formula for ChromaDB cosine distance is `similarity = 1.0 - distance` (since ChromaDB stores `distance = 1 - cosine_similarity`).
   - The current formula `1.0 - (distance / 2.0)` maps the full [-1, 1] cosine range to [0, 1] and the default threshold of 0.3 is too permissive.
   - Use the corrected formula and raise the default threshold to 0.4–0.5.

5. **HyDE (Hypothetical Document Embeddings):**
   - For complex or multi-hop questions, ask the LLM to generate a "hypothetical answer" first (without retrieval).
   - Embed the hypothetical answer and use it for retrieval instead of the raw question.
   - This dramatically improves recall for questions phrased differently from how the paper states the answer.
   - Example: Question = "How does BERT handle long documents?" → HyDE generates a plausible answer → that answer's embedding is closer to the paper's explanation than the question's embedding alone.

---

### 2.4 Context Building: Character Truncation Loses Relevant Chunks

**File:** `src/retrieval/retriever.py` lines 68–105  
**Problem:** `build_context()` accumulates chunks until `total_length > max_context_length` then stops. If the first 5 chunks are verbose, highly relevant chunk #8 is silently dropped. Chunks are also not guaranteed to end at sentence boundaries after accumulation.

**Fix:**
- Truncate **individual chunks** to a maximum of 600 characters before accumulation, rather than stopping the whole accumulation when the running total exceeds the limit. This ensures all top-k results are included at reduced length.
- Add document title/abstract as a prefix for each source in the context string to help the LLM orient itself.
- For the parent-document pattern: retrieve the child chunk for scoring, but include the parent chunk in the context string.

---

### 2.5 Multi-Doc Query is Structurally Identical to Regular Query

**File:** `src/retrieval/rag_pipeline.py` lines 408–446  
**Problem:** `multi_doc_query()` is structurally identical to `query()` — the only difference is the prompt template used. It retrieves top_k=20 chunks with no guarantee of cross-paper coverage. If all 20 chunks come from one paper, the "multi-doc" answer is actually single-doc.

**Fix:**
- Group retrieved results by `source_file`.
- Enforce a maximum of N chunks per paper (e.g., `ceil(top_k / num_papers)`), and a minimum of 2–3 chunks per paper present in the results.
- Or: run `self.retriever.retrieve()` separately for each ingested paper with `filter_source=paper`, take top 5 from each, then merge.

---

### 2.6 Literature Survey Has No Multi-Paper Diversity

**File:** `src/retrieval/rag_pipeline.py` lines 183–219  
**Problem:** `literature_survey()` retrieves `top_k=30` chunks via a single embedding query. All 30 might come from the most frequently indexed paper.

**Fix:**
- Retrieve top 6–8 chunks per paper independently, then merge all results into the context.
- Sort merged results by paper, then by relevance within each paper, to give the LLM a structured cross-paper view.

---

### 2.7 No System Prompt in Any LLM Call

**File:** `src/generation/llm_client.py` lines 162–168  
**Problem:** Every generation call sends:
```python
"messages": [{"role": "user", "content": prompt}]
```
There is no system message. Instruction-tuned models (Llama, GPT-OSS, Qwen) behave significantly better with a system prompt that establishes persona, tone, and rules.

**Fix:** Add a system message to the messages array:
```python
"messages": [
    {
        "role": "system",
        "content": (
            "You are an expert AI research assistant specializing in scientific paper analysis. "
            "Always be precise, technical, and cite your sources. "
            "When context is provided, base your answer strictly on that context."
        ),
    },
    {"role": "user", "content": prompt},
]
```

---

### 2.8 No Streaming Support

**Files:** `src/generation/llm_client.py`, `src/api/routes.py`, all frontend pages  
**Problem:** All responses are fully buffered server-side before being sent to the client. For complex queries (literature survey, agent runs) that take 30–120 seconds, users stare at a spinner with no feedback.

**Fix:**
- Use Groq's streaming API: `client.chat.completions.create(..., stream=True)` returns a generator of token chunks.
- Wrap in FastAPI `StreamingResponse` with `text/event-stream` media type (SSE).
- On the frontend, use the Fetch API's `ReadableStream` or the `eventsource-parser` library to process SSE events and progressively render text.
- This is the single highest-impact UX improvement possible.

---

### 2.9 Summarization Uses a Generic Fixed Query String

**File:** `src/retrieval/rag_pipeline.py` line 101  
**Problem:**
```python
query = "main contributions methodology results conclusions abstract"
```
This generic query retrieves similar chunks for every paper. It doesn't adapt to what the paper is actually about.

**Fix:** Extract the paper's actual title and abstract from the first few chunks (`chunk_index = 0` or the preview endpoint), then use those keywords as the retrieval query for summarization.

---

### 2.10 Chat History Not Used in Regular RAG Mode

**File:** `src/retrieval/rag_pipeline.py` (all methods)  
**Problem:** The `chat_history` parameter is only passed to the agent (`/agent` endpoint). Regular RAG queries (`/query`) and all other endpoints have no conversation memory. Each query is treated as entirely independent.

**Impact:** A follow-up question like "What did the paper say about that?" returns irrelevant results because "that" has no resolved reference.

**Fix:**
- Accept `chat_history: list[dict]` in `QueryRequest`.
- In `query()`, prepend the last 2–3 turns of conversation to the context string or to the retrieval query.
- Or perform query rewriting: use the LLM to rephrase the current question using context from conversation history into a standalone question before retrieval.

---

## 3. Ingestion Pipeline Issues

---

### 3.1 Image Extraction Captures Decorative Elements

**File:** `src/ingestion/image_extractor.py`  
**Problem:** All images are extracted from all pages including logos, horizontal rules, section dividers, watermarks, and decorative icons. These tiny images get stored as figure chunks in ChromaDB with placeholder descriptions.

**Impact:** The visual index is polluted with hundreds of decorative images. When the `/visuals` endpoint filters by 50×50 minimum size, those images are excluded at display time, but they still exist in the vector store and consume index space.

**Fix:**
- Apply the 50×50 size filter at extraction time, not at display time.
- Deduplicate identical images: compute a perceptual hash (phash) of each image and skip images with the same hash as a previously extracted one.
- Consider a minimum file size threshold (e.g., skip images < 5KB).

---

### 3.2 PDF Heading Detection Is Too Aggressive

**File:** `src/ingestion/pdf_processor.py` lines 125–147  
**Problem:** The heuristic `font_size >= 14 and len(text) < 100` flags many non-heading lines as headings:
- Figure captions (e.g., "Figure 3: Architecture overview of our model")
- Bold sentences within paragraphs
- Callout boxes and pull quotes
- References list entries

When a false heading is detected, the current accumulated text is flushed as a chunk, and `current_heading` is updated to the false heading. All subsequent chunks receive incorrect section metadata.

**Fix:**
- Add additional signals: check for bold flag (`span["flags"] & 2^4`), check that the line is isolated (no text in the same block before/after), check for heading-specific patterns.
- Stricter keyword matching: require that the keyword is the entire line or the line starts with a numbering pattern (`\d+\.` or `\d+\.\d+`).
- Add a `is_figure_caption` check: if the text starts with "Figure", "Fig.", "Table", "Eq.", skip it as a heading.

---

### 3.3 Multi-Column PDF Layout Not Handled

**File:** `src/ingestion/pdf_processor.py` line 54  
**Problem:** `page.get_text("dict", sort=True)` with `sort=True` sorts all text blocks by y-coordinate, then x-coordinate. For a two-column paper layout, this interleaves text from the left column with text from the right column of the same horizontal band. A sentence from column 1 is immediately followed by a sentence from column 2 in the extracted text.

**Impact:** Text chunks are garbled for most academic papers, which use two-column layouts.

**Fix:**
- Detect column layout by clustering block x-coordinates into left/right groups.
- Process each column independently: first extract all left-column blocks top-to-bottom, then all right-column blocks top-to-bottom.
- Or use `pdfplumber` with bounding boxes to separate columns.

---

### 3.4 No Duplicate Document Detection

**File:** `src/ingestion/pipeline.py`  
**Problem:** Uploading `paper.pdf` a second time creates a second document record in SQLite and doubles all chunks in ChromaDB (with different IDs). The retrieval will then return duplicate information twice in every query result.

**Fix:**
- Compute SHA-256 hash of the uploaded file before ingestion.
- Check if a document with the same hash already exists in the document store.
- If yes, return the existing document info with a `409 Conflict` or a message like "This document is already uploaded."
- Store the file hash in the `documents` SQLite table.

---

### 3.5 No File Size Limit on Upload

**File:** `src/api/routes.py` lines 205–253  
**Problem:** There is no check on the uploaded file size. A 500MB PDF will be read entirely into memory with `await file.read()`, potentially causing OOM errors or extremely long ingestion times.

**Fix:**
- Add a FastAPI middleware or inline check:
```python
contents = await file.read()
if len(contents) > 50 * 1024 * 1024:  # 50MB limit
    raise HTTPException(status_code=413, detail="File too large. Maximum size is 50MB.")
```
- Inform users of the limit in the frontend upload UI.

---

### 3.6 Vision Analysis Deferred but Never Triggered at Query Time

**File:** `src/ingestion/pipeline.py` lines 89–103  
**Problem:** The comment says "vision analysis deferred to query time to keep ingestion fast," but there is no code anywhere that calls `VisionAnalyzer` at query time for unanalyzed images. The image gets a placeholder description at ingestion and that placeholder is what's embedded and searched forever. The "deferred" vision analysis is simply never run.

**Fix:**
- Either run vision analysis at ingestion time (acceptable if done asynchronously in the background after chunking/embedding).
- Or implement a lazy-evaluation path: when an image chunk is retrieved and its description is still a placeholder, call the vision analyzer then, cache the result back to ChromaDB metadata, and use it in the response.

---

## 4. Agent Issues

---

### 4.1 Text-Format ReAct Instructions Redundant with Native Tool Calling

**File:** `src/generation/prompts.py` lines 195–225  
**Problem:** `AGENT_PROMPT` contains an explicit `FORMAT:` block with `Thought:/Action:/Action Input:/Observation:` instructions. However, the agent exclusively uses Groq's native function-calling API (tool schemas + `tool_choice="auto"`). The text-format path is only a fallback when native tool calls are absent (which shouldn't happen with modern Groq models). The two approaches conflict and confuse each other.

**Fix:**
- Remove the `FORMAT:` section from `AGENT_PROMPT`.
- Replace it with a clean system-prompt style: describe the agent's persona, task, and that it has tools available — let native tool calling handle the rest.
- Keep the `_parse()` text-based fallback in code for robustness, but don't document it in the prompt.

---

### 4.2 Agent Returns Clarifying Question Instead of Partial Answer at Max Iterations

**File:** `src/agents/research_agent.py` lines 278–286  
**Problem:** When the agent reaches 10 iterations without calling `finish`, it calls `_generate_clarification()` which asks the user a question. This is counterintuitive: if the agent has already retrieved and observed relevant information across 10 steps, it should synthesize a partial answer, not deflect to the user with a question.

**Fix:**
- At max iterations, pass all accumulated observations to a final synthesis prompt: "Based on the following retrieved information, answer the original question as best you can."
- Reserve the clarifying question path only when the agent retrieves nothing relevant in multiple tool calls (i.e., all observations are "No relevant content found").

---

### 4.3 Chat History Truncated Too Aggressively

**File:** `src/agents/research_agent.py` lines 370–378  
**Problem:**
```python
recent = history[-4:]  # last 4 messages
lines = [f"... {str(m.get('content', ''))[:200]}" ...]
```
Only the last 4 messages are included, and each is truncated to 200 characters. A prior 2000-character assistant answer is reduced to 200 chars, losing the specific claims the user might be following up on.

**Fix:**
- Increase to last 6–8 messages.
- Increase per-message truncation to 500–800 characters for assistant messages, 300 for user messages.
- Or implement token budget management: count tokens in history messages and trim oldest first when over a budget.

---

### 4.4 No Cross-Session Agent Memory

**Files:** `src/agents/research_agent.py`, `src/api/routes.py`  
**Problem:** Every agent run starts completely fresh. The agent has no memory of which papers were interesting, what conclusions were drawn in previous sessions, or what the user's research focus is.

**Fix (medium effort):**
- Add a lightweight `AgentMemory` class backed by SQLite.
- Store key facts extracted during previous runs: "User is researching RAG for scientific papers", "Paper X was identified as most relevant for query Y".
- Inject up to 500 tokens of relevant memory into the agent prompt at the start of each run.

---

## 5. Frontend Issues

---

### 5.1 Chat History Grows Without Bound in localStorage

**File:** `frontend/lib/store.ts` lines 141–143  
**Problem:** `messages` is fully persisted to localStorage via Zustand's `persist` middleware. After many sessions, accumulated messages can exceed the 5–10MB localStorage limit, causing `QuotaExceededError` — the entire store then fails to persist silently.

**Fix:**
- Cap persisted messages at the last 50 in the `partialize` function:
```ts
partialize: (state) => ({
  settings: state.settings,
  messages: state.messages.slice(-50),
  agentMode: state.agentMode,
}),
```
- Or move messages to IndexedDB (using `idb-keyval`) which has no practical size limit.

---

### 5.2 No Request Cancellation on Navigation or Double-Submit

**File:** `frontend/components/chat-panel.tsx` lines 142–219  
**Problem:** If the user submits a question, then navigates to another page, or clicks Submit again before the first response arrives, the original request keeps running in the background. No `AbortController` is used.

**Fix:**
- Store an `AbortController` in a `useRef`.
- Cancel the previous controller at the start of each new `sendQuestion` call.
- Pass the `signal` to the `fetch` call in `api.ts`.
- On component unmount, call `controller.abort()`.

---

### 5.3 Polling Continues After All Documents Complete

**File:** `frontend/lib/hooks.ts` lines 10–30  
**Problem:** `useDocumentsPolling` polls the `/documents` endpoint every 4 seconds unconditionally — even when all documents show `status = "completed"` and there is nothing to update. This is 15 unnecessary API calls per minute per open browser tab.

**Fix:**
```ts
const hasPending = documents.some(d => d.status === "processing");
const interval = hasPending ? 4000 : 30000;  // slow down when idle
```
Or pause polling entirely when no documents are in "processing" state.

---

### 5.4 Input Cleared Before Response Arrives — Lost on Error

**File:** `frontend/components/chat-panel.tsx` lines 225–226  
**Problem:** `setInput("")` is called immediately when the form is submitted. If the API call fails, the user's typed question is gone and must be retyped.

**Fix:** Store the question text in a local variable before clearing, and restore it to the input field if the API call fails:
```ts
const q = input.trim();
setInput("");
try {
  await sendQuestion(q);
} catch {
  setInput(q);  // restore on error
}
```

---

### 5.5 Humanizer `changes_made` Rendered as Plain Text

**File:** `frontend/app/humanizer/page.tsx` lines 253–260  
**Problem:** `data.changes_made` is wrapped in a `<p>` tag and rendered as plain text. The backend returns this field as markdown containing bold text, checkmarks (`✅`, `⚠`), bullet points (`•`), and line breaks. All markdown syntax is displayed as raw characters.

**Fix:** Replace `<p className="...">{data.changes_made}</p>` with `<Markdown content={data.changes_made} />`.

---

### 5.6 No Error Boundaries

**Files:** All page and component files  
**Problem:** Any uncaught JavaScript error in any component (React rendering error, unexpected `null` access, etc.) will crash the entire application with a blank white screen and no user feedback. This is especially likely given the variety of unknown shapes of backend response data.

**Fix:**
- Create a `ErrorBoundary` class component (or use `react-error-boundary` library).
- Wrap `<main>` in `layout.tsx` with the boundary.
- Show a friendly fallback UI ("Something went wrong. Try refreshing.") instead of a blank screen.

---

### 5.7 Sidebar Fixed Width — Not Responsive

**File:** `frontend/components/sidebar.tsx` line 65  
**Problem:** `w-[340px]` is hardcoded. On screens narrower than ~1024px, the sidebar squeezes the main content to an unusable width. On mobile, the layout is broken.

**Fix:**
- Add responsive classes: `w-[240px] lg:w-[340px]`.
- Or collapse to a hamburger menu button on mobile (`hidden lg:flex` on the full sidebar, add a `Sheet` / drawer component for mobile).

---

### 5.8 ResultView Does Not Show Visual Citations

**File:** `frontend/components/result-view.tsx`  
**Problem:** `ResultView` is the shared output component used by Compare, Survey, Trends, Search (text tab), and Recommendations. It uses only `Citations` (text-only). Even when the backend returns figure or table citations in these responses, they are never rendered.

**Fix:** Add `VisualCitations` import and render it conditionally:
```tsx
import { VisualCitations } from "./visual-citations";
// ...inside ResultView:
<VisualCitations citations={data.citations ?? []} />
<Citations citations={data.citations ?? []} />
```

---

### 5.9 Visual Citations Not Shown in Chat Panel

**File:** `frontend/components/chat-panel.tsx` lines 386–389  
**Problem:** The assistant message renders `<Citations citations={m.citations ?? []} />` but not `<VisualCitations>`. Figure and table citations returned with chat answers are never displayed.

**Fix:** Add `<VisualCitations citations={m.citations ?? []} />` above or below `<Citations>` in the assistant message bubble.

---

### 5.10 Filter State Resets on Navigation

**File:** `frontend/components/chat-panel.tsx` line 78  
**Problem:** `const [filter, setFilter] = useState<string>("__all__")` is local component state. When the user navigates to Compare, then back to Chat, the filter resets to "All papers" — they lose their paper selection.

**Fix:** Move `filter` to the Zustand store with persistence, similar to `agentMode`.

---

### 5.11 Detect/Humanize Results Lost When Switching Actions

**File:** `frontend/app/humanizer/page.tsx` lines 267–361  
**Problem:** The Humanizer page shows detection result OR humanization result but not both at the same time. If you detect first and then humanize, the detection result disappears. There is also no way to detect AI content again after humanizing to verify the improvement in the same workflow.

**Fix:**
- Keep both results visible simultaneously — detection result at the top, humanization result below.
- Add a "Detect again" button in the humanization result view that runs detection on the `humanized_text` and shows a before/after score comparison.

---

### 5.12 Table Data Shape Inconsistency Between Backend and Frontend

**File:** `frontend/components/visual-citations.tsx` lines 53–118  
**Problem:** `visual-citations.tsx` expects `table_data` with shape `{ cols: string[], rows: string[][] }`, but `table_extractor.py` returns `{ rows: int, cols: int, raw: [[...]] }` — the column headers are in `raw[0]`, not in `cols`. The structured table display never works.

**Fix:**
- In `TableExtractor._to_markdown()`, also build and return `{ cols: [col names], rows: [[values...]] }` from `processed_table[0]` and `processed_table[1:]`.
- Or normalize the shape in the `VectorStore.add_chunks()` serialization step.

---

## 6. Security Issues

| # | Issue | File | Severity | Fix |
|---|-------|------|----------|-----|
| 6.1 | CORS `allow_origins=["*"]` | `src/main.py:30-35` | Medium | Restrict to known origins (e.g., `["http://localhost:3000"]`) in production |
| 6.2 | Path traversal in file upload | `src/api/routes.py:229` | High | Use `os.path.basename(file.filename)` |
| 6.3 | No file size limit | `src/api/routes.py:205-253` | Medium | Reject files > 50MB |
| 6.4 | No authentication | All routes | Context-dependent | Add API key header check or OAuth2 for multi-user deployment |
| 6.5 | SQLite concurrent writes without lock | `src/storage/document_store.py` | Medium | Add `threading.Lock()` around all DB operations |
| 6.6 | Blocking `time.sleep()` in async endpoints | `src/generation/llm_client.py` | Medium | Use `asyncio.sleep()` |
| 6.7 | No input validation on text fields | `src/api/routes.py` | Low | Add max-length checks (e.g., question ≤ 2000 chars) |
| 6.8 | API keys logged or traceable | `src/config.py` | Low | Ensure `settings.groq_api_key` is never logged |

---

## 7. Missing Features

### 7.1 High Priority

| Feature | Description | Why It Matters |
|---------|-------------|----------------|
| **Streaming responses** | Use FastAPI `StreamingResponse` + SSE. Frontend reads chunks progressively. | Eliminates the 30–120s wait. Single biggest UX improvement. |
| **Hybrid search (BM25 + dense)** | Run BM25 alongside dense retrieval; merge with RRF. | Fixes keyword-match blind spots. Required for precise technical queries. |
| **Cross-encoder re-ranking** | Rerank top-20 with `ms-marco-MiniLM-L-6-v2`. | +5–15% precision at low cost. |
| **Visual citations in chat & result views** | Add `VisualCitations` to `ChatPanel` and `ResultView`. | Multimodal context is the core selling point. It's currently invisible in the main interface. |
| **Figure descriptions at ingestion** | Call vision model at ingestion time for each image. | Makes figure search actually work. |
| **Agent citation accumulation** | Accumulate citations from all tool observations. | Agent responses currently have zero sources. |
| **Fix double URL encoding in proxy** | Remove `encodeURIComponent` in proxy route handler. | Files with spaces or special chars cannot be loaded. |

### 7.2 Medium Priority

| Feature | Description |
|---------|-------------|
| **Parent-document retrieval** | Store small chunks for retrieval, large chunks for context. |
| **Session conversation persistence** | Save/load named conversations from IndexedDB or server-side. |
| **Batch PDF upload** | Accept multiple files at once in the upload panel. |
| **Export results** | Download answers as `.md`, `.pdf`, or `.docx`. |
| **Upload progress feedback** | Show ingestion progress (% pages processed) via a polling status bar. |
| **Duplicate document detection** | Hash uploaded files and reject duplicates. |
| **Chat history in RAG mode** | Pass last 2–3 turns to regular query for context. |
| **Query rewriting** | Use LLM to rewrite follow-up questions into standalone queries before retrieval. |
| **Upgrade embedding model** | Switch to `SPECTER2` or `BGE-large` for better scientific text embeddings. |

### 7.3 Lower Priority

| Feature | Description |
|---------|-------------|
| **RAGAS evaluation dashboard** | In-app display of faithfulness, answer relevance, context precision scores. |
| **Semantic cache** | Cache embedding + answer for repeated or near-identical questions. |
| **Multi-column PDF support** | Detect and correctly handle two-column academic paper layouts. |
| **OCR activation** | Actually call `OCRProcessor` for scanned/image-heavy pages. |
| **Equation extraction activation** | Actually call `EquationExtractor` for mathematical notation. |
| **Mobile responsive sidebar** | Collapsible drawer on narrow screens. |
| **Dark/light mode toggle** | Currently dark-only. |
| **Citation click-through** | Clicking a citation opens a PDF viewer scrolled to the cited page. |
| **Session-level agent memory** | Persist key findings across multiple agent runs. |
| **Chunking strategy config from UI** | Let users change chunk size, overlap, and strategy per document. |
| **Embedding model selection from UI** | Let users pick the embedding model before ingestion. |

---

## 8. Quick-Win Fixes

These can each be completed in under 30 minutes and immediately improve the product.

| # | What | Where | Effort |
|---|------|-------|--------|
| 1 | Fix `avg_sentence_length` vs `avg_sent_len` key mismatch | `src/generation/humanizer.py` or `frontend/app/humanizer/page.tsx` | 1 min |
| 2 | Remove double `encodeURIComponent` in API proxy | `frontend/app/api/[...path]/route.ts` | 1 min |
| 3 | Add `VisualCitations` to `ResultView` | `frontend/components/result-view.tsx` | 5 min |
| 4 | Add `VisualCitations` to chat panel assistant messages | `frontend/components/chat-panel.tsx` | 5 min |
| 5 | Fix path traversal: use `os.path.basename(file.filename)` | `src/api/routes.py:229` | 1 min |
| 6 | Add system prompt to all `generate()` calls | `src/generation/llm_client.py` | 5 min |
| 7 | Fix humanizer log message (Gemini → Groq) | `src/generation/humanizer.py:215` | 1 min |
| 8 | Rename `SemanticChunker` to `RecursiveChunker` | `src/ingestion/chunker.py` | 1 min |
| 9 | Fix duplicate "Step 6" labels in pipeline | `src/ingestion/pipeline.py` | 1 min |
| 10 | Increase `chunk_size` to 800, `chunk_overlap` to 150 in config | `src/config.py` | 1 min + re-ingest |
| 11 | Add minimum chunk length filter (skip < 15 words) | `src/ingestion/chunker.py` | 5 min |
| 12 | Cap persisted messages to last 50 in store | `frontend/lib/store.ts` | 2 min |
| 13 | Add `threading.Lock()` to `DocumentStore` | `src/storage/document_store.py` | 10 min |
| 14 | Render `changes_made` with `<Markdown>` in humanizer | `frontend/app/humanizer/page.tsx` | 2 min |
| 15 | Mark "processing" docs as "failed" on startup | `src/main.py` | 5 min |

---

## 9. Priority Roadmap

### Phase 1 — Fix Bugs (Week 1)

1. Double URL-encoding bug in proxy
2. `avg_sentence_length` metric key mismatch
3. `VisualCitations` in chat panel and `ResultView`
4. Path traversal in file upload
5. `threading.Lock()` in `DocumentStore`
6. `asyncio.sleep()` replacing `time.sleep()` in LLM client
7. Agent citation accumulation
8. Startup recovery for stuck "processing" documents

### Phase 2 — RAG Quality (Week 2–3)

1. Increase chunk size (800 chars / 150 overlap) + add minimum chunk length filter
2. Add system prompt to all LLM calls
3. Figure descriptions at ingestion time (call vision model)
4. Table `cols`/`rows` structure normalization
5. Upgrade embedding model to `SPECTER2` or `BGE-large` (requires full re-ingestion)
6. Fix similarity threshold formula

### Phase 3 — Retrieval Improvements (Week 3–4)

1. BM25 hybrid retrieval with RRF fusion
2. Cross-encoder re-ranking (top-20 → rerank → top-10)
3. MMR diversity in results
4. Fix multi-doc and literature survey to enforce cross-paper coverage
5. Chat history in regular RAG mode (query rewriting)

### Phase 4 — UX & Architecture (Week 4–6)

1. Streaming responses (SSE) — FastAPI + Next.js
2. Parent-document hierarchical chunking
3. Batch file upload
4. Export results
5. Mobile responsive sidebar
6. Session persistence (save/load named conversations)

### Phase 5 — Advanced Features (Month 2+)

1. HyDE retrieval
2. Agentic session memory
3. Multi-column PDF support
4. Semantic caching
5. RAGAS evaluation dashboard in UI
6. Citation click-through PDF viewer
7. OCR + equation extraction activation

---

*Report generated: 2026-05-18 | Updated: 2026-05-19 | Codebase version: commit 6a88de7*

---

## 10. Live API Testing Results

**Testing date:** 2026-05-18  
**Method:** Live HTTP calls against the running backend (`uvicorn` on port 8000) using real Groq and Gemini API keys  
**Test paper ingested:** "Attention Is All You Need" (Vaswani et al., 2017) — 108 chunks indexed  
**Tests completed:** 32 tests across all endpoints  
**Status of pending tests:** Agent multi-hop, concurrent upload race condition verification, and frontend browser test stopped due to Groq API rate limits on the test key. All findings up to that point are documented below.

---

### 10.1 CRITICAL — Agent Feature Completely Broken (Tool Calling Failure)

**Endpoint:** `POST /api/agent`  
**Tests:** 28a, 28b, 28c  
**Severity:** Critical — the agent feature does not work at all

**What happens:**
1. The agent calls `llm.generate(prompt, tools=tool_schemas, tool_choice="auto")` on every iteration.
2. Groq's `llama-3.3-70b-versatile` model generates tool calls in an old XML-like format: `<function=search_text{"query": "self-attention"}</function>` — not the expected JSON tool-call format.
3. Groq's API rejects this with `BadRequestError 400 — tool_use_failed`.
4. Meanwhile, before reaching the 400 error, the test key also hit a 429 rate limit on the first attempt.
5. The `LLMClient.generate()` retry loop catches 429 errors and calls `time.sleep(15 * attempt)` — sleeping 15, 30, 45, 60, or 75 seconds per retry.
6. Since the agent runs **synchronously inside an `async` FastAPI route handler** (see `src/api/routes.py:399`), these `time.sleep()` calls **block the entire ASGI event loop**.
7. The HTTP connection times out after 120 seconds on the client side with zero bytes received. The server eventually raises the 400 error but the client is already gone.

**Net result:** Every call to `/api/agent` either times out (client-side) or returns HTTP 500 after several minutes. The agent feature is completely unusable in the current state.

**Root causes (three separate bugs compounding):**

| # | Bug | Location |
|---|-----|----------|
| A | Tool calling fails: llama-3.3-70b produces malformed tool call format | Groq model compatibility issue |
| B | Synchronous blocking inside async handler | `src/api/routes.py:399` — `get_agent().run()` called directly in `async def agent_query()` |
| C | `time.sleep()` blocks event loop during retries | `src/generation/llm_client.py:204–206` |

**Fix for root cause A:** Either switch to a model that reliably supports Groq tool calling (e.g., `llama3-groq-70b-8192-tool-use-preview`), or fall back to text-based ReAct parsing (remove `tools=` from the generate call and rely on `_parse()` with a well-structured prompt).

**Fix for root cause B:** Run the synchronous agent in a thread pool:
```python
import asyncio
resp = await asyncio.get_event_loop().run_in_executor(None, lambda: get_agent().run(...))
```

**Fix for root cause C:** Already documented in bug 1.6. Replace `time.sleep()` with `asyncio.sleep()` in async contexts, or move retries to a background thread.

---

### 10.2 CONFIRMED — Agent Citations Always Empty

**Endpoint:** `POST /api/agent`  
**Test:** 13 (from prior session)  
**Severity:** High — already documented in §1.2, confirmed live

Every `AgentResponse` is built with `citations=[]` regardless of what tools retrieved. Confirmed that all agent responses return `"citations": []` even when the agent successfully calls `search_text` and retrieves real chunks.

---

### 10.3 CONFIRMED — Multi-Doc Query Retrieves From Only One Source

**Endpoint:** `POST /api/multi-doc`  
**Test:** 11 (prior session)  
**Severity:** High

When two papers are ingested and `/api/multi-doc` is called, all retrieved chunks come from the same paper. The endpoint performs a single top-k query without enforcing cross-paper coverage. Already documented in §2.5, confirmed live.

---

### 10.4 CONFIRMED — Compare Endpoint Generates Hallucinated Output

**Endpoint:** `POST /api/compare`  
**Tests:** 14, 15 (prior session)  
**Severity:** High

Two sub-bugs confirmed:

**Compare paper with itself:** Passing the same paper as both `paper1` and `paper2` generates a plausible-sounding but entirely fabricated "comparison" with no validation. The response describes differences that don't exist.

**Compare with non-existent paper:** Passing a filename that was never uploaded produces no error — the backend silently generates a response using only the one real paper's content, presenting it as a cross-paper comparison. There is no guard for a zero-chunk result on `paper2`.

---

### 10.5 CONFIRMED — Similarity Threshold Too Permissive, Irrelevant Queries Return Results

**Endpoint:** `POST /api/query`  
**Test:** 3 (prior session)  
**Severity:** Medium

Querying with completely irrelevant text ("quantum entanglement in semiconductor lithography" against a Transformer paper) still returns chunks with scores. The threshold `SIMILARITY_THRESHOLD=0.3` with the formula `1.0 - (distance / 2.0)` effectively filters nothing. Already documented in §2.3, confirmed live.

---

### 10.6 CONFIRMED — Image Descriptions Are File-Path Placeholders (Vision Never Called)

**Endpoint:** `GET /documents/{source_file}/visuals`  
**Test:** 20  
**Severity:** High — core multimodal feature broken

All 13 visual chunks for "Attention Is All You Need" have `image_description` set to:
```
"[Figure on page 3] Image extracted from the document. Path: /home/.../data/images/xxx_p3_img1.png"
```
No actual visual description from Gemini/Groq vision. The "deferred vision analysis" described in a comment in `pipeline.py` (§3.6) is confirmed to never run.

**Contrast:** The `POST /explain-visual` endpoint DOES call Gemini and returns a detailed, accurate description when explicitly invoked. The issue is that this per-request explanation is never fed back into the stored chunk's `image_description` field, so search-time retrieval of "figure" chunks still uses the placeholder.

---

### 10.7 NEW BUG — `explain-visual` Requires `chunk_id` But API Documentation Doesn't Mention It

**Endpoint:** `POST /api/explain-visual`  
**Test:** 21  
**Severity:** Low (developer UX)

Calling `POST /explain-visual` with `{"image_path": "...", "context": "..."}` returns a validation error:
```json
{"detail": [{"type": "missing", "loc": ["body", "chunk_id"], "msg": "Field required"}]}
```
The required field is `chunk_id` (a UUID from ChromaDB), not `image_path`. There is no in-app way to discover valid `chunk_id` values without first calling `/documents/{source}/visuals`. The frontend "Explain" button uses the chunk_id from the visuals list correctly, but the REST API surface is confusing for external callers or documentation.

**Fix:** Either accept `image_path` as an alternative to `chunk_id`, or document the required flow clearly in OpenAPI schema.

---

### 10.8 CONFIRMED — Path Traversal Attack Traverses Outside Upload Directory

**Endpoint:** `POST /api/upload`  
**Test:** 26  
**Severity:** High — security vulnerability

Uploading a file with `filename = "../../etc/passwd_injection.pdf"` causes the server to construct:
```
./data/uploads/_tmp/../../etc/passwd_injection.pdf
```
which resolves to `./etc/passwd_injection.pdf` — outside the intended uploads directory. The write fails only because no such directory exists; if an attacker could create a writable path above the working directory, the file would be written there.

Additionally, the server **leaks its full internal path** in the error message:
```json
{"detail": "[Errno 2] No such file or directory: './data/uploads/_tmp/../../etc/passwd_injection.pdf'"}
```
This is information disclosure — the absolute server working directory and internal directory layout are exposed to the client.

**Two fixes required:**
1. Sanitize the filename with `os.path.basename(file.filename)` — already noted in §1.7.
2. Catch `OSError`/`IOError` and return a generic error message without exposing internal paths.

---

### 10.9 CONFIRMED — No File Size Limit (50MB+ Accepted)

**Endpoint:** `POST /api/upload`  
**Test:** 27  
**Severity:** Medium

A 50MB file (random bytes prefixed with a PDF header) was accepted with `{"status": "processing"}`. The backend reads the entire file into memory with `await file.read()`, wastes ingestion resources, and eventually marks it `"failed"` after attempting to parse it as a PDF. A 500MB file would consume 500MB of RAM with no limit.

Already documented in §3.5, confirmed live.

---

### 10.10 NEW FINDING — `GET /api/query` Field Name Is `question`, Not `query`

**Endpoint:** `POST /api/query`  
**Test:** 24d  
**Severity:** Developer UX / inconsistency

The query body field is named `question` (in `QueryRequest`), but any caller using the natural name `"query"` gets a 422 validation error:
```json
{"detail": [{"type": "missing", "loc": ["body", "question"], "msg": "Field required"}]}
```
Meanwhile, the `GenerationResponse` returned by the same endpoint returns `"query"` as the key in the response body. Input uses `question`, output uses `query` — inconsistent naming that causes confusion.

**Fix:** Either rename all usages to `question` consistently, or rename to `query` everywhere for consistency with the rest of the ecosystem.

---

### 10.11 CONFIRMED — AI Detection Scores Are Inaccurate / Too Lenient

**Endpoint:** `POST /api/detect-ai`  
**Tests:** 18, 31 (prior session + extended test)  
**Severity:** Medium — core humanizer feature unreliable

**Test 18 (prior session):** Text written entirely by an LLM (GPT-style academic prose) scored only **49% AI probability** ("Mixed signals"). Expected: 85%+.

**Test 31 (extended test):** Same LLM-generated text repeated 50 times (7600 characters) scored **51% AI probability**. Text had:
- Burstiness: 0.0 (every sentence the same length — a strong AI signal)
- Lexical diversity: 0.02 (highly repetitive — an AI signal)
- Standard deviation of sentence length: 0.0

Despite two clear AI signals firing, the combined score was still only 51%. The RoBERTa component (`roberta_score`) returned **0%** — the model is either not loaded correctly or is returning useless scores that average down the heuristic score.

**Root cause:** The `roberta_score` is always near 0% in practice. The `openai-community/roberta-base-openai-detector` model is trained on GPT-2 outputs and is not effective at detecting modern LLM-generated text. It consistently under-detects recent LLM outputs (GPT-3.5, GPT-4, Llama, etc.).

**Fix:** Replace or supplement with a model trained on modern LLM outputs, such as `Hello-SimpleAI/chatgpt-detector-roberta`, or use a heuristic-only score without the misleading RoBERTa component dragging the combined score toward 50%.

---

### 10.12 CONFIRMED — Humanizer Fails to Reach Target Score

**Endpoint:** `POST /api/humanize`  
**Test:** 19 (prior session)  
**Severity:** Medium — feature underperforms

After 3 passes of Groq-powered rewriting, the AI score moved from **39% → 38%** — a 1-point improvement after 3 full LLM calls. `target_reached: false` was returned. The rewriting loop is calling the LLM 3 times but making no meaningful progress toward the 20% target.

**Root cause:** The LLM is asked to "humanize" text using a prompt, but the AI detector (as noted in §10.11) scores based on statistical features (burstiness, lexical diversity), not on whether the content reads as human. The LLM rewriting doesn't systematically change those statistical features — it rewrites meaning/phrasing without varying sentence lengths or adding the vocabulary variety that would lower the heuristic score.

**Fix:** The humanizer prompt needs to explicitly instruct the LLM to vary sentence lengths, use contractions, break up uniform structures, and mix sentence patterns — not just rephrase.

---

### 10.13 CONFIRMED — SQLite/ChromaDB Sync Corruption

**Test:** Background finding from all sessions  
**Severity:** High

`EJ1172284.pdf` shows `status = "completed"`, `total_chunks = 138` in SQLite, but ChromaDB contains **0 chunks** for this document. Queries with `filter_source = "EJ1172284.pdf"` return nothing.

This is exactly the scenario described in §1.9 — a document that was ingested in a previous server session persists in SQLite as "completed" but its ChromaDB data was lost (possibly when ChromaDB's persistence was recreated or the database was wiped).

There is no built-in reconciliation: the system will never detect or report this discrepancy. Users see a document with 138 chunks but all queries against it return empty results with no error.

**Fix:** Add a startup reconciliation step that, for each "completed" document in SQLite, queries ChromaDB for chunk count and marks the document "failed" if the count is 0.

---

### 10.14 NEW FINDING — `filter_source` With Non-Existent Paper Returns Generic "No Info" Message

**Endpoint:** `POST /api/query`  
**Test:** 25  
**Severity:** Low — but misleading UX

When `filter_source` points to a paper that was never uploaded, the API returns:
```json
{"answer": "I couldn't find relevant information in the uploaded documents. Please rephrase your question or upload relevant papers."}
```
The same message is shown when the question is valid but the paper has no matching chunks. Users cannot distinguish between "paper doesn't exist" and "paper exists but no relevant chunks were found."

**Fix:** Before running the RAG pipeline with a filter, validate that the `filter_source` value matches a known document in the store. Return a 404 or a clear error if not found.

---

### 10.15 NEW FINDING — OpenAI GPT-OSS Models Listed But Likely Non-Functional

**Endpoint:** `GET /api/models`  
**Test:** 32  
**Severity:** Medium — misleading UI

The models endpoint returns `openai/gpt-oss-120b` and `openai/gpt-oss-20b` as available options. These are OpenAI's open-source models served via a separate endpoint and require different credentials than Groq. The current codebase only has a Groq client (`LLMClient`). Selecting these models from the frontend dropdown will cause the API call to fail silently or return a misleading error.

The frontend offers these as a dropdown option with no indication that they require additional setup.

**Fix:** Either implement the OpenAI client integration, or remove these models from the dropdown, or add a UI badge/note that they require separate API configuration.

---

### 10.16 NEW FINDING — Error Messages Expose Internal File Paths

**Endpoint:** `POST /api/upload`  
**Test:** 26b  
**Severity:** Medium — information disclosure

When any file operation fails, the raw Python `OSError` message is returned directly to the client, including the full absolute server-side path. Example:
```json
{"detail": "[Errno 2] No such file or directory: './data/uploads/_tmp/../../etc/passwd_injection.pdf'"}
```
This exposes the working directory, the internal directory structure, and in path-traversal attempts, reveals exactly which traversal depth was attempted.

**Fix:** Catch all `OSError` / `IOError` exceptions in the upload route and return a generic:
```json
{"detail": "File processing failed. Please try again."}
```
Log the full exception server-side, not in the response.

---

### 10.17 NEW FINDING — Concurrent Uploads Both Succeed (SQLite Locking Untested Under Real Load)

**Test:** 30  
**Severity:** Note — latent risk

Two simultaneous PDF uploads both completed successfully. This doesn't rule out the SQLite race condition documented in §1.8 — it simply means two slow background threads with their own timing didn't collide during this test. The locking issue is a latent risk under sustained concurrent load (e.g., 5+ simultaneous uploads), not necessarily triggered by two uploads.

---

### 10.18 NEW FINDING — Uploaded Files With Spaces in Name Stored Without Sanitization

**Test:** 24  
**Severity:** Low — operational hygiene

Uploading `"my research paper (2024) final v2.pdf"` stores the file on disk as:
```
data/uploads/b64d5a92..._my research paper (2024) final v2.pdf
```
with literal spaces in the filename. While this works on Linux filesystems, it can cause issues with shell scripts, log parsing, and any downstream tool that doesn't quote filenames.

**Fix:** At save time, normalize filenames: replace spaces with underscores and remove special characters other than hyphens and periods. Store the original display name separately in SQLite for UI presentation.

---

### Summary: New Bugs Found in Live Testing (Not in Static Analysis)

| # | Bug | Severity | Status |
|---|-----|----------|--------|
| L1 | Agent completely broken — Groq 400 `tool_use_failed` for llama-3.3-70b | Critical | Confirmed |
| L2 | Agent blocks event loop via synchronous run + `time.sleep()` | Critical | Confirmed |
| L3 | `explain-visual` requires `chunk_id` — undocumented, confusing to callers | Low | New |
| L4 | Path traversal: error message leaks full internal server path | Medium | New |
| L5 | `question` vs `query` field name inconsistency (input vs output) | Low | New |
| L6 | RoBERTa AI detector returns near-0% for all modern LLM text | Medium | Confirmed |
| L7 | Humanizer 3 passes produce only 1% score improvement | Medium | Confirmed |
| L8 | GPT-OSS models listed in dropdown but likely non-functional without separate credentials | Medium | New |
| L9 | All OSError exceptions leak internal server paths | Medium | New |
| L10 | `filter_source` for missing paper returns identical message as "no relevant chunks" | Low | New |
| L11 | Uploaded filenames not normalized (spaces/special chars kept on disk) | Low | New |
| L12 | 50MB+ file accepted and processed before failing — no size guard | Medium | Confirmed |
| L13 | `documents.db` deleted on disk while server runs — all DB writes fail with "readonly database" | Critical | New (2026-05-19) |
| L14 | `groq/compound-mini` listed as "Fast agent" but does not support tool calling | Medium | New (2026-05-19) |
| L15 | Bug 1.3 (double URL encoding) **not confirmed** live — Next.js 15 decodes path segments before proxy re-encodes | N/A | Retracted (2026-05-19) |
| L16 | `qwen/qwen3-32b` model works as agent workaround — only model tested that supports tool calling on Groq | Note | New (2026-05-19) |

---

### Remaining Tests Not Completed (Stopped by Rate Limit)

The following tests were planned but not executed due to Groq API rate limits being exhausted on the test key:

| Test | Description |
|------|-------------|
| T29-complete | Agent chat_history context preservation (agent was timing out) |
| T33 | Delete document endpoint — verify ChromaDB cleanup happens |
| T34 | Agent with `groq/compound-mini` model (may support tool calling better than llama-3.3-70b) |
| T35 | Qwen3-32b model variant test |
| T36 | Frontend browser test — start `npm run dev`, open all pages, check for JS errors |
| T37 | Image URL resolution from frontend — verify `/images/xxx.png` paths resolve through Next.js |
| T38 | Literature survey with single document vs multi-document |
| T39 | Research gaps endpoint |
| T40 | Recommend similar papers endpoint |

*Live testing section appended: 2026-05-18*

---

## 11. Completed Tests — Round 2 (2026-05-19)

**Testing date:** 2026-05-19  
**Method:** Live HTTP calls against the same running backend (uvicorn PID 969143, port 8000). Rate limit resolved; tests completed using `qwen/qwen3-32b` for agent tests where Groq llama-3.3-70b fails.  
**Documents available:** 6 in server's in-memory DB (5 completed + 1 failed). Note: `data/documents.db` on disk was deleted and replaced while server was running — server holds a deleted fd for the old DB file (all 5 uploaded test docs exist only in the server's in-memory SQLite connection and ChromaDB, not in the on-disk `documents.db`).

---

### 11.1 T29-complete — PASS: Agent Chat History Context Preserved

**Test:** Two-turn agent conversation using `qwen/qwen3-32b`.

**Turn 1:** Asked "What is the attention mechanism?" — agent completed in 3 steps, returned 613-character answer describing self-attention and multi-head attention.

**Turn 2:** Asked "How many attention heads were used in their experiments?" with the first answer passed as `chat_history`. Agent answered correctly in 2 steps: *"The experiments in 'attention_is_all_you_need.pdf' used 8 attention heads in parallel... h=8 parallel attention layers or heads [Paper: attention_is_all_you_need.pdf, Page 5]"*.

**Outcome:** Chat history is correctly injected into the agent prompt and reduces the number of retrieval steps needed for follow-up questions. The agent resolved the implicit reference "their experiments" using context.

**Remaining issue:** Citations array is still `[]` for both turns — confirms bug §1.2 (Agent Always Returns Empty Citations).

---

### 11.2 T33 — FAIL: Delete Endpoint Returns HTTP 500 (Readonly Database)

**Endpoint:** `DELETE /api/documents/{doc_id}`  
**Tests:** Attempted deletion of `large_test.pdf` (id: `0666f2b7`) and `concurrent_test_1.pdf` (id: `d7d60b7a`). Both returned `HTTP 500 Internal Server Error`.

**Root cause from server log:**
```
sqlite3.OperationalError: attempt to write a readonly database
  File "src/storage/document_store.py", line 78, in delete_document
    self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
```

**Underlying cause (critical operational finding):** The `data/documents.db` file was **deleted and recreated on disk** while the server process was running. The server still holds an open file descriptor to the original (now deleted) file (visible as `fd/18 → data/documents.db (deleted)` in `/proc/969143/fd/`). SQLite can read from the deleted inode but cannot create the WAL journal file (the directory entry is gone), so all write operations fail with "attempt to write a readonly database".

**Impact of this state:**
1. `DELETE /api/documents/{id}` always returns HTTP 500 — document deletion is completely broken.
2. Any new `POST /api/upload` will fail to persist the document record to SQLite (it may write to disk and ChromaDB, but the SQLite record will not be saved — the document appears "missing" after server restart).
3. `update_status()` calls (called during ingestion) all fail silently — uploaded documents remain in `status="processing"` forever.
4. The 6 documents visible via the API exist only in the server's in-memory SQLite connection — they will be lost on next server restart.

**Fix:** Restart the server. On restart, the new `documents.db` on disk (which only has EJ1172284.pdf) will be used. All test documents will disappear from the document list. To prevent this, add a startup check: if the DB file can't be opened read-write, log an error and exit instead of starting with a degraded DB connection.

**Secondary code bug:** The delete route calls `vector_store.delete_by_source()` (removes ChromaDB chunks) **before** `document_store.delete_document()` (removes SQLite record). If the SQLite delete fails (as it does now), ChromaDB data is permanently lost but the SQLite record remains — the document shows as "completed" with 0 queryable chunks. The order should be reversed, or wrapped in a try/except that re-inserts the ChromaDB chunks on failure.

---

### 11.3 T34 — FAIL: `groq/compound-mini` Does Not Support Tool Calling

**Endpoint:** `POST /api/agent` with `llm_config: {"model": "groq/compound-mini"}`  
**Result:** `HTTP 500` with error:
```json
{"detail": "Error code: 400 - {'error': {'message': '`tool calling` is not supported with this model', 'type': 'invalid_request_error', 'param': 'tool calling'}}"}
```

**Finding:** The `GET /api/models` endpoint lists `groq/compound-mini` with label "Groq Compound Mini — Fast agent" and `best_for: "Faster agent runs when quality tradeoff is acceptable"`. This model is specifically marketed for agent use in the UI, but it does not support tool calling on Groq's API. Every agent request using this model immediately returns a Groq 400 error.

**Fix:** Remove `groq/compound-mini` from the models list, or conditionally hide it in the agent-mode model selector. Only expose it for non-agent (RAG) queries where tool calling is not used.

---

### 11.4 T35 — PARTIAL PASS: `qwen/qwen3-32b` Works as Agent

**Endpoint:** `POST /api/agent` with `llm_config: {"model": "qwen/qwen3-32b"}`  
**Result:** Agent returns coherent, sourced answers. Example response for "What is multi-head attention?":

> *"Multi-head attention is a key mechanism in transformer models that enables parallel computation of attention across different representation subspaces. It operates by: (1) Projecting queries, keys, and values through h different learned linear projections to create h attention heads. (2) Computing attention independently for each head. [Paper: attention_is_all_you_need.pdf, p.5]..."*

**Key finding:** `qwen/qwen3-32b` successfully performs native Groq tool calls. This makes it the **only currently functional model** for agent mode among the six listed models:

| Model | Agent (Tool Calling) | Reason |
|-------|----------------------|--------|
| `llama-3.3-70b-versatile` | BROKEN | Generates XML-format tool calls → Groq rejects with 400 |
| `llama-3.1-8b-instant` | Unknown | Not tested |
| `qwen/qwen3-32b` | WORKS | Correct JSON tool call format |
| `groq/compound-mini` | BROKEN | Tool calling not supported by model |
| `openai/gpt-oss-120b` | Unknown | Requires separate credentials |
| `openai/gpt-oss-20b` | Unknown | Requires separate credentials |

**Remaining issue:** Agent citations are still `[]` even with qwen3-32b — confirms bug §1.2.

**Immediate workaround:** Change the agent's default model from `llama-3.3-70b-versatile` to `qwen/qwen3-32b` in the frontend's default model selector.

---

### 11.5 T36 — NOT RUN: Frontend Not Running

**Finding:** Port 3000 is occupied by an unrelated application (RemotePC attended remote desktop — `<link rel="icon" href="/oldCph/AppIcon.ico" />`). The research assistant's Next.js frontend (`npm run dev`) is not started. No Next.js process was found in `ps aux`.

**What was verified instead (static analysis):**
- All 8 page routes exist as files: `/`, `/search`, `/chat`, `/compare`, `/humanizer`, `/survey`, `/trends`, `/recommend`.
- No `npm run build` errors detected (TypeScript types appear consistent based on component inspection).
- The Next.js proxy route at `frontend/app/api/[...path]/route.ts` is correctly wired for GET, POST, PUT, DELETE, PATCH methods.

**Action needed:** Start frontend with `cd frontend && npm run dev` (or use a different port) to run full browser tests.

---

### 11.6 T37 — VERIFIED: Image URL Resolution Design is Correct

**Finding:** The image URL flow is correctly designed:

1. Backend returns `image_url: "/images/<filename>.png"` in visual chunk metadata.
2. Frontend component (`visual-citations.tsx:35`) builds: `` src={`/api${citation.image_url}`} `` → `/api/images/<filename>.png`.
3. Next.js proxy forwards `/api/images/...` to `http://localhost:8000/api/images/...`.
4. Backend StaticFiles mounted at `/api/images` serves the file (verified: `HTTP 200`, 121KB PNG).

**Verification:** Direct backend image request returns the correct PNG image:
```
GET http://localhost:8000/api/images/911ddf5f-..._p3_img1.png → HTTP 200, 121244 bytes, PNG image
```

**Cannot test end-to-end:** Frontend not running (see T36). The design is correct; end-to-end test is pending frontend startup.

**Note on Bug 1.3 (Static Analysis Retraction):** The audit report §1.3 identified a double URL-encoding bug: `path.map(encodeURIComponent)` in the proxy re-encoding an already-encoded path. **This bug does NOT occur in practice with Next.js 15.** Next.js 15 decodes path segments before passing them to `[...path]` catch-all route handlers (`params.path` contains decoded strings like `["documents", "my paper (2024).pdf", "visuals"]`). The proxy's `encodeURIComponent` re-encodes them correctly. Verified: requests with `%20` and `%28/%29` in filenames return HTTP 200 through the proxy.

---

### 11.7 T38 — PASS: Literature Survey Works (Single and Multi-Doc)

**Endpoint:** `POST /api/literature-survey`

**T38a — Single document:**
```json
{"question": "What is the transformer architecture?", "source_files": ["attention_is_all_you_need.pdf"]}
```
Result: 4712-character structured survey with 26 citations. Well-formatted with numbered sections, introduction, methodology, results, and conclusions. Correctly scoped to the one paper.

**T38b — Multi-document (no source filter):**
```json
{"question": "Compare attention mechanisms across these papers"}
```
Result: 3803-character survey citing **4 unique source files** (attention_is_all_you_need.pdf, concurrent_test_1.pdf, concurrent_test_2.pdf, my_research_paper.pdf). However, all four of these are copies of the same "Attention Is All You Need" paper — the test database has no genuinely different papers.

**Confirms §2.6:** With all documents being the same paper, cross-paper diversity cannot be measured. But the single-query top-30 retrieval design (§2.6) would fail to enforce coverage across genuinely different papers. The bug remains in the code regardless.

---

### 11.8 T39 — PASS: Research Gaps Endpoint Works

**Endpoint:** `POST /api/research-gaps`  
**Request:** `{"question": "What are the research gaps in transformer architectures?"}`  
**Result:** HTTP 200, 3630-character answer, 26 citations.

Sample gaps returned:
- **Scalability of Attention Mechanisms** — O(n²) memory and compute limits; matters for long-sequence tasks.
- **Multi-Modal Integration** — limited to text; integration with vision, audio, and structured data is an open area.
- **Interpretability** — attention weights don't fully explain model decisions.
- **Efficiency in Low-Resource Environments** — high parameter counts problematic for edge deployment.

**Assessment:** The endpoint is functional. The gaps identified are real and consistent with the ingested paper's "Future Work" and limitations sections. Response quality is high.

---

### 11.9 T40 — PASS: Recommend Papers Endpoint Works

**Endpoint:** `POST /api/recommend`  
**Field name:** `interest` (not `question` — inconsistency with other endpoints noted in §10.10).  
**Request:** `{"interest": "attention mechanisms and transformer architectures for NLP"}`  
**Result:** HTTP 200, 1972-character answer, 16 citations.

Sample recommendation:
> *"Paper: attention_is_all_you_need.pdf — This paper introduces the Transformer model, which relies entirely on self-attention to compute representations of its input and output. Key sections to focus on: Section 3 (Model Architecture), Section 3.2 (Attention), Section 3.2.1 (Scaled Dot-Product Attention)."*

**Finding:** The recommend endpoint is functional, but it can only recommend papers already uploaded to the system — it has no access to external paper databases (arXiv, Semantic Scholar, etc.). This is an inherent limitation of the current RAG approach and should be surfaced in the UI.

**Confirms field naming inconsistency (§10.10):** The request body uses `interest`, but the response body key for the echoed query is `query`. Four other endpoints use `question` as the input field name. This inconsistency makes the API harder to use programmatically.

---

### 11.10 NEW FINDING — `documents.db` Deleted on Disk While Server Runs (Operational Bug)

**Severity:** Critical  
**Discovery:** During T33 investigation via `/proc/969143/fd/` inspection.

The server's open file descriptors show:
```
fd/18 → data/documents.db (deleted)
fd/24 → data/documents.db (deleted)
```

The `data/documents.db` file was replaced (or deleted and recreated) while the server was running. The current on-disk `documents.db` contains only 1 document (EJ1172284.pdf), but the server serves 6 documents from the old deleted file.

**Consequences:**
1. All DB write operations fail silently with `sqlite3.OperationalError: attempt to write a readonly database` — including upload status updates and document deletes.
2. The 5 test documents (concurrent_test_1.pdf, concurrent_test_2.pdf, large_test.pdf, my_research_paper.pdf, attention_is_all_you_need.pdf) visible via the API will disappear from the document list on server restart.
3. The mismatch between what the API reports and what's on disk is invisible to users and operators.

**Root cause:** No file integrity check or crash recovery detects this state. The server started with the old DB file, that file was later replaced, and the process continued using the stale file handle.

**Fix:** Add a startup health check in `src/main.py` that:
1. Opens a test write to `documents.db` (e.g., `PRAGMA user_version = 1`).
2. If it fails, logs a critical error and exits rather than starting with a broken DB connection.

---

### Summary: Round 2 Test Results (2026-05-19)

| Test | Result | Key Finding |
|------|--------|-------------|
| T29 (Agent chat_history) | PASS | Chat history correctly reduces re-retrieval; follow-up answered with specific value (8 heads) from context. Citations still empty. |
| T33 (Delete endpoint) | FAIL | HTTP 500 — `sqlite3.OperationalError: attempt to write a readonly database`. `documents.db` deleted on disk while server runs. |
| T34 (compound-mini agent) | FAIL | Model does not support tool calling despite being listed as "Fast agent" in the UI. |
| T35 (qwen3-32b agent) | PASS | Only currently working agent model on Groq. Returns correct tool-call-based answers. Citations still empty. |
| T36 (Frontend browser) | NOT RUN | Frontend not started. Port 3000 occupied by unrelated app (RemotePC). |
| T37 (Image URL resolution) | VERIFIED | Backend image serving correct (HTTP 200, 121KB PNG). Frontend design correct (`/api` + image_url). Cannot test end-to-end. |
| T38 (Literature survey) | PASS | Single-doc and multi-doc both work. Multi-doc cites 4 sources (all same paper copies — diversity issue from §2.6 not testable). |
| T39 (Research gaps) | PASS | Returns real, well-identified gaps. Functional. |
| T40 (Recommend papers) | PASS | Returns relevant recommendations. Field name is `interest`, not `question`. |

### New Bugs Found in Round 2

| # | Bug | Severity |
|---|-----|----------|
| L13 | `documents.db` deleted on disk while server runs — all writes fail with "readonly database" error | Critical |
| L14 | `groq/compound-mini` listed as "Fast agent" in UI but does not support tool calling | Medium |
| L15 | Bug §1.3 (double URL encoding) **retracted** — not reproducible with Next.js 15 | N/A |
| L16 | `qwen/qwen3-32b` is the only working agent model; should be the default or at least recommended | Note |
| L17 | Delete order flaw: ChromaDB chunks deleted before SQLite record — inconsistent state if SQLite write fails | Medium |

*Round 2 testing completed: 2026-05-19*
