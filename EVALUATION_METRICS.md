# Evaluation Metrics — Multimodal AI Research Assistant

## The Problem: No Ground Truth

There is no labeled dataset with "question → correct answer" pairs for uploaded research papers. This is normal for RAG systems. But there are **well-established evaluation approaches** that work without ground truth.

---

## Two Evaluation Approaches

1. **Component-wise evaluation** — evaluate each module separately
2. **End-to-end evaluation** — evaluate the full pipeline

**Both should be done.**

---

---

## Component-Wise Evaluation

### 1. Ingestion Pipeline (Extraction Quality)

| Component | What to evaluate | How to evaluate | Metric |
|-----------|-----------------|-----------------|--------|
| **PDFProcessor** | Does it extract all text correctly? | Manually compare extracted text vs original PDF for 5-10 pages | **Extraction Accuracy** = correct blocks / total blocks |
| **TableExtractor** | Does it detect and convert all tables? | Count tables in PDF manually, compare with extracted count | **Table Detection Rate** = detected tables / actual tables |
| **ImageExtractor** | Does it extract all images? | Count images in PDF manually, compare with extracted count | **Image Extraction Rate** = extracted images / actual images |
| **OCRProcessor** | Is the OCR text accurate? | Compare OCR output vs actual text for 10 images | **Character Error Rate (CER)** = edit_distance / total_chars |
| **VisionAnalyzer** | Are figure descriptions accurate and useful? | Human rating (1-5 scale) on 10-15 figures | **Average Human Score** (1-5) |
| **EquationExtractor** | Is the LaTeX correct? | Compare generated LaTeX vs actual equation for 10 equations | **LaTeX Accuracy** = correct extractions / total extractions |

**These are simple manual evaluations — pick a sample of 10-15 cases and score them.**

---

### 2. Chunking Quality

| Metric | What it measures | How to compute |
|--------|-----------------|----------------|
| **Average Chunk Size** | Are chunks within the 512-char target? | `mean([len(chunk.content) for chunk in chunks])` |
| **Chunk Boundary Quality** | Do chunks break at meaningful boundaries (sentences/paragraphs) vs mid-word? | Manually check 20 chunks — count how many end at a sentence/paragraph boundary |
| **Metadata Completeness** | Do chunks have correct page numbers, section headings, element types? | Verify metadata of 20 random chunks against the original PDF |

---

### 3. Retrieval Quality

This is the **most important component to evaluate**. Can be done without ground truth:

| Metric | What it measures | How to compute |
|--------|-----------------|----------------|
| **Hit Rate @ K** | For a given question, is the relevant chunk in the top-K results? | Ask 20 questions, manually check if the correct section was retrieved in top-10. Hit Rate = hits / total queries |
| **Mean Reciprocal Rank (MRR)** | How high is the first relevant result ranked? | For each query, find the rank of the first relevant chunk. MRR = mean(1/rank) |
| **Context Relevance** | Are the retrieved chunks actually relevant to the query? | For 20 queries, have a human rate each retrieved chunk as relevant/not-relevant. Relevance = relevant_chunks / total_retrieved |
| **Diversity** | Do results come from different sections/pages (not all from the same paragraph)? | Check if top-10 results span multiple pages/sections |

**How to create test queries without ground truth:**

1. Read 5 papers yourself
2. Write 20 questions where you **know which section/page has the answer**
3. Run each query through the retriever
4. Check if the correct section appears in results

---

### 4. Generation Quality (LLM-as-Judge — No Ground Truth Needed)

This is where the **RAGAS framework** comes in. RAGAS evaluates RAG systems using the LLM itself as a judge:

| Metric | What it measures | How it works |
|--------|-----------------|-------------|
| **Faithfulness** | Does the answer only use information from the retrieved context? (No hallucination) | LLM checks if every claim in the answer can be traced to the retrieved chunks |
| **Answer Relevance** | Does the answer actually address the question? | LLM generates questions from the answer, checks if they match the original question |
| **Context Precision** | Are the retrieved chunks relevant to the question? | LLM judges if each retrieved chunk is useful for answering |
| **Context Recall** | Does the retrieved context contain all information needed to answer? | LLM checks if the answer could be fully derived from the context |

---

### 5. Agent Evaluation

| Metric | What it measures | How to compute |
|--------|-----------------|----------------|
| **Task Completion Rate** | Does the agent successfully reach a `finish` action? | completed_runs / total_runs |
| **Average Steps** | How many iterations does the agent take? | mean(steps per query) — fewer is more efficient |
| **Tool Selection Accuracy** | Does the agent choose the right tool? | For 15 queries, manually check if the tool chosen was appropriate (e.g., used `search_tables` for table questions) |
| **Reasoning Quality** | Are the Thought steps logical? | Human rating (1-5) on 15 agent traces |
| **Answer Improvement over RAG** | Is the agent answer better than single-shot RAG for multi-hop questions? | Compare agent vs RAG answers for 10 multi-hop questions using human rating |

---

---

## End-to-End Evaluation

### Method 1: Human Evaluation (Most Reliable)

Create a test set of **20-30 questions** across different types:

| Question Type | Example | Count |
|---------------|---------|-------|
| Factual (single paper) | "What embedding model does Paper X use?" | 5 |
| Comparison (two papers) | "How do Paper X and Y differ in methodology?" | 5 |
| Multi-hop (needs multiple searches) | "Which paper achieves the best accuracy and what method do they use?" | 5 |
| Table-based | "What are the benchmark results in Table 3?" | 3 |
| Figure-based | "What does Figure 2 show about the trend?" | 3 |
| Summarization | "Summarize the contributions of Paper X" | 3 |
| Research gaps | "What are the limitations mentioned?" | 3 |
| Trend analysis | "What methodological trends exist across papers?" | 3 |

