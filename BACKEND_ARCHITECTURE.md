# Backend Architecture — Multimodal AI Research Assistant

## Overview

The backend is a **FastAPI** server running on `localhost:8000`. It handles everything — document processing, storage, retrieval, LLM generation, and agentic reasoning. The frontend (Streamlit) is just a thin UI that makes HTTP calls to this backend.

---

## 1. Entry Point — `src/main.py`

- Creates a FastAPI app with CORS middleware (allows all origins so Streamlit can talk to it)
- Mounts all API routes under `/api` prefix
- Runs via Uvicorn ASGI server on `0.0.0.0:8000`
- Calls `ensure_directories()` on startup to create `data/uploads/`, `data/images/`, `data/chroma_db/`

---

## 2. Configuration — `src/config.py`

Uses **Pydantic Settings** to load everything from `.env`:

| Setting | Value | Purpose |
|---------|-------|---------|
| `gemini_api_key` | from .env | Gemini Vision API (image tasks only) |
| `groq_api_key` | from .env | Groq API (all text generation) |
| `embedding_model` | all-MiniLM-L6-v2 | Sentence-transformer model name |
| `chroma_persist_dir` | data/chroma_db | Where ChromaDB stores vectors on disk |
| `upload_dir` | data/uploads | Where uploaded PDFs are saved |
| `images_dir` | data/images | Where extracted images are saved |
| `chunk_size` | 512 | Characters per chunk |
| `chunk_overlap` | 50 | Overlap between consecutive chunks |
| `top_k` | 10 | Default number of results to retrieve |
| `similarity_threshold` | 0.3 | Minimum similarity score to include a result |

---

## 3. API Layer — `src/api/routes.py`

**14 REST endpoints** handling all frontend requests:

| Endpoint | What it does internally |
|----------|------------------------|
| `POST /api/upload` | Saves PDF to disk → spawns a **background thread** that runs the full ingestion pipeline → returns immediately with "processing" status |
| `GET /api/documents` | Queries SQLite for all document records with their status |
| `DELETE /api/documents/{id}` | Deletes from SQLite + deletes all chunks from ChromaDB for that document |
| `POST /api/query` | Calls `RAGPipeline.query()` — single-shot RAG |
| `POST /api/agent` | Calls `ResearchAgent.run()` — multi-hop ReAct loop |
| `POST /api/summarize` | Calls `RAGPipeline.summarize()` |
| `POST /api/compare` | Calls `RAGPipeline.compare()` |
| `POST /api/literature-survey` | Calls `RAGPipeline.literature_survey()` |
| `POST /api/research-gaps` | Calls `RAGPipeline.identify_gaps()` |
| `POST /api/explain` | Calls `RAGPipeline.explain()` |
| `POST /api/recommend` | Calls `RAGPipeline.recommend()` |
| `POST /api/trends` | Calls `RAGPipeline.analyze_trends()` |
| `POST /api/multi-doc` | Calls `RAGPipeline.multi_doc_query()` |
| `GET /api/health` | Returns `{"status": "healthy"}` |

A **threading lock** (`_ingest_lock`) serializes PDF ingestion so two uploads don't corrupt the database simultaneously.

---

## 4. Data Models — `src/models/schemas.py`

**8 dataclasses** that define all the data structures flowing through the system:

| Model | What it represents |
|-------|--------------------|
| `ExtractedElement` | Raw output from any processor (text block, table, image, equation) — carries content, element_type, page_number, section_heading |
| `ChunkMetadata` | Rich metadata per chunk: source_file, page_number, section_heading, chunk_index, element_type, table_data, latex_source, image_path, image_description, confidence, created_at |
| `Chunk` | The core data unit — content string + content_type + ChunkMetadata + UUID4 id + embedding vector |
| `DocumentInfo` | Document lifecycle record — id, filename, file_path, file_type, total_pages, total_chunks, ingested_at, status (pending/processing/completed/failed) |
| `QueryResult` | One search result — a Chunk + similarity score + rank |
| `GenerationResponse` | Output from any RAG method — answer, citations list, query, intent, chunks_used |
| `AgentStep` | One iteration of the ReAct loop — step_number, thought, action, action_input, observation |
| `AgentResponse` | Output from the agent — answer, list of AgentSteps, citations, query, intent, chunks_used, total_steps |

---

## 5. Ingestion Pipeline — `src/ingestion/`

This is the **document processing module** — runs when a PDF is uploaded. It has **7 components** that execute in sequence:

### 5a. PDFProcessor (`pdf_processor.py`)

