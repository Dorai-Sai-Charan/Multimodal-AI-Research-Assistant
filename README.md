# Multimodal AI Research Assistant

> An intelligent research assistant that combines **Multimodal RAG**, **Agentic Reasoning**, and **Semantic Search** to help users understand, analyse, and synthesise complex scientific documents.

---

## Project Overview

This system analyses research papers containing text, images, tables, and equations. It uses computer vision, natural language processing, and retrieval-augmented generation to retrieve relevant information and generate accurate, context-aware answers.

Unlike traditional RAG systems that only process text, this system supports **multimodal inputs** and **agent-based multi-hop reasoning** to improve understanding, retrieval, and explanation of scientific documents.

### Major Area

Artificial Intelligence (Multimodal AI and Agentic Systems)

### Minor Areas

- Natural Language Processing
- Computer Vision
- Information Retrieval
- Machine Learning and Deep Learning

### Key Concepts

- Multimodal Retrieval-Augmented Generation (RAG)
- Agentic AI (planning, reasoning, tool use)
- ReAct (Reason + Act) agent pattern
- Vision-language models
- Vector databases and semantic search
- Multi-hop reasoning

---

## Features (20 Capabilities)

| # | Feature | Implementation |
|---|---------|---------------|
| 1 | Research paper upload and processing | FastAPI async upload + background ingestion |
| 2 | Text, image, table, and chart extraction | PyMuPDF, pdfplumber, image extraction |
| 3 | Multimodal document understanding | Gemini Vision, EasyOCR, LaTeX extraction |
| 4 | Multimodal Retrieval-Augmented Generation | ChromaDB + Gemini LLM with context injection |
| 5 | Agent-based reasoning and task planning | ReAct agent with Thought/Action/Observation loop |
| 6 | Question answering from research papers | Single-shot RAG with citation tracking |
| 7 | Research paper summarization | Broad retrieval + summarization prompt |
| 8 | Research paper comparison | Side-by-side retrieval from two papers |
| 9 | Table and chart question answering | Typed retrieval filtering by content type |
| 10 | Literature survey generation | Multi-paper retrieval + survey prompt |
| 11 | Research gap identification | Targeted retrieval (limitations, future work) |
| 12 | Semantic search across research papers | Dense vector search via ChromaDB |
| 13 | Technical concept explanation | Concept-targeted retrieval + explanation prompt |
| 14 | Diagram and table explanation | Figure/table content retrieval + explanation |
| 15 | Multi-document reasoning | Cross-paper retrieval + synthesis prompt |
| 16 | Multi-hop retrieval | ReAct agent with iterative search refinement |
| 17 | Citation-based answering | Source file + page number in every response |
| 18 | Related paper recommendation | Interest-based retrieval + recommendation prompt |
| 19 | Research trend analysis | Multi-query retrieval + trend analysis prompt |
| 20 | Conversational research assistant | Chat history passed to agent for context |

---

## System Architecture

```
                           INGESTION PIPELINE
 PDF Upload ──────────────────────────────────────────────────────
 │                                                                │
 ├─► PDFProcessor         (PyMuPDF: text + heading detection)     │
 ├─► TableExtractor       (pdfplumber: tables → Markdown)         │
 ├─► ImageExtractor       (PyMuPDF: save images to disk)          │
 ├─► OCRProcessor         (EasyOCR: scanned/handwritten text)     │
 ├─► VisionAnalyzer       (Gemini Vision: figure descriptions)    │
 └─► EquationExtractor    (Gemini Vision: image → LaTeX)          │
      │                                                           │
      ▼                                                           │
 SemanticChunker (RecursiveCharacterTextSplitter)                 │
      │                                                           │
      ▼                                                           │
 EmbeddingService (all-MiniLM-L6-v2, 384 dimensions)             │
      │                                                           │
      ▼                                                           │
 ChromaDB (cosine similarity) + SQLite (metadata)                 │
──────────────────────────────────────────────────────────────────

                          QUERY PIPELINE
 User Question ───────────────────────────────────────────────────
 │                                                                │
 ├─► Single-shot RAG: embed → search → build context → generate   │
 │                                                                │
 └─► ReAct Agent (multi-hop):                                     │
      │  THINK: decompose question                                │
      │  ACT:   call tool (search_text / search_tables / ...)     │
      │  OBSERVE: evaluate retrieved chunks                       │
      │  REPEAT until confident                                   │
      │  FINISH: synthesise final answer                          │
      │                                                           │
      ▼                                                           │
 Gemini LLM → Answer + Citations → Streamlit UI                  │
──────────────────────────────────────────────────────────────────
```

