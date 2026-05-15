# Mermaid.js Diagrams — Multimodal AI Research Assistant Report
# Tool: https://mermaid.live  →  Paste code → Download PNG → Save with the filename shown

---

## How to use
1. Open **https://mermaid.live**
2. Paste the code block for the figure you want
3. Click **Actions → Download PNG** (top-right)
4. Save the file with the **exact filename shown in the "Save as" line**
5. Put all saved PNGs into the folder:
   `/home/nst-kaja/Documents/Dorai/figures/`
6. Tell Claude "all images are in the figures folder" — the report will be rebuilt automatically

---

## Fig 1.1 — Conceptual Overview
**Save as:** `fig_1_1_overview.png`

```mermaid
graph LR
    subgraph INPUT["📄 Input"]
        A[PDF Research Papers]
    end
    subgraph PROCESS["⚙️ Multimodal Processing"]
        B1[Text Extraction]
        B2[Table Extraction]
        B3[Image Extraction]
        B4[OCR Processing]
        B5[Vision Analysis]
        B6[Equation Extraction]
    end
    subgraph STORAGE["🗄️ Knowledge Base"]
        C1[ChromaDB\nVector Store]
        C2[SQLite\nMetadata]
    end
    subgraph QUERY["🤖 AI Reasoning"]
        D1[RAG Pipeline\n9 Task Methods]
        D2[ReAct Agent\nMulti-hop Reasoning]
        D3[Humanizer\nAI Detection]
    end
    subgraph OUTPUT["💬 Output"]
        E1[Cited Answers]
        E2[Literature Survey]
        E3[Paper Comparison]
        E4[Research Gaps]
    end
    A --> B1 & B2 & B3 & B4 & B5 & B6
    B1 & B2 & B3 & B4 & B5 & B6 --> C1 & C2
    C1 --> D1 & D2
    D1 & D2 --> D3
    D3 --> E1 & E2 & E3 & E4
```

---

## Fig 2.1 — RAG Pipeline Overview
**Save as:** `fig_2_1_rag_pipeline.png`

```mermaid
flowchart LR
    Q([User Question]) --> E1[Embed Query\nall-MiniLM-L6-v2]
    E1 --> VDB[(ChromaDB\nHNSW Index)]
    VDB -->|Top-K chunks| R[Ranked Results\nwith scores]
    R --> CTX[Build Context\nwith Citations]
    CTX --> PROMPT[Inject into\nPrompt Template]
    PROMPT --> LLM[Groq LLM\nLlama 3.3 70B]
    LLM --> ANS([Answer + Citations])
    style Q fill:#4472C4,color:#fff
    style ANS fill:#70AD47,color:#fff
    style LLM fill:#ED7D31,color:#fff
    style VDB fill:#7030A0,color:#fff
```

---

## Fig 2.2 — Multimodal Document Processing Taxonomy
**Save as:** `fig_2_2_taxonomy.png`

```mermaid
mindmap
  root((Multimodal\nDocument\nProcessing))
    Text
      Section Headings
      Paragraphs
      Captions
    Tables
      Structured Data
      Markdown Format
      Raw Cell Values
    Images
      Figures
      Charts
      Diagrams
      Photographs
    Equations
      LaTeX Notation
      Mathematical Symbols
      Variable Definitions
    Scanned Content
      OCR Text
      Handwriting
      Low-quality Scans
```

---

## Fig 2.3 — ReAct Agent Reasoning Loop
**Save as:** `fig_2_3_react_loop.png`

```mermaid
flowchart TD
    START([Question + Chat History]) --> THINK
    THINK[Thought\nLLM reasons about what to do next]
    THINK --> ACT
    ACT[Action\nsearch_text / search_tables\nsearch_figures / search_equations\nget_paper_list]
    ACT --> OBS[Observation\nTool returns retrieved content]
    OBS --> CHECK{Reached finish\nor max iterations?}
    CHECK -->|No — continue| THINK
    CHECK -->|Yes — done| FINAL([Final Answer\n+ Reasoning Trace + Citations])
    style START fill:#4472C4,color:#fff
    style FINAL fill:#70AD47,color:#fff
    style THINK fill:#FFD966
    style ACT fill:#F4B183
    style OBS fill:#C9E0F5
```

---

## Fig 4.1 — High-Level System Architecture
**Save as:** `fig_4_1_architecture.png`