- **Library:** PyMuPDF (fitz)
- **What it does:** Opens the PDF, iterates page by page, extracts all text blocks
- **Heading detection:** Identifies section headings by two rules:
  - Font size >= 14pt (body text is typically 10-12pt)
  - Text matches one of 21 known keywords: abstract, introduction, background, related work, methodology, method, methods, approach, proposed, experiment, experiments, results, evaluation, discussion, conclusion, conclusions, future work, references, appendix, acknowledgment, acknowledgments
  - Also handles numbered headings like "1. Introduction", "2.1 Method"
- **Output:** List of `ExtractedElement` objects with `element_type="text"`, each tagged with its page number and detected section heading

### 5b. TableExtractor (`table_extractor.py`)

- **Library:** pdfplumber
- **What it does:** Opens the PDF separately with pdfplumber (which is better at table detection than PyMuPDF), finds tables on each page
- **Conversion:** Each table is converted to **pipe-delimited Markdown** format (header row + separator + data rows)
- **Metadata:** Stores raw table data (rows, columns, cell values) in `table_data` dict
- **Output:** `ExtractedElement` objects with `element_type="table"`

### 5c. ImageExtractor (`image_extractor.py`)

- **Library:** PyMuPDF (fitz)
- **What it does:** Iterates through each page, calls `page.get_images()` to find embedded images, extracts and saves them to `data/images/`
- **Naming:** `{doc_id}_p{page_num}_img{img_idx}.{ext}` (e.g., `abc123_p5_img0.png`)
- **Output:** `ExtractedElement` objects with `element_type="figure"` and `image_path` in metadata

### 5d. OCRProcessor (`ocr_processor.py`)

- **Library:** EasyOCR
- **What it does:** Takes an extracted image, runs OCR to detect text (useful for scanned papers or handwritten content)
- **Config:** English language, GPU disabled for compatibility
- **Output:** `ExtractedElement` with OCR'd text and confidence score

### 5e. VisionAnalyzer (`vision_analyzer.py`)

- **Library:** Google Gemini Vision API
- **What it does:** Sends each extracted image to Gemini with a prompt: "Describe this image from a research paper in detail. If it's a graph, explain the axes, data trends, and key findings..."
- **Output:** A detailed text description of the figure/chart/diagram
- **This is why Gemini is still needed** — Groq doesn't support image input

### 5f. EquationExtractor (`equation_extractor.py`)

- **Library:** Google Gemini Vision API
- **What it does:** Sends equation images to Gemini with a prompt asking to extract LaTeX and provide an explanation
- **Output:** `{"latex": "\\sum_{i=1}^{n} x_i", "explanation": "Summation of all x values..."}`

### 5g. SemanticChunker (`chunker.py`)

- **Library:** LangChain's `RecursiveCharacterTextSplitter`
- **What it does:** Takes all extracted elements and splits them into chunks for embedding
- **Config:** 512 chars per chunk, 50 char overlap
- **Separators (in priority):** `["\n\n", "\n", ". ", " ", ""]` — tries to split at paragraph boundaries first, then lines, then sentences, then words
- **Type-aware strategy:**
  - Text → split into multiple chunks
  - Tables → kept as a single chunk (whole table = one chunk)
  - Figures → kept as a single chunk (description = one chunk)
  - Equations → kept as a single chunk (LaTeX + explanation = one chunk)
- **Each chunk gets rich metadata:** source_file, page_number, section_heading, chunk_index, element_type, confidence, created_at, and type-specific fields (image_path, latex_source, table_data)

---

## 6. Storage Layer — `src/storage/`

### 6a. EmbeddingService (`embedding_service.py`)

- **Library:** Sentence-Transformers
- **Model:** all-MiniLM-L6-v2 (384-dimensional vectors)
- **Pattern:** Singleton — the model is loaded once into memory and shared everywhere (avoids loading a ~90MB model multiple times)
- **Normalization:** Enabled — all vectors are L2-normalized
- **Batch processing:** Embeds texts in batches of 32 for efficiency
- **Used by:** Both ingestion (embed chunks) and retrieval (embed queries)

### 6b. VectorStore (`vector_store.py`)

- **Library:** ChromaDB
- **Collection name:** "research_chunks"
- **Index:** HNSW (Hierarchical Navigable Small World) — an approximate nearest neighbor index
- **Distance metric:** Cosine
- **Persistence:** Stored on disk at `data/chroma_db/` — survives server restarts
- **What it stores per chunk:** ID (UUID), embedding vector (384 floats), text content, and all metadata fields
- **Search:** Takes a query embedding → finds nearest neighbors by cosine distance → returns chunks with distances
- **Distance → Similarity conversion:** `similarity = 1.0 - (distance / 2.0)` (cosine distance ranges 0-2, so this maps to 0-1)
- **Filtering:** Supports `where` clauses to filter by `source_file` (specific paper) or `content_type` (text/table/figure/equation)
- **Operations:** add_chunks, search, delete_by_source, get_all_sources, count