**For each question, evaluate on these 4 dimensions (1-5 scale):**

| Dimension | 1 (Poor) | 3 (Acceptable) | 5 (Excellent) |
|-----------|----------|-----------------|---------------|
| **Correctness** | Factually wrong | Partially correct | Fully correct, matches paper content |
| **Completeness** | Missing key information | Covers main points | Comprehensive, covers all relevant details |
| **Relevance** | Off-topic or generic | Mostly on-topic | Directly addresses the question |
| **Citation Quality** | No citations or wrong citations | Some correct citations | All claims cited with correct source, page, section |

**Final score** = average across all dimensions and questions.

---

### Method 2: RAGAS Framework (Automated, No Ground Truth)

RAGAS can be run programmatically:

```python
# pip install ragas

from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

# Prepare your test data
data = {
    "question": ["What method does Paper X use?", ...],
    "answer": ["Paper X uses transformer-based...", ...],       # from your system
    "contexts": [["chunk1 text", "chunk2 text", ...], ...],     # retrieved chunks
    "ground_truth": ["Paper X uses a transformer...", ...],     # optional, can be empty
}

dataset = Dataset.from_dict(data)

# Evaluate
results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
)

print(results)
# Output: {'faithfulness': 0.85, 'answer_relevancy': 0.78, ...}
```

**RAGAS scores (0 to 1):**

| Metric | Good Threshold | Meaning |
|--------|---------------|---------|
| **Faithfulness** | > 0.8 | Low hallucination — answer is grounded in context |
| **Answer Relevancy** | > 0.7 | Answer actually addresses the question |
| **Context Precision** | > 0.7 | Retrieved chunks are relevant to the question |
| **Context Recall** | > 0.7 | Context has enough information to answer |

---

### Method 3: Comparative Evaluation

Compare the system against baselines:

| System | What to compare |
|--------|----------------|
| **Direct LLM (no RAG)** | Send the question to Groq/Gemini without any retrieved context — compare answer quality |
| **Basic RAG (no agent)** | Compare single-shot RAG vs agent mode on multi-hop questions |
| **ChatGPT with PDF** | Upload the same paper to ChatGPT, ask the same questions, compare |

This gives **relative performance** even without ground truth.

---

---

## Recommended Evaluation Plan

| Phase | What | How | Effort |
|-------|------|-----|--------|
| **Phase 1** | Component evaluation | Manually verify extraction, chunking, retrieval on 10-15 samples per component | 2-3 hours |
| **Phase 2** | End-to-end human evaluation | Create 20-30 test questions, rate answers on 4 dimensions (1-5 scale) | 3-4 hours |
| **Phase 3** | RAGAS automated evaluation | Run RAGAS on the same 20-30 questions, get faithfulness/relevancy scores | 1 hour |
| **Phase 4** | Comparative evaluation | Compare against direct LLM and ChatGPT on 10 questions | 1-2 hours |
| **Phase 5** | RAG vs Agent comparison | Compare single-shot RAG vs agent mode on 10 multi-hop questions | 1 hour |

---

---

## Summary of All Metrics

| Category | Metrics |
|----------|---------|
| **Extraction** | Extraction Accuracy, Table Detection Rate, Image Extraction Rate, CER (OCR), LaTeX Accuracy, Vision Description Score (1-5) |
| **Chunking** | Average Chunk Size, Boundary Quality, Metadata Completeness |
| **Retrieval** | Hit Rate@K, MRR, Context Relevance, Diversity |
| **Generation** | Faithfulness, Answer Relevancy, Context Precision, Context Recall (via RAGAS) |
| **Agent** | Task Completion Rate, Average Steps, Tool Selection Accuracy, Reasoning Quality |
| **End-to-End** | Correctness (1-5), Completeness (1-5), Relevance (1-5), Citation Quality (1-5) |
| **Comparative** | System vs Direct LLM, RAG vs Agent, System vs ChatGPT |

---

---

## Formulas Reference

### Hit Rate @ K

```
Hit Rate @ K = (Number of queries where at least one relevant chunk is in top-K) / (Total queries)
```

### Mean Reciprocal Rank (MRR)

```
MRR = (1/N) * Σ (1 / rank_i)

where rank_i = position of the first relevant chunk for query i
      N = total number of queries
```

**Example:**
- Query 1: first relevant chunk at rank 1 → 1/1 = 1.0
- Query 2: first relevant chunk at rank 3 → 1/3 = 0.33
- Query 3: first relevant chunk at rank 2 → 1/2 = 0.5
- MRR = (1.0 + 0.33 + 0.5) / 3 = 0.61

### Character Error Rate (CER) for OCR

```
CER = Edit_Distance(OCR_output, Ground_Truth) / Length(Ground_Truth)
```

- CER = 0 means perfect OCR
- CER = 0.05 means 5% of characters are wrong

### Cosine Similarity (used by ChromaDB)

```
similarity(A, B) = (A · B) / (||A|| × ||B||)

In ChromaDB: similarity = 1.0 - (cosine_distance / 2.0)
```

- 1.0 = identical vectors
- 0.0 = completely unrelated
- Threshold in this project: 0.3

### RAGAS Faithfulness

```
Faithfulness = (Number of claims in answer that can be inferred from context) / (Total claims in answer)
```

- 1.0 = every claim is grounded in retrieved context (zero hallucination)
- 0.0 = completely hallucinated

### RAGAS Answer Relevancy

```
Answer Relevancy = mean(cosine_similarity(original_question, generated_questions))

where generated_questions are questions that the answer would be a valid response to
```

- 1.0 = answer perfectly addresses the question
- 0.0 = answer is completely off-topic