```mermaid
graph TB
    subgraph FE["Frontend — Next.js 15 + React 19 (Port 3000)"]
        UI1[Search Page]
        UI2[Compare Page]
        UI3[Survey Page]
        UI4[Humanizer Page]
        UI5[Trends Page]
    end
    subgraph BE["Backend — FastAPI + Uvicorn (Port 8000)"]
        API[API Layer\n14 REST endpoints]
        ING[Ingestion Layer\n6 processors + chunker]
        RAG[RAG Pipeline\n9 task methods]
        AGT[ReAct Agent\nTool loop]
        HUM[Humanizer\nAI detection]
        STR[Storage Layer\nEmbedding + Vector + Metadata]
    end
    subgraph DATA["Data Layer"]
        CDB[(ChromaDB\nHNSW vectors)]
        SDB[(SQLite\nMetadata)]
        DSK[/Disk Storage\nPDFs + Images/]
    end
    subgraph EXT["External APIs"]
        GROQ[Groq API\nLlama 3.3 70B]
        GEM[Gemini 2.0 Flash\nVision + LaTeX]
    end
    FE <-->|HTTP/JSON| API
    API --> ING & RAG & AGT & HUM
    ING & RAG & AGT --> STR
    STR <--> CDB & SDB & DSK
    RAG & AGT & ING --> GROQ & GEM
```

---

## Fig 4.2 — Six-Stage PDF Ingestion Pipeline
**Save as:** `fig_4_2_ingestion.png`

```mermaid
flowchart TD
    PDF([PDF Upload]) --> P1
    P1["1 PDFProcessor\nPyMuPDF\ntext + heading detection\nfont >= 14pt or keyword"]
    P1 --> P2["2 TableExtractor\npdfplumber\nborder detection\nMarkdown conversion"]
    P2 --> P3["3 ImageExtractor\nPyMuPDF\nsave PNG/JPEG\nfilter smaller than 50x50px"]
    P3 --> P4["4 OCRProcessor\nEasyOCR\nscanned text\nconfidence score"]
    P4 --> P5["5 VisionAnalyzer\nGemini 2.0 Flash\nfigure descriptions\n4s rate limit"]
    P5 --> P6["6 EquationExtractor\nGemini Vision\nimage to LaTeX\n+ explanation"]
    P6 --> P7["7 SemanticChunker\ntext: 512 chars 50 overlap\ntables/figs/eqs: single chunk\nUUID4 per chunk"]
    P7 --> P8["EmbeddingService\nall-MiniLM-L6-v2\nbatch=32, 384-dim\nL2-normalised"]
    P8 --> OUT([ChromaDB + SQLite\nstatus = completed])
    style PDF fill:#4472C4,color:#fff
    style OUT fill:#70AD47,color:#fff
```

---

## Fig 4.4 — Nine-Method RAG Pipeline
**Save as:** `fig_4_4_rag_methods.png`

```mermaid
graph LR
    Q([User Request]) --> RM[RAGPipeline\nMethod Router]
    RM --> M1["query()\nTop-10, 4000 chars"]
    RM --> M2["summarize()\nTop-20, 6000 chars"]
    RM --> M3["compare()\nTop-15x2, 3000x2 chars"]
    RM --> M4["literature_survey()\nTop-30, 8000 chars"]
    RM --> M5["identify_gaps()\n3 queries, 6000 chars"]
    RM --> M6["explain()\nTop-12, 5000 chars"]
    RM --> M7["recommend()\nTop-20, 6000 chars"]
    RM --> M8["analyze_trends()\n3 queries, 8000 chars"]
    RM --> M9["multi_doc_query()\nTop-20, 7000 chars"]
    M1 & M2 & M3 & M4 & M5 & M6 & M7 & M8 & M9 --> LLM[Groq LLM\nLlama 3.3 70B]
    LLM --> R([Answer + Citations])
    style Q fill:#4472C4,color:#fff
    style R fill:#70AD47,color:#fff
    style LLM fill:#ED7D31,color:#fff
```

---

## Fig 4.5 — ReAct Agent Iteration Flow
**Save as:** `fig_4_5_agent_flow.png`

```mermaid
flowchart TD
    INIT(["Start: Question\nmax_iterations = 10"]) --> LLM
    subgraph LOOP["Iteration Loop"]
        LLM["LLM Call\nGroq + tool_schemas\ntemperature=0.1"]
        LLM --> CHECK{tool_calls\nin response?}
        CHECK -->|Yes| PARSE["Parse Action\n+ Action Input JSON"]
        PARSE --> EXEC["Execute Tool\nsearch_text / search_tables\nsearch_figures / get_paper_list"]
        EXEC --> OBS["Record Observation\ntruncated to 1500 chars"]
        OBS --> APPEND["Append to\nWorking Memory Prompt"]
        APPEND --> INC{iteration < 10?}
        INC -->|Yes| LLM
    end
    CHECK -->|No — plain text| DONE
    INC -->|No — max reached| DONE
    DONE(["AgentResponse\nanswer + reasoning_steps\n+ citations"])
    style INIT fill:#4472C4,color:#fff
    style DONE fill:#70AD47,color:#fff
    style LLM fill:#ED7D31,color:#fff
    style EXEC fill:#F4B183
```