### 6c. DocumentStore (`document_store.py`)

- **Library:** SQLite3 (built-in Python)
- **Database:** `data/documents.db`
- **Table schema:**

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT DEFAULT 'pdf',
    total_pages INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    ingested_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending'
)
```

- **Status lifecycle:** `pending` → `processing` → `completed` (or `failed`)
- **Purpose:** Tracks which documents are uploaded, their processing status, page counts, chunk counts

---

## 7. Retrieval Layer — `src/retrieval/`

### 7a. Retriever (`retriever.py`)

The bridge between queries and the vector store.

- **`retrieve(query, top_k, filter_source, filter_type)`:**
  1. Embeds the query string using EmbeddingService (same model used for chunks)
  2. Calls VectorStore.search() with the query embedding
  3. Filters results below similarity threshold (0.3)
  4. Returns ranked list of `QueryResult` objects

- **`build_context(results, max_context_length)`:**
  - Formats retrieved chunks into a single context string
  - Format: `[Source: filename, Page X, Section: heading] (score=0.XX)\ncontent text\n---`
  - Truncates at `max_context_length` characters

- **`get_citations(results)`:**
  - Extracts structured citation dicts: `{source_file, page_number, section_heading, score}`

### 7b. RAGPipeline (`rag_pipeline.py`)

**9 methods**, each following the same pattern: **retrieve → build context → inject into prompt → call LLM → return response**

Each method has a **different retrieval strategy** optimized for its task:

| Method | Query Strategy | Top-K | Max Context | Prompt |
|--------|----------------|-------|-------------|--------|
| `query()` | User's question directly | 10 | 4000 chars | QA_PROMPT |
| `summarize()` | Fixed: "main contributions methodology results conclusions abstract" | 20 | 6000 chars | SUMMARIZE_PROMPT |
| `compare()` | Fixed: "methodology approach contributions results evaluation" — **separate retrieval per paper** | 15 each | 3000 chars/paper | COMPARE_PAPERS_PROMPT |
| `literature_survey()` | User's topic or fixed broad query | 30 | 8000 chars | LITERATURE_SURVEY_PROMPT |
| `identify_gaps()` | **3 queries** (limitations, future work, drawbacks) — deduplicated | ~30 | 6000 chars | RESEARCH_GAP_PROMPT |
| `explain()` | User's concept | 12 | 5000 chars | CONCEPT_EXPLANATION_PROMPT |
| `recommend()` | User's interest | 20 | 6000 chars | RECOMMENDATION_PROMPT |
| `analyze_trends()` | **3 queries** (methodology, results, datasets) — deduplicated | ~45 | 8000 chars | TREND_ANALYSIS_PROMPT |
| `multi_doc_query()` | User's question (no source filter) | 20 | 7000 chars | MULTI_DOC_PROMPT |

---

## 8. Generation Layer — `src/generation/`

### 8a. LLMClient (`llm_client.py`)

- **Text generation:** Uses **Groq API** with `llama-3.3-70b-versatile`
- **Vision tasks:** Uses **Gemini 2.0 Flash** (via `gemini_call_with_retry`) — only used by VisionAnalyzer and EquationExtractor during ingestion
- **Retry logic:** 5 attempts with escalating backoff (15s, 30s, 45s, 60s, 75s) on 429 errors
- **Gemini rate limiter:** Thread-safe, 4s minimum interval between vision API calls
- **Two methods:**
  - `generate(prompt, temperature, max_tokens)` — raw generation via Groq
  - `generate_with_context(prompt_template, **kwargs)` — fills a template with `.format()` then generates

### 8b. Prompts (`prompts.py`)

**13 prompt templates** — each is a carefully crafted string with `{placeholders}` for variable injection:

| # | Template Name | Used By | Purpose |
|---|---------------|---------|---------|
| 1 | `QA_PROMPT` | `RAGPipeline.query()` | Answer questions based on retrieved context |
| 2 | `SUMMARIZE_PROMPT` | `RAGPipeline.summarize()` | Summarize research papers |
| 3 | `COMPARE_PROMPT` | (Legacy) | Basic paper comparison |
| 4 | `EXPLAIN_VISUAL_PROMPT` | (Available) | Explain visual elements from papers |
| 5 | `EXPLAIN_EQUATION_PROMPT` | (Available) | Explain equations step-by-step |
| 6 | `COMPARE_PAPERS_PROMPT` | `RAGPipeline.compare()` | Detailed structured paper comparison |
| 7 | `LITERATURE_SURVEY_PROMPT` | `RAGPipeline.literature_survey()` | Generate literature survey with themes, methodology, findings |
| 8 | `RESEARCH_GAP_PROMPT` | `RAGPipeline.identify_gaps()` | Identify gaps: description, importance, citations, approaches |
| 9 | `CONCEPT_EXPLANATION_PROMPT` | `RAGPipeline.explain()` | Explain concepts: definition, mechanism, relevance, examples |
| 10 | `RECOMMENDATION_PROMPT` | `RAGPipeline.recommend()` | Recommend papers: name, reasons, key sections, connections |
| 11 | `TREND_ANALYSIS_PROMPT` | `RAGPipeline.analyze_trends()` | Analyze trends: methodology, datasets, performance, techniques |
| 12 | `MULTI_DOC_PROMPT` | `RAGPipeline.multi_doc_query()` | Multi-document synthesis with source attribution |
| 13 | `AGENT_PROMPT` | `ResearchAgent.run()` | ReAct agent with tool definitions and format instructions |

Every prompt has strict **RULES** telling the LLM to only use provided context and cite sources. The LLM never searches the web — it only generates from retrieved document chunks.

---

## 9. Agentic Reasoning — `src/agents/`

### 9a. ResearchAgent (`research_agent.py`)

- **Pattern:** ReAct (Reason + Act) — the LLM alternates between thinking and executing tools
- **Reference:** "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022)

**Loop:**

```
1. Send prompt to LLM → it outputs Thought + Action + Action Input
2. Parse the output with regex
3. If action is "finish" → return the answer
4. Otherwise, execute the tool → get observation
5. Append the step to the prompt → go back to step 1
6. Max 6 iterations — if not finished, force a synthesis step
```

**Configuration:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| Max iterations | 6 | Prevents runaway loops |
| Reasoning temperature | 0.1 | Low temperature for focused, deterministic reasoning |
| Synthesis temperature | 0.2 | Slightly higher for natural language generation |
| Reasoning max tokens | 1024 | Sufficient for Thought + Action + Action Input |
| Synthesis max tokens | 2048 | Larger for comprehensive final answers |
| Observation truncation | 1500 chars | Prevents context overflow per step |
| Conversation history | Last 4 messages | Provides conversational context from chat |

**Parsing:** Uses regex to extract Thought, Action, and Action Input from LLM output. Tool dispatch via `_tool_map` dictionary mapping action names to functions.

**Forced synthesis:** If the agent doesn't call `finish` within 6 iterations, a forced synthesis step appends "I have gathered enough information" and generates the final answer.

### 9b. AgentTools (`tools.py`)

**5 tools** the agent can call autonomously:

| Tool | What it does internally |
|------|------------------------|
| `search_text(query, source_file)` | Calls Retriever with `filter_type="text"`, top_k=5. If no results, falls back to searching all types. Returns formatted results with citations. |
| `search_tables(query, source_file)` | Calls Retriever with `filter_type="table"`, top_k=5. Returns table markdown with citations. |
| `search_figures(query, source_file)` | Calls Retriever with `filter_type="figure"`, top_k=5. Returns figure descriptions with image paths. |
| `search_equations(query, source_file)` | Calls Retriever with `filter_type="equation"`, top_k=5. Returns LaTeX source and explanations. |
| `get_paper_list()` | Queries DocumentStore for all completed documents, returns names + page/chunk counts. No vector search needed. |

**Citation format in tool output:** `[{source_file}, p.{page_number}, §{section_heading}] (score={score:.2f})`

**Fallback behavior:** If a typed search (e.g., search_tables) returns no results, it automatically retries without the type filter to search across all content types.

---

## 10. Complete Request Flow

### Single Query Flow (POST /api/query):

```
User types question in Streamlit
  → Streamlit sends POST /api/query {question, top_k, filter_source} to FastAPI
    → routes.py calls RAGPipeline.query(question, top_k, filter_source)
      → Retriever.retrieve(question, top_k, filter_source)
        → EmbeddingService.embed_text(question)
          → all-MiniLM-L6-v2 encodes question → 384-dim float vector
        → VectorStore.search(query_embedding, top_k, filter_source)
          → ChromaDB HNSW cosine similarity search
          → Returns top-k chunks with distances
        → Filter by similarity threshold (>= 0.3)
        → Return ranked list of QueryResult objects
      → Retriever.build_context(results, max_context_length=4000)
        → Format each chunk: [Source: file, Page X, Section: heading]\ncontent\n---
        → Truncate at 4000 chars
      → Retriever.get_citations(results)
        → Extract: [{source_file, page_number, section_heading, score}, ...]
      → LLMClient.generate_with_context(QA_PROMPT, context=context, question=question)
        → QA_PROMPT.format(context=..., question=...)
        → Groq API call: llama-3.3-70b-versatile generates answer
      → Return GenerationResponse(answer, citations, query, intent, chunks_used)
    → routes.py returns JSON response
  → Streamlit displays answer with citation boxes
