# 🔬 Multimodal AI Research Assistant

> RAG-powered research paper analysis with multimodal understanding, agent-based reasoning, and intelligent Q&A.

## ✨ Features

- **PDF Ingestion** — Upload research papers and extract structured text with section detection
- **Semantic Search** — Find relevant content using dense vector embeddings
- **Question Answering** — Ask questions and get answers with citations
- **Document Summarization** — Summarize entire papers or specific sections
- **Chat Interface** — Beautiful Streamlit UI with document management

## 🏗️ Architecture

```
Input Layer → Multimodal Processing → Knowledge Chunks → Vector DB
    ↓                                                        ↓
Chat UI ← LLM Generation ← RAG Pipeline ← Semantic Search ←┘
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Gemini API key
# Get one free at: https://aistudio.google.com/apikey
```

### 3. Run the Application

```bash
# Terminal 1: Start the API server
source venv/bin/activate
python -m src.main

# Terminal 2: Start the Streamlit UI
source venv/bin/activate
streamlit run src/ui/app.py
```

### 4. Use the App

1. Open http://localhost:8501 in your browser
2. Upload a PDF research paper via the sidebar
3. Ask questions in the chat interface
4. Get answers with citations!

## 📁 Project Structure

```
src/
├── main.py                    # FastAPI entry point
├── config.py                  # Configuration management
├── models/
│   └── schemas.py             # Data models (Chunk, Document, etc.)
├── ingestion/
│   ├── pdf_processor.py       # PDF text extraction (PyMuPDF)
│   ├── chunker.py             # Semantic text chunking
│   └── pipeline.py            # End-to-end ingestion pipeline
├── storage/
│   ├── embedding_service.py   # Sentence-transformer embeddings
│   ├── vector_store.py        # ChromaDB vector storage
│   └── document_store.py      # SQLite metadata store
├── retrieval/
│   ├── retriever.py           # Semantic search retriever
│   └── rag_pipeline.py        # Full RAG pipeline (retrieve + generate)
├── generation/
│   ├── llm_client.py          # Google Gemini LLM client
│   └── prompts.py             # Prompt templates
├── api/
│   └── routes.py              # FastAPI REST endpoints
└── ui/
    └── app.py                 # Streamlit chat interface
```

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI |
| LLM | Google Gemini 1.5 Flash |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | ChromaDB |
| PDF Processing | PyMuPDF |
| Chunking | LangChain Text Splitters |
| Frontend | Streamlit |
| Metadata DB | SQLite |

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/upload` | Upload and ingest a PDF |
| POST | `/api/query` | Ask a question (RAG) |
| POST | `/api/summarize` | Summarize a document |
| GET | `/api/documents` | List all documents |
| DELETE | `/api/documents/{id}` | Delete a document |
| GET | `/api/health` | Health check |

## 🗺️ Roadmap

- [x] **Phase 1**: Basic RAG with PDF ingestion & QA
- [ ] **Phase 2**: Multimodal support (tables, images, OCR, equations)
- [ ] **Phase 3**: Agent-based reasoning (LangGraph)
- [ ] **Phase 4**: Advanced features (comparison, graph reasoning)
- [ ] **Phase 5**: Optimization & scaling

## 📄 License

MIT