---

## Fig 4.6 — REST API Endpoint Structure
**Save as:** `fig_4_6_api.png`

```mermaid
graph LR
    FE[Frontend\nNext.js] -->|POST| A1["/api/upload\nAsync PDF ingestion"]
    FE -->|GET| A2["/api/documents\nList all papers"]
    FE -->|DELETE| A3["/api/documents/id\nRemove paper"]
    FE -->|POST| A4["/api/query\nSingle-shot RAG"]
    FE -->|POST| A5["/api/agent\nReAct multi-hop"]
    FE -->|POST| A6["/api/summarize"]
    FE -->|POST| A7["/api/compare"]
    FE -->|POST| A8["/api/literature-survey"]
    FE -->|POST| A9["/api/research-gaps"]
    FE -->|POST| A10["/api/explain"]
    FE -->|POST| A11["/api/recommend"]
    FE -->|POST| A12["/api/trends"]
    FE -->|POST| A13["/api/detect-ai"]
    FE -->|POST| A14["/api/humanize"]
```

---

## Fig 4.7 — Frontend Component Hierarchy
**Save as:** `fig_4_7_frontend.png`

```mermaid
graph TD
    APP[Next.js App Router] --> LAYOUT[RootLayout\nNavSidebar + ModelSettings drawer]
    LAYOUT --> P1[Search Page /]
    LAYOUT --> P2[Compare Page /compare]
    LAYOUT --> P3[Survey Page /survey]
    LAYOUT --> P4[Humanizer Page /humanizer]
    LAYOUT --> P5[Trends Page /trends]
    P1 --> C1[ChatInterface]
    P1 --> C2[DocumentSelector]
    P1 --> C3[ModeToggle RAG/Agent]
    C1 --> C4[MessageList]
    C1 --> C5[TextInput + Submit]
    C4 --> C6[MarkdownRenderer]
    C4 --> C7[KaTeX Math Renderer]
    C4 --> C8[CitationPanel]
    P2 --> C9[PaperDropdown x2]
    P4 --> C10[AIScoreGauge]
    P4 --> C11[HumanizedOutput]
```

---

## Fig 5.1 — PDF Heading Detection Logic
**Save as:** `fig_5_1_heading_detection.png`

```mermaid
flowchart TD
    BLOCK([Text Block from PyMuPDF]) --> FS{Font size >= 14pt?}
    FS -->|Yes| HEADING[SECTION HEADING]
    FS -->|No| KW{Matches keyword?\nIntroduction / Methodology\nResults / Conclusion / Abstract}
    KW -->|Yes| HEADING
    KW -->|No| NUM{Numbered heading?\n1. Intro / 2.1 Method}
    NUM -->|Yes| HEADING
    NUM -->|No| BODY[BODY TEXT]
    HEADING --> UPDATE[Update current_section_heading]
    BODY --> ASSIGN[Assign current_section_heading\nto element metadata]
    UPDATE --> ASSIGN
    ASSIGN --> ELEM([ExtractedElement\nelement_type=text\npage_number + section_heading])
    style HEADING fill:#70AD47,color:#fff
    style BODY fill:#4472C4,color:#fff
    style ELEM fill:#ED7D31,color:#fff
```

---

## Fig 5.2 — Type-Aware Chunking Strategy
**Save as:** `fig_5_2_chunking.png`

```mermaid
flowchart TD
    ELEM([ExtractedElement]) --> TYPE{Content Type?}
    TYPE -->|text| TEXT["RecursiveCharacterTextSplitter\nchunk_size=512, overlap=50\nparagraph > line > sentence > word"]
    TEXT --> MULTI[Multiple Chunks with UUID4 IDs]
    TYPE -->|table| TABLE["Single Chunk\nFull Markdown table\nraw cell data in metadata"]
    TABLE --> S1[One Chunk + UUID4]
    TYPE -->|figure| FIG["Single Chunk\nGemini description\nimage_path in metadata"]
    FIG --> S2[One Chunk + UUID4]
    TYPE -->|equation| EQN["Single Chunk\nLaTeX source\nexplanation in metadata"]
    EQN --> S3[One Chunk + UUID4]
    MULTI & S1 & S2 & S3 --> STORE([EmbeddingService\nChromaDB upsert])
    style ELEM fill:#4472C4,color:#fff
    style STORE fill:#70AD47,color:#fff
```

---