```

### Agent Query Flow (POST /api/agent):

```
User types question with Agent Mode ON
  → Streamlit sends POST /api/agent {question, chat_history} to FastAPI
    → routes.py calls ResearchAgent.run(question, chat_history)
      → Format last 4 chat messages as context
      → Build initial prompt from AGENT_PROMPT template
      → ITERATION 1:
        → LLMClient.generate(prompt, temperature=0.1, max_tokens=1024)
          → Groq returns: "Thought: I need to find... Action: search_text Action Input: {"query": "..."}"
        → _parse(raw) extracts thought, action, action_input via regex
        → _execute("search_text", {"query": "..."})
          → AgentTools.search_text(query="...")
            → Retriever.retrieve(query, top_k=5, filter_type="text")
              → EmbeddingService → ChromaDB → ranked results
            → Format results with citations → return observation string
        → Truncate observation to 1500 chars
        → Record AgentStep(step_number=1, thought, action, action_input, observation)
        → Append step to prompt so LLM sees its own history
      → ITERATION 2:
        → LLMClient.generate(extended_prompt, temperature=0.1)
        → ... same parse → execute → observe cycle ...
      → ITERATION N (agent calls "finish"):
        → LLM outputs: "Action: finish Action Input: {"answer": "Based on the papers..."}"
        → _parse detects action="finish"
        → Extract final answer from action_input
      → Return AgentResponse(answer, reasoning_steps[], citations, query, intent, chunks_used, total_steps)
    → routes.py returns JSON with answer + reasoning trace
  → Streamlit displays answer + expandable reasoning steps