---

## Core Components

### 1. Document Processing Module

Extracts structured content from PDFs using multiple specialised processors.

| Processor | Library | Purpose |
|-----------|---------|---------|
| `PDFProcessor` | PyMuPDF (fitz) | Text extraction with heading detection (font size >= 14pt, keyword matching) |
| `TableExtractor` | pdfplumber | Table extraction → Markdown format with raw data preservation |
| `ImageExtractor` | PyMuPDF | Image extraction and saving (format: `{doc_id}_p{page}_img{idx}.{ext}`) |
| `OCRProcessor` | EasyOCR | Optical character recognition for scanned/handwritten content |
| `VisionAnalyzer` | Gemini Vision | AI-powered description of figures, diagrams, and charts |
| `EquationExtractor` | Gemini Vision | Equation image → LaTeX conversion with explanation |

### 2. Chunking Algorithm

Uses LangChain's `RecursiveCharacterTextSplitter` for semantic chunking.

| Parameter | Value | Description |
|-----------|-------|-------------|
| Chunk size | 512 characters | Maximum size of each text chunk |
| Chunk overlap | 50 characters | Overlap between consecutive chunks for context continuity |
| Separators | `["\n\n", "\n", ". ", " ", ""]` | Split priority: paragraph → line → sentence → word → character |

**Chunking strategy by content type:**

- **Text**: Recursively split at natural boundaries using the separator hierarchy
- **Tables**: Kept as single chunks (entire table = one chunk) with raw data in metadata
- **Figures**: Kept as single chunks with image path and description in metadata
- **Equations**: Kept as single chunks with LaTeX source in metadata

Each chunk carries rich metadata: source file, page number, section heading, element type, confidence score, and content-specific data (table data, image path, LaTeX source).

### 3. Embedding and Storage

| Component | Technology | Details |
|-----------|-----------|---------|
| Embedding model | `all-MiniLM-L6-v2` | Sentence-transformer, 384-dimensional vectors, normalised embeddings |
| Vector database | ChromaDB | Persistent storage, HNSW index, cosine distance metric |
| Metadata store | SQLite | Document lifecycle tracking (pending → processing → completed/failed) |
| Similarity score | `1.0 - (cosine_distance / 2.0)` | Converted from ChromaDB distance to 0-1 similarity |
| Similarity threshold | 0.3 | Minimum relevance score to include in results |

**Singleton pattern**: The embedding model is loaded once and shared across all components to avoid redundant memory usage.

### 4. RAG Pipeline

Nine specialised pipeline methods, each with tailored retrieval strategies and prompt templates:

| Method | Retrieval Strategy | Max Context | Prompt |
|--------|-------------------|-------------|--------|
| `query()` | Single query, top-10 | 4000 chars | QA_PROMPT |
| `summarize()` | Broad query ("contributions methodology results"), top-20 | 6000 chars | SUMMARIZE_PROMPT |
| `compare()` | Separate retrieval per paper, top-15 each | 3000 chars per paper | COMPARE_PAPERS_PROMPT |
| `literature_survey()` | Topic-based or broad, top-30 | 8000 chars | LITERATURE_SURVEY_PROMPT |
| `identify_gaps()` | Multi-query ("limitations", "future work", "challenges"), deduplicated | 6000 chars | RESEARCH_GAP_PROMPT |
| `explain()` | Concept-targeted, top-12 | 5000 chars | CONCEPT_EXPLANATION_PROMPT |
| `recommend()` | Interest-based, top-20 | 6000 chars | RECOMMENDATION_PROMPT |
| `analyze_trends()` | Multi-query ("methodology", "results", "datasets"), deduplicated | 8000 chars | TREND_ANALYSIS_PROMPT |
| `multi_doc_query()` | Broad cross-paper, top-20 | 7000 chars | MULTI_DOC_PROMPT |

