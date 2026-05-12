# Multimodal AI Research Assistant

> An intelligent research assistant that combines **Multimodal RAG**, **Agentic Reasoning**, and **Semantic Search** to help users understand, analyse, and synthesise complex scientific documents.

---

## Project Overview

This system analyses research papers containing text, images, tables, and equations. It uses computer vision, natural language processing, and retrieval-augmented generation to retrieve relevant information and generate accurate, context-aware answers.

Unlike traditional RAG systems that only process text, this system supports **multimodal inputs**, **agent-based multi-hop reasoning**, and **advanced text humanization** to provide a complete research workflow.

### Major Area
Artificial Intelligence (Multimodal AI and Agentic Systems)

### Minor Areas
- Natural Language Processing (NLP)
- Computer Vision (CV)
- Information Retrieval (IR)
- Text Humanization & AI Detection

### Key Concepts
- **Multimodal RAG**: Seamlessly integrates tables, figures, and text.
- **Agentic AI**: Uses the ReAct (Reason + Act) pattern for autonomous planning.
- **Human-in-the-Loop**: Advanced humanizer to refine AI outputs for academic standards.
- **Semantic Search**: High-performance vector search via ChromaDB.

---

## Features (22 Key Capabilities)

| #  | Feature                                   | Implementation                                   |
| -- | ----------------------------------------- | ------------------------------------------------ |
| 1  | Research paper upload and processing      | FastAPI async upload + background ingestion      |
| 2  | Text, image, table, and chart extraction  | PyMuPDF, pdfplumber, image extraction            |
| 3  | Multimodal document understanding         | Gemini Vision, EasyOCR, LaTeX extraction         |
| 4  | Multimodal RAG                            | ChromaDB + Gemini/Groq context injection         |
| 5  | **Humanizer Engine**                      | **Iterative refinement with AI detection scoring**|
| 6  | **AI Detection**                          | **RoBERTa-based detector + heuristic metrics**    |
| 7  | **Integrated Image Display**              | **Figures/Charts rendered directly in chat/summaries**|
| 8  | Agent-based reasoning and planning        | ReAct agent with Thought/Action/Observation loop |
| 9  | Question answering from research papers   | Single-shot RAG with citation tracking           |
| 10 | Research paper summarization              | Broad retrieval + multi-modal synthesis          |
| 11 | Research paper comparison                 | Side-by-side retrieval from multiple papers       |
| 12 | Table and chart question answering        | Typed retrieval filtering by content type        |
| 13 | Literature survey generation              | Multi-paper retrieval + structured survey        |
| 14 | Research gap identification               | Targeted retrieval (limitations, future work)    |
| 15 | Semantic search across research papers    | Dense vector search via ChromaDB                 |
| 16 | Technical concept explanation             | Concept-targeted retrieval + explanation prompt  |
| 17 | Diagram and table explanation             | Figure/table content retrieval + vision analysis |
| 18 | Multi-document reasoning                  | Cross-paper retrieval + synthesis prompt         |
| 19 | Multi-hop retrieval                       | ReAct agent with iterative search refinement     |
| 20 | Citation-based answering                  | Source file + page number in every response      |
| 21 | Related paper recommendation              | Interest-based retrieval + recommendation prompt |
| 22 | Research trend analysis                   | Multi-query retrieval + trend analysis prompt    |

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
 ├─► RAG Pipeline: embed → search → build context → generate      │
 │                                                                │
 ├─► ReAct Agent: Think → Act (Tools) → Observe → Finish          │
 │                                                                │
 └─► Humanizer: AI Detection → Iterative Rewriting → Final Answer │
      │                                                           │
      ▼                                                           │
 Groq/Gemini LLM → Multimodal Answer (Text + Images) → Next.js UI │
 ──────────────────────────────────────────────────────────────────