```

### PDF Upload Flow (POST /api/upload):

```
User uploads PDF via Streamlit sidebar
  → Streamlit sends POST /api/upload (multipart file) to FastAPI
    → routes.py saves file to data/uploads/{doc_id}_{filename}
    → Creates DocumentInfo record (status="pending")
    → Spawns background thread with _ingest_lock:
      → IngestionPipeline.ingest_file(file_path, filename)
        → DocumentStore.add_document(doc) — status="processing"
        → PDFProcessor.extract(file_path) → text elements with headings
        → TableExtractor.extract(file_path) → table elements as Markdown
        → ImageExtractor.extract(file_path, doc_id) → saves images to data/images/
        → For each extracted image:
          → VisionAnalyzer.analyze(image_path) → figure description (Gemini Vision API)
          → OCRProcessor.extract_from_image(image_path) → OCR text (EasyOCR)
          → EquationExtractor.extract_from_image(image_path) → LaTeX (Gemini Vision API)
        → SemanticChunker.chunk(all_elements, source_file)
          → Text → split into 512-char chunks with 50-char overlap
          → Tables/Figures/Equations → single chunk each
          → Attach rich metadata to every chunk
        → EmbeddingService.embed_texts([chunk.content for chunk in chunks])
          → all-MiniLM-L6-v2 batch encoding → list of 384-dim vectors
        → VectorStore.add_chunks(chunks_with_embeddings)
          → ChromaDB stores IDs, vectors, content, metadata
        → DocumentStore.update_status(doc_id, "completed", total_chunks, total_pages)
    → Returns immediately with DocumentResponse(status="processing")
  → Streamlit polls GET /api/documents to check when status → "completed"
```

---

## 11. Summary Statistics

| Category | Count/Detail |
|----------|-------------|
| **Total Python files** | 21 |
| **API endpoints** | 14 (12 features + health + documents list) |
| **Data models** | 8 dataclasses |
| **Ingestion processors** | 6 (PDF, Table, Image, OCR, Vision, Equation) + 1 Chunker |
| **RAG pipeline methods** | 9 |
| **Prompt templates** | 13 |
| **Agent tools** | 5 |
| **Databases** | 2 (ChromaDB for vectors, SQLite for metadata) |
| **External APIs** | 2 (Groq for text generation, Gemini for vision) |
| **Embedding dimensions** | 384 |
| **Chunk size / overlap** | 512 / 50 characters |
| **Similarity threshold** | 0.3 |
| **Agent max iterations** | 6 |
| **Rate limit retries** | 5 with escalating backoff |