### 5. Agentic Reasoning Module (ReAct Agent)

Implements the ReAct (Reason + Act) pattern for multi-hop question answering.

**Agent tools:**

| Tool | Description |
|------|-------------|
| `search_text` | Search textual content, optionally filtered by paper |
| `search_tables` | Search table content with type filtering |
| `search_figures` | Search figure descriptions |
| `search_equations` | Search mathematical equations |
| `get_paper_list` | List all uploaded papers |
| `finish` | Provide the final synthesised answer |

**Agent loop:**

```
Thought: I need to find information about X     ← LLM reasons
Action: search_text                              ← LLM picks a tool
Action Input: {"query": "X"}                     ← LLM provides arguments
Observation: [retrieved chunks]                  ← System executes tool
... repeat up to 6 iterations ...
Action: finish                                   ← LLM decides to stop
Action Input: {"answer": "Final answer..."}      ← LLM synthesises
```

**Configuration:**

- Maximum iterations: 6
- LLM temperature: 0.1 (reasoning), 0.2 (final synthesis)
- Observation truncation: 1500 characters per step
- Conversation history: last 4 messages for context

### 6. Rate Limiting

A global thread-safe rate limiter is shared across all Gemini API calls (LLM generation, vision analysis, equation extraction) to stay within free-tier quotas.

| Parameter | Value |
|-----------|-------|
| Minimum interval | 4 seconds between calls |
| Max retries | 5 |
| Retry delay | 15s, 30s, 45s, 60s, 75s (escalating) |
| Model | `gemini-2.5-flash-lite` |

---

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend | FastAPI + Uvicorn | 0.115.6 |
| LLM | Google Gemini (gemini-2.5-flash-lite) | via google-genai SDK |
| Vision | Google Gemini (multimodal) | via google-genai SDK |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 3.3.1 |
| Vector DB | ChromaDB (persistent, cosine distance) | 0.6.3 |
| PDF Processing | PyMuPDF + pdfplumber | 1.25.3 / 0.11.4 |
| Chunking | LangChain Text Splitters | 0.3.4 |
| OCR | EasyOCR | 1.7.2 |
| Frontend | Streamlit | 1.41.1 |
| Metadata DB | SQLite | Built-in |
| Config | Pydantic Settings + python-dotenv | 2.7.1 |

---

## Project Structure

```
Multimodal-AI-Research-Assistant/
├── src/
│   ├── main.py                     # FastAPI entry point (Uvicorn server)
│   ├── config.py                   # Pydantic settings from .env
│   │
│   ├── models/
│   │   └── schemas.py              # Chunk, DocumentInfo, QueryResult,
│   │                               # GenerationResponse, AgentStep, AgentResponse
│   ├── ingestion/
│   │   ├── pipeline.py             # End-to-end ingestion orchestration
│   │   ├── pdf_processor.py        # Text extraction with heading detection
│   │   ├── table_extractor.py      # Table extraction → Markdown
│   │   ├── image_extractor.py      # Image extraction and saving
│   │   ├── ocr_processor.py        # EasyOCR for scanned documents
│   │   ├── vision_analyzer.py      # Gemini Vision image analysis
│   │   ├── equation_extractor.py   # Equation → LaTeX conversion
│   │   └── chunker.py              # RecursiveCharacterTextSplitter
│   │
│   ├── storage/
│   │   ├── embedding_service.py    # Singleton sentence-transformer embeddings
│   │   ├── vector_store.py         # ChromaDB CRUD + similarity search
│   │   └── document_store.py       # SQLite document metadata
│   │
│   ├── retrieval/
│   │   ├── retriever.py            # Embed query → vector search → rank
│   │   └── rag_pipeline.py         # 9 pipeline methods (QA, compare, survey, ...)
│   │
│   ├── generation/
│   │   ├── llm_client.py           # Gemini client + rate limiter + retry
│   │   └── prompts.py              # 10 prompt templates
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── research_agent.py       # ReAct agent (Thought/Action/Observation loop)
│   │   └── tools.py                # Agent tool implementations
│   │
│   ├── api/
│   │   └── routes.py               # 12 FastAPI REST endpoints
│   │
│   └── ui/
│       └── app.py                  # Streamlit UI (5 tabs, 20 features)
│
├── data/                           # Runtime data (auto-created)
│   ├── uploads/                    # Uploaded PDF files
│   ├── images/                     # Extracted images
│   ├── chroma_db/                  # ChromaDB persistent storage
│   └── documents.db                # SQLite metadata database
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload and ingest a PDF (async background processing) |
| `POST` | `/api/query` | Single-shot RAG question answering |
| `POST` | `/api/agent` | Multi-hop agentic question answering (ReAct) |
| `POST` | `/api/summarize` | Summarize one or all papers |
| `POST` | `/api/compare` | Compare two papers side-by-side |
| `POST` | `/api/literature-survey` | Generate a literature survey |
| `POST` | `/api/research-gaps` | Identify research gaps and future directions |
| `POST` | `/api/explain` | Explain a concept, diagram, or table |
| `POST` | `/api/recommend` | Recommend papers for a research interest |
| `POST` | `/api/trends` | Analyse research trends across papers |
| `POST` | `/api/multi-doc` | Multi-document reasoning |
| `GET` | `/api/documents` | List all ingested documents |
| `DELETE` | `/api/documents/{id}` | Delete a document and its chunks |
| `GET` | `/api/health` | Health check |

---

## Quick Start

### Prerequisites

- Python 3.10+
- A Google Gemini API key (free at https://aistudio.google.com/apikey)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd Multimodal-AI-Research-Assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

```bash
# Create .env from template
cp .env.example .env