```

---

## Core Components

### 1. Document Processing Module
Extracts structured content from PDFs using multiple specialised processors.

| Processor             | Library        | Purpose                                                                      |
| --------------------- | -------------- | ---------------------------------------------------------------------------- |
| `PDFProcessor`      | PyMuPDF (fitz) | Text extraction with heading detection (font size >= 14pt, keyword matching) |
| `TableExtractor`    | pdfplumber     | Table extraction → Markdown format with raw data preservation               |
| `ImageExtractor`    | PyMuPDF        | Image extraction and saving (format:`{doc_id}_p{page}_img{idx}.{ext}`)     |
| `OCRProcessor`      | EasyOCR        | Optical character recognition for scanned/handwritten content                |
| `VisionAnalyzer`    | Gemini Vision  | AI-powered description of figures, diagrams, and charts                      |
| `EquationExtractor` | Gemini Vision  | Equation image → LaTeX conversion with explanation                          |

### 2. Humanizer Engine (`humanizer.py`)
A unique feature that ensures AI-generated content sounds natural and passes academic standards.
- **Detection**: Uses a hybrid approach combining **RoBERTa (base-openai-detector)** and heuristic metrics (Burstiness, TTR).
- **Refinement**: Iteratively rewrites text using Gemini with aggressive "human-like" prompts until the AI score drops below **20%**.
- **Metrics**: Tracks sentence length variance, lexical diversity, and human markers (em-dashes, parentheticals).

### 3. Chunking Algorithm
Uses LangChain's `RecursiveCharacterTextSplitter` for semantic chunking.

| Parameter     | Value                             | Description                                                        |
| ------------- | --------------------------------- | ------------------------------------------------------------------ |
| Chunk size    | 512 characters                    | Maximum size of each text chunk                                    |
| Chunk overlap | 50 characters                     | Overlap between consecutive chunks for context continuity          |
| Separators    | `["\n\n", "\n", ". ", " ", ""]` | Split priority: paragraph → line → sentence → word → character |

**Chunking strategy by content type:**
- **Text**: Recursively split at natural boundaries using the separator hierarchy.
- **Tables**: Kept as single chunks (entire table = one chunk) with raw data in metadata.
- **Figures**: Kept as single chunks with image path and description in metadata.
- **Equations**: Kept as single chunks with LaTeX source in metadata.

### 4. Embedding and Storage

| Component            | Technology                        | Details                                                                 |
| -------------------- | --------------------------------- | ----------------------------------------------------------------------- |
| Embedding model      | `all-MiniLM-L6-v2`              | Sentence-transformer, 384-dimensional vectors, normalised embeddings    |
| Vector database      | ChromaDB                          | Persistent storage, HNSW index, cosine distance metric                  |
| Metadata store       | SQLite                            | Document lifecycle tracking (pending → processing → completed/failed) |
| Similarity score     | `1.0 - (cosine_distance / 2.0)` | Converted from ChromaDB distance to 0-1 similarity                      |
| Similarity threshold | 0.3                               | Minimum relevance score to include in results                           |

### 5. RAG Pipeline
Nine specialised pipeline methods, each with tailored retrieval strategies and prompt templates:

| Method                  | Retrieval Strategy                                                     | Max Context          | Prompt                     |
| ----------------------- | ---------------------------------------------------------------------- | -------------------- | -------------------------- |
| `query()`             | Single query, top-10                                                   | 4000 chars           | QA_PROMPT                  |
| `summarize()`         | Broad query ("contributions methodology results"), top-20              | 6000 chars           | SUMMARIZE_PROMPT           |
| `compare()`           | Separate retrieval per paper, top-15 each                              | 3000 chars per paper | COMPARE_PAPERS_PROMPT      |
| `literature_survey()` | Topic-based or broad, top-30                                           | 8000 chars           | LITERATURE_SURVEY_PROMPT   |
| `identify_gaps()`     | Multi-query ("limitations", "future work", "challenges"), deduplicated | 6000 chars           | RESEARCH_GAP_PROMPT        |
| `explain()`           | Concept-targeted, top-12                                               | 5000 chars           | CONCEPT_EXPLANATION_PROMPT |
| `recommend()`         | Interest-based, top-20                                                 | 6000 chars           | RECOMMENDATION_PROMPT      |
| `analyze_trends()`    | Multi-query ("methodology", "results", "datasets"), deduplicated       | 8000 chars           | TREND_ANALYSIS_PROMPT      |
| `multi_doc_query()`   | Broad cross-paper, top-20                                              | 7000 chars           | MULTI_DOC_PROMPT           |

### 6. Agentic Reasoning Module (ReAct Agent)
Implements the ReAct (Reason + Act) pattern for multi-hop question answering.
- **Tools**: `search_text`, `search_tables`, `search_figures`, `search_equations`, `get_paper_list`.
- **Reasoning Loop**: Think → Act (execute tool) → Observe (result) → Repeat until Finish.

### 7. Rate Limiting
A global thread-safe rate limiter is shared across all Gemini API calls to stay within free-tier quotas.
- **Minimum interval**: 4 seconds between calls.
- **Max retries**: 5 with escalating backoff (15s to 75s).

---

## Tech Stack

| Category       | Technology                               | Details                                      |
| -------------- | ---------------------------------------- | -------------------------------------------- |
| **Frontend**   | **Next.js 15 + Tailwind CSS**           | Modern, responsive React-based UI            |
| **Backend**    | FastAPI + Uvicorn                        | High-performance async Python API            |
| **LLMs**       | **Groq (Llama 3.3)** + **Gemini 2.0**    | Groq for speed, Gemini for Vision tasks      |
| **AI Detection**| **RoBERTa (openai-detector)** + Torch    | Blended detection logic in Humanizer         |
| **Vector DB**  | ChromaDB                                 | Persistent vector storage with HNSW index    |
| **Embeddings** | all-MiniLM-L6-v2                         | 384-dimensional semantic vectors             |
| **Processing** | PyMuPDF, pdfplumber, EasyOCR             | Advanced PDF and Image extraction libraries |

---

## Project Structure

```
Multimodal-AI-Research-Assistant/
├── frontend/                       # Next.js Frontend (React)
│   ├── app/                        # Pages and layouts
│   ├── components/                 # UI Components
│   └── lib/                        # API clients and types
│
├── src/
│   ├── main.py                     # FastAPI Entry Point
│   ├── ingestion/                  # PDF & Multimodal processing
│   │   ├── pdf_processor.py        # Text & Heading extraction
│   │   ├── table_extractor.py      # Markdown table conversion
│   │   ├── image_extractor.py      # Image extraction
│   │   ├── vision_analyzer.py      # Gemini Vision integration
│   │   └── chunker.py              # Semantic splitting logic
│   ├── generation/
│   │   ├── humanizer.py            # AI Detection & Text Refinement
│   │   ├── llm_client.py           # Multi-LLM provider interface
│   │   └── prompts.py              # Structured prompt templates
│   ├── agents/
│   │   └── research_agent.py       # ReAct agent implementation
│   ├── retrieval/
│   │   └── rag_pipeline.py         # 9+ RAG capability methods
│   └── storage/
│       ├── vector_store.py         # ChromaDB interface
│       └── document_store.py       # SQLite metadata management
│
├── data/                           # Local data (uploads, images, db)
├── EVALUATION_METRICS.md           # Comprehensive evaluation guide
└── PROJECT_EVALUATION_PLAN.md      # RAG Triad and performance plan
```

---

## API Endpoints

| Method     | Endpoint                   | Description                                           |
| ---------- | -------------------------- | ----------------------------------------------------- |
| `POST`   | `/api/upload`            | Upload and ingest a PDF (async background processing) |
| `POST`   | `/api/query`             | Single-shot RAG question answering                    |
| `POST`   | `/api/agent`             | Multi-hop agentic question answering (ReAct)          |
| `POST`   | `/api/summarize`         | Summarize one or all papers                           |
| `POST`   | `/api/compare`           | Compare two papers side-by-side                       |
| `POST`   | `/api/literature-survey` | Generate a literature survey                          |
| `POST`   | `/api/research-gaps`     | Identify research gaps and future directions          |
| `POST`   | `/api/explain`           | Explain a concept, diagram, or table                  |
| `POST`   | `/api/recommend`         | Recommend papers for a research interest              |
| `POST`   | `/api/trends`            | Analyse research trends across papers                 |
| `POST`   | `/api/multi-doc`         | Multi-document reasoning                              |
| `GET`    | `/api/documents`         | List all ingested documents                           |
| `DELETE` | `/api/documents/{id}`    | Delete a document and its chunks                      |

---

## Quick Start

### Prerequisites
- Python 3.10+
- Google Gemini API key
- Groq API key

### 1. Setup
```bash
git clone <repo-url>
pip install -r requirements.txt
```

### 2. Configure
Add your API keys to the `.env` file:
```env
GEMINI_API_KEY=your_key
GROQ_API_KEY=your_key
```

### 3. Run
**Backend:** `python -m src.main`
**Frontend:** `cd frontend && npm install && npm run dev`

---

## Evaluation Strategy
The project follows a rigorous evaluation plan documented in `PROJECT_EVALUATION_PLAN.md`:
- **RAG Triad**: Context Relevance, Faithfulness, and Answer Relevance.
- **Multimodal Metrics**: OCR (CER), Table Detection, and LaTeX Accuracy.
- **Frameworks**: RAGAs, DeepEval, and TruLens for automated scoring.

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
