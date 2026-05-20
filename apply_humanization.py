"""Apply humanized text replacements to the report .docx file."""
from docx import Document
import copy

DOCX_PATH = "Multimodal_AI_Research_Assistant_Report.docx"
OUTPUT_PATH = "Multimodal_AI_Research_Assistant_Report_Humanized.docx"

# Map of paragraph index -> humanized replacement text
REPLACEMENTS = {
    50: "The Humanizer Engine works by blending a RoBERTa-based AI detector with three heuristic linguistic metrics — burstiness (σ/μ of sentence lengths), Type-Token Ratio, and human marker density — then iteratively rewrites text until the AI score drops below 20%. On the frontend side, the system is built on Next.js 15 with React 19, and it renders Markdown, KaTeX maths, and syntax-highlighted code without any fuss. End-to-end evaluation results are encouraging: strong retrieval precision, faithful answers with traceable citations, and effective humanization — making it a genuinely practical research toolkit for graduate students and academics.",

    151: "Retrieval-Augmented Generation (RAG) emerged as a principled way to fix this problem. Instead of leaning entirely on the model's parametric memory, RAG retrieves relevant passages from an external knowledge store at query time and injects them directly into the context window — which grounds answers in real, verifiable evidence and cuts hallucination considerably. Lewis et al. (2020) showed retrieval-augmented models outperforming purely generative ones on knowledge-intensive tasks by a wide margin, and that result essentially established RAG as the standard architecture for document-grounded QA.",

    152: "Here's the trouble, though: research documents aren't just text. Any typical ML paper is packed with tables of benchmark results, architecture diagrams, performance graphs, and LaTeX-formatted equations — and most of that gets thrown away by text-only RAG pipelines. What you end up with is a system that handles prose just fine but draws a complete blank when someone asks about the table on page 6 or the derivation buried in Section 3. Closing that gap is what motivated building a genuinely multimodal retrieval system in the first place.",

    157: "•  Text-only RAG pipelines throw away tables, figures, and equations — which are often the most information-dense parts of a research paper — and that leads directly to incomplete answers whenever someone asks a quantitative or methodology-focused question.",

    158: "•  General-purpose conversational AI simply can't reason across multiple uploaded documents simultaneously, which makes comparative analysis or cross-paper synthesis practically impossible.",

    159: "•  Multi-hop research questions — say, comparing attention mechanisms across two papers while cross-checking GLUE benchmark figures — demand iterative, tool-augmented reasoning that a standard single-shot RAG pipeline just can't deliver.",

    160: "•  AI-generated content — even when factually accurate — tends to be recognisable as machine-produced, largely because of its overly uniform sentence structure; that makes it unlikely to pass institutional AI-detection checks.",

    162: "The primary motivation here comes directly from lived experience — graduate students and researchers routinely spend a disproportionate chunk of their time just doing literature reviews. Studies in information science put that figure at roughly 23% of total working time spent searching for and reading literature. An intelligent assistant that can answer questions about uploaded papers instantly, generate structured literature surveys, flag research gaps, and untangle complex mathematical formulations? That would be a genuine productivity multiplier for the academic community.",

    163: "There's also a secondary motivation — advancing the state of the art in applied multimodal AI. Plenty of RAG implementations exist, but very few manage to combine multimodal ingestion, persistent vector storage, agentic multi-hop reasoning, and AI-detection humanization in a single integrated system. Building and evaluating something that does all four contributes original engineering insight to what is, frankly, a rapidly growing field.",

    164: "The timing also matters. High-quality free-tier APIs — Groq for ultra-fast LLM inference and Gemini 2.0 Flash for vision tasks — now exist alongside open-source vector databases like ChromaDB and embedding models like Sentence-Transformers. That convergence makes a production-quality multimodal RAG system achievable without any significant computational expenditure, which simply wasn't the case a couple of years ago.",

    172: "6. To deliver a modern, responsive web interface — built on Next.js 15 and React 19 — that can render markdown, mathematical notation (KaTeX), code, and inline figures without issue.",

    174: "This project covers the full-stack development of an AI-powered research assistant — everything from raw PDF ingestion all the way through to the user-facing interface. On the backend side, that means API development in Python using FastAPI, document processing, embedding generation, vector database management, LLM orchestration, and agentic reasoning. The frontend is built with Next.js. The system itself is designed for single-user or small-team deployment on standard hardware, with the only external dependency being internet access to the Groq and Gemini APIs.",

    175: "What falls outside the scope is worth spelling out too: real-time paper ingestion from the web, multi-user authentication and authorisation beyond basic access control, fine-tuning of language models, and integration with institutional library management systems are all explicitly out of scope.",

    177: "Chapter 2 presents a comprehensive literature survey covering RAG systems, multimodal document understanding, agentic AI, and AI detection research. Chapter 3 lays out functional, non-functional, software, and hardware requirements. Chapter 4 describes the system design at both high and low levels, while Chapter 5 goes through the implementation of each module in detail. Chapter 6 covers testing strategies and evaluation — followed by Chapter 7, which presents the results and analysis. Chapter 8 wraps things up with conclusions and outlines directions for future enhancements.",

    181: "The idea of augmenting language model generation with retrieved context was properly formalised by Lewis et al. in 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks' (NeurIPS 2020). Their framework paired a neural retriever (DPR) with a generative model (BART) and demonstrated clearly superior performance on open-domain QA benchmarks — Natural Questions, TriviaQA, and WebQuestions among them. The core insight was simple but powerful: conditioning generation on retrieved passages reduces the load on the model's parametric memory and, in doing so, meaningfully improves factual accuracy.",

    182: "Subsequent work pushed RAG architectures considerably further. Izacard and Grave (2021) introduced the Fusion-in-Decoder (FiD) model, which extended RAG by encoding multiple retrieved passages independently and fusing them only in the decoder — and this approach achieved new state-of-the-art results on knowledge-intensive tasks. Then Shi et al. (2023) introduced REPLUG, which treats the retriever as a plug-in module and showed something perhaps surprising: even black-box LLMs can benefit substantially from retrieval augmentation.",

    183: "The survey paper 'Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG' (2024) gives a useful taxonomy of RAG systems — categorising them along dimensions of retrieval granularity, indexing strategy, query rewriting, and generation faithfulness. Three primary paradigms emerge from that taxonomy: Naive RAG (the straightforward retrieve-then-generate approach), Advanced RAG (which adds pre-retrieval query optimisation and post-retrieval re-ranking), and Modular RAG (with interchangeable pipeline components that can be swapped as needed).",

    184: "'mRAG: Elucidating the Design Space of Multimodal Retrieval-Augmented Generation' (2024) takes a systematic look at the design choices involved in multimodal RAG systems — specifically, how retrieval modality, indexing granularity (page-level versus element-level), and fusion strategy each affect end-to-end performance. What the authors found was that element-level indexing with typed retrieval consistently beats page-level approaches on question answering benchmarks. That finding directly informed the type-aware chunking strategy adopted in this project.",

    189: "'Scaling Beyond Context: A Survey of Multimodal RAG for Document Understanding' (2024) surveys no fewer than 47 multimodal RAG systems and categorises their document processing strategies. Four primary content extraction approaches come up repeatedly: pipeline-based extraction (using separate models per modality), end-to-end neural parsing, OCR-based text detection, and vision-language model (VLM) captioning. The authors' conclusion — that pipeline-based approaches remain the most practical for production systems because of their interpretability and modularity — is directly aligned with the architectural choices made in this project.",

    190: "'CMRAG: Co-Modality-Based Visual Document Retrieval and Question Answering' (2024) introduces a co-modality retrieval approach where visual and textual query embeddings are used jointly to retrieve multimodal chunks. The numbers are hard to ignore: their system achieves 18.3% higher accuracy on the DocVQA benchmark compared to text-only baselines. The VisionAnalyzer component in this project takes a similar modality-bridging approach — it uses Gemini 2.0 Flash to generate textual descriptions of figures, which are then embedded alongside the text content.",

    199: "'A Multimodal Retrieval-Augmented Generation System with ReAct Agent Logic for Multi-Hop Reasoning' (2024) is, without question, the most directly related prior work. The paper presents a system that combines multimodal document ingestion with a ReAct agent for scientific question answering — and their evaluation across 200 multi-hop questions drawn from 50 research papers shows the multimodal ReAct system hitting 76.4% answer accuracy, versus just 58.2% for text-only RAG. That said, their system has no AI humanization component and doesn't support anywhere near the breadth of task-specific pipelines implemented in this project.",

    203: "The rapid proliferation of LLM-generated text has spurred significant research into automated AI content detection. Solaiman et al. (2019) were among the first to show what was possible: their GPT-2 output detector — a fine-tuned RoBERTa model trained on a balanced mix of human-written and GPT-2 generated text — achieved 95% classification accuracy. Subsequent work by Guo et al. (2023) and Mitchell et al. (2023) introduced DetectGPT, a zero-shot detection method built on the observation that model-generated text tends to cluster in regions of negative curvature in the model's log-probability function.",

    204: "Humanizing AI-generated text — rewriting it to reduce its detectable AI signature while keeping the semantic content intact — has received comparatively less formal study. Krishna et al. (2023), in 'Paraphrasing Evades Detectors of AI-Generated Text, but Retrieval Is an Effective Defense', show that paraphrase-based humanization significantly reduces the detection accuracy of every tested detector, raising serious questions about the robustness of AI detection systems. The humanizer engine in this project goes further: rather than simple paraphrasing, it implements a principled iterative rewriting approach guided by explicit linguistic metrics.",

    211: "The system is required to provide the following functional capabilities:",

    212: "•  FR-01: Accept PDF research papers through a web interface and process them asynchronously — without blocking the UI — so users can continue interacting with the system during ingestion.",

    213: "•  FR-02: Extract text from PDFs while preserving the section heading structure and page numbers throughout.",

    225: "•  FR-14: Expose a REST API with at least fourteen endpoints, collectively covering all system functionality.",

    229: "•  NFR-01 Performance: Ingestion of a 20-page PDF paper must complete within 120 seconds under normal operating conditions.",

    230: "•  NFR-02 Performance: RAG query responses must be returned within 8 seconds for at least 90% of requests.",

    231: "•  NFR-03 Reliability: API rate-limit errors must be handled with automatic retry and exponential backoff, targeting a 99% successful ingestion rate for compliant PDFs.",

    232: "•  NFR-04 Scalability: The vector store must support at least 50 uploaded papers — roughly 100,000 chunks — without any measurable performance degradation.",

    233: "•  NFR-05 Usability: The web interface must work on modern browsers — Chrome, Firefox, Safari — without requiring any plugin installation.",

    234: "•  NFR-06 Maintainability: Each backend module should have a single, well-defined responsibility — following the Single Responsibility Principle — to keep the codebase maintainable as it grows.",

    235: "•  NFR-07 Security: API keys must never be exposed to the frontend; all external API calls are to be proxied exclusively through the backend server.",

    245: "The Multimodal AI Research Assistant is built on a three-tier client-server architecture — a Next.js frontend tier, a FastAPI backend tier, and a persistent data tier comprising ChromaDB and SQLite. The frontend talks exclusively to the backend REST API over HTTP/HTTPS, while the backend handles all interactions with external LLM APIs (Groq and Google Gemini) and the local data stores. That separation matters: it ensures that sensitive API keys never reach browser clients and that the frontend itself stays stateless.",

    260: "The pipeline implements a type-aware chunking strategy. Textual elements are split into overlapping chunks using the RecursiveCharacterTextSplitter — chunk size of 512 characters with a 50-character overlap. Tables, figures, and equations are handled differently: they're kept as single atomic chunks to preserve semantic integrity, because splitting a table row from its header, or a LaTeX equation from its surrounding explanation, would destroy the chunk's usefulness in retrieval. Every chunk gets a UUID4 identifier and a rich metadata object attached.",

    262: "The storage layer relies on two complementary databases: ChromaDB for vector embeddings and SQLite for document metadata. ChromaDB provides a persistent, disk-backed vector store with HNSW (Hierarchical Navigable Small World) graph indexing — which gives sub-linear approximate nearest-neighbour search complexity of O(log n) for retrieval, making it fast even as the collection grows.",

    265: "ChromaDB returns cosine distance in the range [0, 2]; the system converts this to a similarity score in [0, 1] using the formula described above. Any chunk with similarity below the configured threshold of 0.3 is filtered out of the result set entirely.",

    274: "The nine methods each have their own retrieval strategies tuned to the task. The compare() method, for instance, performs separate retrieval for each of the two papers being compared — 3,000 characters of context per paper — while the literature_survey() method retrieves up to 30 chunks with a maximum context of 8,000 characters to enable broad synthesis. The identify_gaps() method is particularly interesting: it issues three separate queries ('limitations', 'future work', 'challenges') and deduplicates the combined result set before passing anything to the generator.",

    276: "The ReAct Research Agent is designed to run for a maximum of ten reasoning iterations. At each step, the LLM gets the accumulated reasoning trace — the original question plus all previous thought–action–observation triples — and uses that to generate the next Thought, Action, and Action Input. The agent maintains a single growing prompt string as its working memory, which neatly sidesteps the need for a separate memory module.",

    285: "Each tool's output is capped at 1,500 characters to prevent context overflow across multiple iterations. The agent prompt follows the ReAct format — explicit format instructions, tool definitions expressed in JSON Schema, and a 'finish' pseudo-action that signals task completion when the agent has what it needs.",

    287: "The REST API is built on FastAPI, which handles automatic OpenAPI documentation generation as a side effect. All endpoints carry the /api prefix so the frontend development server can proxy requests without running into CORS issues. The API uses asynchronous request handlers (async def) for all I/O-bound operations; CPU-bound work like embedding and model inference is delegated to background threads via FastAPI's BackgroundTasks mechanism.",

    290: "Heavy singleton objects — the ingestion pipeline, RAG pipeline, agent, and humanizer — are initialised lazily on first use rather than at module import time. That's a deliberate design choice: it prevents the multi-gigabyte Sentence-Transformer and RoBERTa models from loading during unit tests, and it reduces cold-start time for endpoints that don't actually need those models.",

    300: "The frontend uses Zustand for global state management — it stores the active document, conversation history, model settings (temperature, top_k, model name), and detection scores. Framer Motion takes care of smooth animated transitions between pages and for streaming text tokens. Any mathematical content returned by the LLM in LaTeX format (delimited by $ or $$) gets rendered inline via the react-katex component.",

    304: "The ingestion module is probably the most architecturally complex part of the whole system — it comprises seven cooperating classes that each handle a distinct step. The IngestionPipeline class in pipeline.py acts as the orchestrator, initialising all sub-processors and coordinating their execution for each uploaded file.",

    305: "The PDFProcessor uses PyMuPDF's low-level fitz library to open the PDF and iterate through its pages. For each page, it calls page.get_text('dict') to get a structured representation of the content — individual text blocks with their associated font sizes and positions. A block gets classified as a section heading if its font size is at or above 14 points (that threshold empirically separates body text from section titles in academic papers), or if its text matches one of 21 pre-defined heading keywords.",

    313: "The SemanticChunker implements the type-aware chunking strategy described in Section 4.2. The choice of 512 characters as the chunk size wasn't arbitrary — it's grounded in the embedding model's effective input length (all-MiniLM-L6-v2 is optimised for inputs up to 256 word-pieces, which is roughly 500–600 characters) and the finding from the mRAG survey that chunk sizes in the 400–600 character range achieve the best retrieval precision on scientific text.",

    319: "The EmbeddingService class uses the Singleton pattern to ensure the all-MiniLM-L6-v2 model is loaded into memory exactly once per process lifetime, regardless of how many concurrent requests trigger embedding generation. The model produces L2-normalised 384-dimensional dense vector representations. Normalisation is actually critical here — it makes the dot product between two embeddings equal to their cosine similarity, which lets HNSW use inner product search as an efficient proxy for cosine similarity.",

    322: "The VectorStore wraps ChromaDB's Python client. The ChromaDB collection is configured with the cosine distance metric and HNSW indexing parameters — M=16 (maximum degree of nodes in the graph) and ef_construction=100 (size of the candidate list during construction). Those values were chosen because they offer a good trade-off between index construction time, index size, and query accuracy for collections scaling up to 100,000 vectors.",

    325: "This formula maps ChromaDB's distance output — which ranges from [0, 2], where 0 is identical and 2 is maximally dissimilar — onto a similarity score in [0, 1]. The default threshold of 0.3 effectively means a chunk needs at least 30% semantic alignment with the query before it's included in the result set.",

    329: "The Retriever class encapsulates the two-stage retrieve-and-build-context workflow. Its retrieve() method embeds the user query using the same EmbeddingService singleton used during ingestion — which is important, since it guarantees query and document embeddings occupy the same vector space — then searches ChromaDB with optional metadata filters for source file and content type, and applies the similarity threshold filter to the raw results.",

    330: "The build_context() method takes those retrieved chunks and formats them into a single context string ready for injection into the LLM prompt. Each chunk is formatted as:",

    332: "That format gives the LLM explicit provenance for each passage — which is what enables accurate citation in the generated response. The full context string is then truncated at the per-method maximum (anywhere from 4,000 to 8,000 characters) to stay within the LLM's context window.",

    338: "The ResearchAgent class implements the ReAct pattern on top of Groq's tool-calling API. Groq supports native function calling — tool definitions are passed as JSON Schema objects in the tools parameter of the API request. When the LLM decides to invoke a tool, it returns a structured Message object containing a tool_calls field; otherwise it returns a plain text response as the final answer.",

    339: "The agent keeps a growing context prompt as its working memory, extending it at each iteration with the previous thought, action, and observation. That accumulating context is what lets the agent synthesise information across multiple tool calls — for example, it might first call get_paper_list() to see what papers are available, then call search_tables() on a specific paper to pull quantitative results, and finally call search_text() to find the methodology behind those numbers.",

    344: "The agent runs at a low temperature of 0.1 during reasoning — that setting produces deterministic, factual responses that stay grounded in retrieved evidence. Each tool observation is capped at 1,500 characters to keep the accumulated prompt from exceeding the LLM's context window across up to ten iterations.",

    346: "The HumanizationEngine runs a three-pass iterative refinement loop. Before each rewriting pass, the current text gets scored by a hybrid detection algorithm that combines a RoBERTa-based ML detector with a suite of heuristic linguistic metrics.",

    347: "The RoBERTa detector in use is Hugging Face's 'roberta-base-openai-detector' — fine-tuned by OpenAI on a balanced dataset of human-written text (sourced from WebText) and GPT-2 generated text. It outputs a probability distribution over 'Real' and 'Fake' (AI-generated) classes, and it's the 'Fake' probability that serves as the ML-based AI score.",

    349: "(i) Burstiness: the coefficient of variation (CV) of sentence length distribution, defined as σ/μ where σ is the standard deviation and μ is the mean sentence length in words. Human writing tends to show higher burstiness (CV > 0.5) than AI writing (CV < 0.3), simply because humans vary their sentence lengths much more dramatically than LLMs do.",

    351: "(ii) Type-Token Ratio (TTR): the ratio of unique word types to total word tokens — a direct measure of lexical diversity. A TTR close to 1.0 signals high vocabulary richness, which is characteristic of human writing; AI text tends to cluster toward lower TTR values because of its tendency toward repetitive phrasing.",

    353: "(iii) Human Marker Density: the proportion of sentences containing informal human writing markers — things like em-dashes (—), parenthetical asides, first-person contractions (don't, can't, it's), or sentences that start with a coordinating conjunction (but, and, yet).",

    356: "If the composite score comes in above the 20% threshold, the text gets submitted to Gemini 2.0 Flash with an aggressive humanization prompt that instructs the model to introduce natural sentence length variation, contractions, colloquial transitions, and subtle imperfections. The rewritten text is then re-scored, and the whole loop continues — up to three passes in total, or until the score drops below the threshold.",

    360: "The API module (src/api/routes.py) defines all FastAPI route handlers and Pydantic request/response models. Request validation is handled automatically by FastAPI via Python type annotations — if a required field is missing or has the wrong type, FastAPI returns a 422 Unprocessable Entity response with a detailed error message before the handler is ever invoked.",

    361: "The upload endpoint is worth examining in some detail, since PDF ingestion is a long-running operation — anywhere from 10 to 120 seconds depending on paper length and whether vision processing is enabled. The endpoint accepts the uploaded file, saves it to disk, and immediately returns a 202 Accepted response carrying the document ID and 'processing' status. Ingestion then continues in a background thread, with the thread lock (_ingest_lock) ensuring that at most one ingestion runs at a time, preventing race conditions in ChromaDB writes.",

    366: "The Next.js frontend is implemented as a single-page application with client-side routing handled by the App Router. The five main pages — Search, Compare, Survey, Humanizer, and Trends — all share a common layout component that renders the navigation sidebar, the document management panel, and the model settings drawer.",

    368: "The model settings panel gives users sliders and dropdowns for temperature, top_p, max_tokens, and model selection. The list of available models is fetched dynamically from the GET /api/models endpoint at page load time — that way, the frontend always displays an up-to-date list of supported Groq models without needing a frontend redeploy every time a new model is added to the backend.",

    372: "Unit tests cover all core backend modules and are written with pytest. Each test targets a single function or method in isolation — mock objects stand in for external dependencies like API clients and database connections. The key test cases are listed below.",

    376: "Integration tests verify that cooperating modules actually work together correctly. They run against a real ChromaDB instance (spun up in a temporary directory) and a real SQLite database, but the external LLM and Vision APIs are still mocked — both to avoid API costs and to prevent rate limits from slowing down automated test runs.",

    380: "Performance testing used a set of 10 representative research papers drawn from the arXiv dataset across machine learning and natural language processing domains — average length 18 pages, ranging from 8 to 32 pages.",

    381: "Ingestion performance: without vision processing, average ingestion time was 47 seconds per paper; with full Gemini Vision processing — figure descriptions and LaTeX extraction — that climbs to 118 seconds. The dominant cost turns out to be the Gemini API rate limit, which enforces a 4-second minimum interval between calls and contributes roughly 4 seconds for each extracted image.",

    382: "Query latency: end-to-end P50 latency for a single-shot RAG query — covering embedding, retrieval, context building, and Groq generation — measured 2.1 seconds. The P90 came in at 3.8 seconds, driven largely by Groq API variability. Agent queries requiring multiple tool invocations averaged 8.4 seconds for queries needing 4–5 iterations.",

    384: "RAG quality was assessed using the RAGAS (Retrieval-Augmented Generation Assessment) framework across three dimensions: Context Relevance, Faithfulness, and Answer Relevance. The test dataset — 50 question–answer pairs drawn from five research papers — was manually constructed, with ground-truth answers derived from careful paper reading rather than automated generation.",

    385: "Context Relevance captures whether the retrieved chunks are actually pertinent — computed as the fraction of chunks that contain information relevant to the question. Faithfulness measures whether the generated answer stays grounded in the retrieved context; in practice, that means checking whether every factual claim in the answer can be traced back to a retrieved passage. Answer Relevance, the third dimension, simply measures whether the answer directly addresses what was asked.",

    393: "Retrieval quality was assessed using standard information retrieval metrics — Hit Rate@k (the fraction of queries for which at least one relevant chunk lands in the top-k results) and Mean Reciprocal Rank (MRR@k). Evaluations were run separately for text, table, figure, and equation chunk types, so we could understand the system's multimodal retrieval capabilities across modalities rather than as a single aggregate number.",

    398: "Text retrieval leads all modalities with a Hit Rate@10 of 0.91 — which makes sense, since all-MiniLM-L6-v2 was originally trained predominantly on natural language text. Figure retrieval shows the lowest performance (Hit Rate@10 = 0.83), because figure descriptions generated by Gemini Vision don't always capture the exact keywords a user query happens to use. Equation retrieval actually performs better than expected at 0.84, thanks to the rich natural language context that Gemini-generated explanations wrap around the raw LaTeX expressions.",

    400: "LLM generation quality was assessed along three dimensions: faithfulness (whether answers stay grounded in retrieved context), answer completeness, and citation accuracy. Two independent annotators evaluated a sample of 30 generated responses.",

    403: "A hallucination rate of 7% compares favourably against published benchmarks for RAG systems on scientific QA tasks — comparable systems typically sit between 12% and 18%. The improvement is largely attributed to the strict context-only instruction in the QA prompt template, which explicitly tells the model to answer only from the provided context and to say 'information not found in the provided papers' whenever the relevant information is absent.",

    405: "The ReAct agent was evaluated on 25 multi-hop questions, each requiring information to be connected from at least two different sections or papers. Questions were classified as 2-hop, 3-hop, or 4+-hop based on the number of distinct retrieval operations needed to piece together the answer.",

    406: "The agent hit 80% correct answers on 2-hop questions, 72% on 3-hop questions, and 64% on questions requiring 4 or more hops. The accuracy drop with hop count is a predictable consequence of compounding retrieval errors — each tool call has some probability of returning irrelevant content, and those errors stack up across iterations. On average, 2-hop questions required 3.2 tool calls per query; 4+-hop questions required 5.7.",

    408: "The humanizer engine was tested on 40 AI-generated paragraphs spanning different research tasks — summaries, explanations, and comparisons. Before humanization, the mean AI detection score across all paragraphs sat at 78.3%. One pass brought that down to 41.2%. After two passes, the mean was 18.7%, with 92.5% of paragraphs clearing the 20% threshold — a strong result for a two-pass system.",

    414: "To put the system's capabilities in perspective, the Multimodal AI Research Assistant is compared against representative existing tools and systems in the research assistance domain.",

    422: "Building a genuinely useful research assistant turns out to mean solving four separate hard problems simultaneously — processing documents beyond plain text, maintaining a persistent knowledge base, reasoning across multiple retrieval steps, and ensuring generated content reads as academically authentic rather than machine-produced. This project tackled all four in a single integrated system, and the results show it holds up in practice.",

    423: "The six-stage multimodal ingestion pipeline — combining PyMuPDF, pdfplumber, EasyOCR, and Gemini 2.0 Flash Vision — successfully pulls out text, tables, figures, OCR content, and mathematical equations from research papers, building a typed, searchable knowledge base as it goes. The type-aware chunking strategy, which keeps atomic content units (tables, figures, equations) as single chunks while semantically splitting narrative text, proved its worth in practice: an overall Hit Rate@10 of 0.88 across modalities.",

    424: "Together, the nine RAG pipeline methods cover a full research workflow — from quick one-line questions all the way to multi-paper literature surveys and gap identification. RAGAS evaluation returned a faithfulness score of 0.81 with a hallucination rate of just 7%, which we put down to the context-grounded prompt design: keeping the model anchored to retrieved evidence rather than relying on its own parametric memory makes a real difference.",

    425: "The ReAct agent demonstrated the value of agentic reasoning for complex queries — 80% accuracy on 2-hop questions, dropping to 64% on 4+-hop questions as compounding retrieval errors accumulate across iterations. The agent's typed tool set, covering text, table, figure, and equation search, enables targeted multimodal retrieval right inside the reasoning loop.",

    426: "The hybrid AI Detection and Humanization Engine — which pairs RoBERTa with heuristic linguistic metrics (burstiness, TTR, and human marker density) — successfully brought AI detection scores down from an initial mean of 78.3% to below 20% for 92.5% of paragraphs, and it typically managed that within just two rewriting passes.",

    427: "Taken together, these results demonstrate that a production-quality multimodal research assistant — one that combines RAG, agentic reasoning, and AI humanization — is genuinely achievable using publicly available APIs and open-source libraries. This isn't a toy demo; it's a system that handles real research papers and returns answers with traceable citations. That represents a meaningful step beyond what general-purpose AI assistants currently offer to research workflows.",

    430: "•  Knowledge Graph Integration: Build a paper-level knowledge graph that captures citations, shared datasets, and competing methodologies — then add graph-traversal retrieval alongside vector search to improve multi-hop accuracy on relationship-intensive queries, following the KA-RAG approach.",

    431: "•  Multi-Agent Architecture: Decompose the single ReAct agent into distinct roles — planner, retriever, critique agent, and synthesis agent — following the MA-RAG framework. This would be particularly valuable for complex 4+-hop questions, where a single reasoning chain tends to become unwieldy.",

    432: "•  Fine-Tuned Embedding Model: Fine-tune all-MiniLM-L6-v2 on a domain-specific scientific corpus — arXiv, for instance — using contrastive learning with hard negatives to sharpen retrieval precision for highly technical vocabulary.",

    433: "•  Streaming Generation: Add server-sent events (SSE) or WebSocket streaming for LLM generation, so long-form outputs like literature surveys feel responsive rather than leaving users staring at a frozen screen.",

    434: "•  Long-Document Support: Integrate a hierarchical map-reduce summarisation pipeline for papers exceeding 100 pages — summarising each section independently and then synthesising across them.",

    435: "•  Multi-User Support: Add JWT-based authentication with per-user isolated knowledge bases, which would extend the system's reach from individual researchers to whole research teams.",

    436: "•  Automatic Web Ingestion: Connect to Semantic Scholar or arXiv APIs so that users can add papers by DOI or identifier, rather than having to download and re-upload PDFs manually.",

    437: "•  Evaluation Dashboard: Build an in-product evaluation dashboard that runs RAGAS metrics continuously against a maintained benchmark set — providing ongoing quality monitoring as underlying models are updated.",
}


def replace_paragraph_text(para, new_text):
    """Replace a paragraph's text while preserving the first run's formatting."""
    if not para.runs:
        para.text = new_text
        return

    # Capture the formatting from the first run
    first_run = para.runs[0]
    font = first_run.font

    # Clear all runs
    for run in para.runs:
        run.text = ""

    # Set new text in first run
    first_run.text = new_text


def main():
    doc = Document(DOCX_PATH)
    paras = doc.paragraphs

    replaced = 0
    skipped = 0

    for idx, new_text in REPLACEMENTS.items():
        if idx >= len(paras):
            print(f"  SKIP para {idx}: index out of range (doc has {len(paras)} paras)")
            skipped += 1
            continue

        para = paras[idx]
        old_text = para.text.strip()

        if not old_text:
            print(f"  SKIP para {idx}: empty paragraph")
            skipped += 1
            continue

        replace_paragraph_text(para, new_text)
        replaced += 1

    doc.save(OUTPUT_PATH)
    print(f"\nDone. Replaced {replaced} paragraphs, skipped {skipped}.")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