## Fig 5.4 — Retrieval Flow
**Save as:** `fig_5_4_retrieval.png`

```mermaid
flowchart LR
    Q([User Query]) --> EMB[EmbeddingService\nall-MiniLM-L6-v2\n384-dim vector]
    EMB --> FILTER{Optional Filters?}
    FILTER -->|source_file| SF[Filter: source_file = X]
    FILTER -->|element_type| ET[Filter: type = text/table/fig/eq]
    FILTER -->|none| BROAD[Broad Search\nAll documents]
    SF & ET & BROAD --> CHROMA[(ChromaDB\nHNSW cosine search\ntop_k nearest)]
    CHROMA --> DIST["Distance to Similarity\n1.0 minus dist/2.0"]
    DIST --> THRESH{similarity >= 0.3?}
    THRESH -->|Yes| KEEP[Include in results]
    THRESH -->|No| DROP[Discard]
    KEEP --> RANK[Rank by similarity]
    RANK --> CITE[Build context string\nwith citations]
    CITE --> OUT([Ranked QueryResult list\nchunk + score + rank])
    style Q fill:#4472C4,color:#fff
    style OUT fill:#70AD47,color:#fff
    style CHROMA fill:#7030A0,color:#fff
```

---

## Fig 5.5 — Agent Multi-Hop Reasoning Trace
**Save as:** `fig_5_5_agent_trace.png`

```mermaid
sequenceDiagram
    participant U as User
    participant A as ResearchAgent
    participant L as Groq LLM
    participant T as AgentTools
    U->>A: Compare BERT and GPT attention mechanisms
    A->>L: Prompt + tool_schemas (iteration 1)
    L-->>A: Action: get_paper_list
    A->>T: get_paper_list()
    T-->>A: bert_paper.pdf, gpt_survey.pdf
    A->>L: Prompt + observation (iteration 2)
    L-->>A: Action: search_text(attention mechanism, bert_paper.pdf)
    A->>T: search_text(...)
    T-->>A: Chunks about multi-head self-attention
    A->>L: Prompt + observation (iteration 3)
    L-->>A: Action: search_tables(GLUE benchmark results)
    A->>T: search_tables(...)
    T-->>A: BERT=82.1, GPT=78.3 on GLUE
    A->>L: Prompt + observation (iteration 4)
    L-->>A: Final Answer with citations
    A-->>U: AgentResponse (4 steps)
```

---

## Fig 5.6 — Humanizer Engine Loop
**Save as:** `fig_5_6_humanizer.png`

```mermaid
flowchart TD
    IN([AI-Generated Text]) --> DETECT
    subgraph LOOP["Refinement Loop — max 3 passes"]
        DETECT["Hybrid AI Detection\nRoBERTa score 0-100%\nBurstiness = sigma divided by mu\nTTR = unique words divided by total words\nHuman markers density"]
        DETECT --> BLEND["Blend Scores\nfinal = 0.6 x RoBERTa + 0.4 x heuristic"]
        BLEND --> CHECK{AI score < 20%?}
        CHECK -->|Yes| DONE
        CHECK -->|No and passes < 3| REWRITE["Gemini Rewrite\nVary sentence length\nAdd contractions\nUse em-dashes\nHuman transitions"]
        REWRITE --> DETECT
        CHECK -->|No but pass = 3| DONE
    end
    DONE(["HumanizationResponse\noriginal + humanized text\nchanges made + metrics"])
    style IN fill:#C00000,color:#fff
    style DONE fill:#70AD47,color:#fff
    style REWRITE fill:#ED7D31,color:#fff
```

---

## Summary — All 15 filenames to save

| Figure | Save as |
|--------|---------|
| Fig 1.1 | `fig_1_1_overview.png` |
| Fig 2.1 | `fig_2_1_rag_pipeline.png` |
| Fig 2.2 | `fig_2_2_taxonomy.png` |
| Fig 2.3 | `fig_2_3_react_loop.png` |
| Fig 4.1 | `fig_4_1_architecture.png` |
| Fig 4.2 | `fig_4_2_ingestion.png` |
| Fig 4.4 | `fig_4_4_rag_methods.png` |
| Fig 4.5 | `fig_4_5_agent_flow.png` |
| Fig 4.6 | `fig_4_6_api.png` |
| Fig 4.7 | `fig_4_7_frontend.png` |
| Fig 5.1 | `fig_5_1_heading_detection.png` |
| Fig 5.2 | `fig_5_2_chunking.png` |
| Fig 5.4 | `fig_5_4_retrieval.png` |
| Fig 5.5 | `fig_5_5_agent_trace.png` |
| Fig 5.6 | `fig_5_6_humanizer.png` |