# Edit .env and add your Gemini API key
# GEMINI_API_KEY=your_key_here
```

### 3. Run the Backend (Terminal 1)

```bash
source venv/bin/activate
python -m src.main
```

The FastAPI server starts on **http://localhost:8000**.
Swagger docs available at **http://localhost:8000/docs**.

### 4. Run the Frontend (Terminal 2)

```bash
source venv/bin/activate
streamlit run src/ui/app.py --server.port 8501
```

The Streamlit UI opens at **http://localhost:8501**.

### 5. Use the Application

1. **Upload** a research paper PDF via the sidebar
2. Click **Refresh** to check ingestion status (processing → completed)
3. Use the **5 tabs**:
   - **Chat Assistant** — Ask questions, toggle Agent Mode for multi-hop reasoning
   - **Compare Papers** — Upload 2+ papers and compare them
   - **Survey & Gaps** — Generate literature surveys, identify research gaps
   - **Search & Explain** — Semantic search, explain concepts/diagrams/tables
   - **Trends & Recommend** — Analyse trends, get paper recommendations

---

## Configuration

All settings are in `.env` (loaded via Pydantic Settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | (required) | Google Gemini API key |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `CHROMA_PERSIST_DIR` | `./data/chroma_db` | ChromaDB storage path |
| `UPLOAD_DIR` | `./data/uploads` | Uploaded files directory |
| `APP_HOST` | `0.0.0.0` | Server bind address |
| `APP_PORT` | `8000` | Server port |
| `LOG_LEVEL` | `info` | Logging level |

---

## Literature Survey (Referenced Papers)

- Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG
- A Multimodal Retrieval-Augmented Generation System with ReAct Agent Logic for Multi-Hop Reasoning
- CMRAG: Co-Modality-Based Visual Document Retrieval and Question Answering
- DocAgent: An Agentic Framework for Multi-Modal Long-Context Document Understanding
- KA-RAG: Integrating Knowledge Graphs and Agentic Retrieval-Augmented Generation
- MA-RAG: Multi-Agent Retrieval-Augmented Generation via Collaborative Reasoning
- MMA-RAG: A Survey on Multimodal Agentic Retrieval-Augmented Generation
- mRAG: Elucidating the Design Space of Multimodal Retrieval-Augmented Generation
- Scaling Beyond Context: A Survey of Multimodal RAG for Document Understanding
- VisRAG: Vision-Based Retrieval-Augmented Generation on Multi-Modality Documents

---

## License

MIT
