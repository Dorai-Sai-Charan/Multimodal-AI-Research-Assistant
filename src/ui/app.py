"""
Streamlit UI — Multimodal AI Research Assistant
Tabs:
  1. Chat Assistant      — conversational Q&A with optional ReAct agent
  2. Compare Papers      — side-by-side paper comparison
  3. Survey & Gaps       — literature survey + research gap identification
  4. Search & Explain    — semantic search, concept / diagram / table explanation
  5. Trends & Recommend  — trend analysis + related-paper recommendation
"""

import streamlit as st
import requests
import os

API_URL = os.getenv("API_URL", "http://localhost:8000/api")

# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* gradient header */
    .main-header {
        font-size: 2rem; font-weight: 700;
        background: linear-gradient(90deg, #667eea, #764ba2);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .sub-header { font-size: 0.95rem; color: #888; margin-bottom: 1.5rem; }
    /* citation box */
    .citation-box {
        background: #1e1e2e; border-left: 4px solid #764ba2;
        padding: 8px 14px; margin: 6px 0;
        border-radius: 0 8px 8px 0; font-size: 0.82rem;
    }
    /* reasoning step */
    .step-box {
        background: #12122a; border: 1px solid #333;
        border-radius: 8px; padding: 10px 14px; margin: 6px 0;
        font-size: 0.82rem;
    }
    .step-thought { color: #a78bfa; }
    .step-action  { color: #34d399; }
    .step-obs     { color: #93c5fd; }
    /* doc card */
    .doc-card {
        background: #1e1e2e; border-radius: 8px;
        padding: 10px 14px; margin: 6px 0; border: 1px solid #333;
    }
    /* stat card */
    .stat-card {
        background: linear-gradient(135deg,#1e1e2e,#2d2d3f);
        border-radius: 10px; padding: 16px; text-align: center; border: 1px solid #333;
    }
    .stat-value { font-size: 1.8rem; font-weight: 700; color: #764ba2; }
    .stat-label { font-size: 0.8rem; color: #888; }
    /* feature badge */
    .feature-badge {
        display: inline-block; background: #2d2d3f;
        border: 1px solid #764ba2; border-radius: 20px;
        padding: 3px 10px; font-size: 0.75rem; color: #a78bfa; margin: 3px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

for key, default in [
    ("messages", []),
    ("documents", []),
    ("agent_mode", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def refresh_documents():
    try:
        r = requests.get(f"{API_URL}/documents", timeout=30)
        if r.status_code == 200:
            st.session_state.documents = r.json()
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
        st.session_state.documents = []


def render_citations(citations: list[dict]):
    if not citations:
        return
    with st.expander("📎 Sources & Citations"):
        for c in citations:
            section = f" — {c['section']}" if c.get("section") else ""
            st.markdown(
                f'<div class="citation-box">'
                f'📄 <b>{c["source_file"]}</b> — Page {c["page_number"]}'
                f'{section} (Relevance: {c["relevance_score"]:.0%})'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_reasoning_steps(steps: list[dict]):
    if not steps:
        return
    with st.expander(f"🧠 Agent Reasoning Trace ({len(steps)} steps)"):
        for s in steps:
            st.markdown(
                f'<div class="step-box">'
                f'<b>Step {s["step"]}</b><br>'
                f'<span class="step-thought">💭 Thought:</span> {s["thought"]}<br>'
                f'<span class="step-action">⚡ Action:</span> <code>{s["action"]}</code> '
                f'— {s["action_input"]}<br>'
                f'<span class="step-obs">👁 Observation:</span> {s["observation"][:300]}{"…" if len(s["observation"]) > 300 else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )


def api_post(endpoint: str, payload: dict, timeout: int = 300):
    """POST to the backend; returns (data_dict | None, error_str | None)."""
    try:
        r = requests.post(f"{API_URL}/{endpoint}", json=payload, timeout=timeout)
        if r.status_code == 200:
            return r.json(), None
        return None, r.json().get("detail", "Unknown error")
    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to the API server. Start it with `python -m src.main`."
    except requests.exceptions.ReadTimeout:
        return None, "Request timed out. The server may be rate-limited — please wait a moment and try again."
    except Exception as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# Sidebar — document management
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<p class="main-header">🔬 Research Assistant</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Upload papers · ask questions · discover insights</p>',
        unsafe_allow_html=True,
    )

    # Feature badges (inline)
    badges_html = " ".join(
        f'<span class="feature-badge">{b}</span>'
        for b in ["RAG", "Agentic AI", "Multimodal", "Multi-hop", "Semantic Search"]
    )
    st.markdown(badges_html, unsafe_allow_html=True)

    st.divider()
    st.markdown("### 📄 Upload Document")
    uploaded_file = st.file_uploader(
        "Upload a research paper (PDF)", type=["pdf"], label_visibility="collapsed"
    )
    if uploaded_file and st.button("📥 Process Document", use_container_width=True):
        try:
            r = requests.post(
                f"{API_URL}/upload",
                files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                timeout=30,
            )
            if r.status_code == 200:
                st.success(
                    f"**{uploaded_file.name}** uploaded! "
                    "Ingestion is running in the background. "
                    "The status will update automatically."
                )
                refresh_documents()
            else:
                st.error(f"Upload failed: {r.json().get('detail', 'Unknown error')}")
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API server.")
        except requests.exceptions.ReadTimeout:
            st.error("Upload timed out. Please try again.")

    st.divider()
    st.markdown("### 📚 Uploaded Papers")
    refresh_documents()

    # Show processing status
    any_processing = any(
        d["status"] == "processing" for d in st.session_state.documents
    )
    if any_processing:
        st.caption("⏳ Ingestion in progress…")

    if st.button("🔄 Refresh", key="refresh_docs", use_container_width=True):
        refresh_documents()
        st.rerun()

    if st.session_state.documents:
        for doc in st.session_state.documents:
            emoji = "✅" if doc["status"] == "completed" else "⏳" if doc["status"] == "processing" else "❌"
            st.markdown(
                f'<div class="doc-card">{emoji} <b>{doc["filename"]}</b><br>'
                f'<span style="color:#888">📄 {doc["total_pages"]} pages | 🧩 {doc["total_chunks"]} chunks</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("🗑 Delete", key=f"del_{doc['id']}"):
                try:
                    requests.delete(f"{API_URL}/documents/{doc['id']}", timeout=10)
                    refresh_documents()
                    st.rerun()
                except Exception:
                    st.error("Delete failed.")
    else:
        st.info("No papers uploaded yet.")

    st.divider()
    total_docs = len(st.session_state.documents)
    total_chunks = sum(d.get("total_chunks", 0) for d in st.session_state.documents)
    c1, c2 = st.columns(2)
    c1.markdown(
        f'<div class="stat-card"><div class="stat-value">{total_docs}</div>'
        f'<div class="stat-label">Papers</div></div>',
        unsafe_allow_html=True,
    )
    c2.markdown(
        f'<div class="stat-card"><div class="stat-value">{total_chunks}</div>'
        f'<div class="stat-label">Chunks</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main area — tabs
# ---------------------------------------------------------------------------

st.title("Multimodal AI Research Assistant")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Chat Assistant",
    "Compare Papers",
    "Survey & Gaps",
    "Search & Explain",
    "Trends & Recommend",
])


# ===========================================================================
# TAB 1 — Chat Assistant
# Covers: Q&A, multi-hop retrieval, citation-based answering,
#         conversational assistant, multi-doc reasoning
# ===========================================================================

with tab1:
    st.markdown("#### 💬 Conversational Research Assistant")
    st.caption(
        "Ask anything about your uploaded papers. "
        "Toggle **Agent Mode** for complex multi-hop questions."
    )

    col_opt1, col_opt2, col_opt3 = st.columns([2, 2, 2])
    with col_opt1:
        st.session_state.agent_mode = st.toggle(
            "🤖 Agent Mode (multi-hop)", value=st.session_state.agent_mode
        )
    with col_opt2:
        multi_doc = st.toggle("🌐 Multi-document reasoning")
    with col_opt3:
        filter_paper = st.selectbox(
            "Filter to paper",
            options=["All papers"] + [d["filename"] for d in st.session_state.documents if d["status"] == "completed"],
            label_visibility="collapsed",
        )
        source_filter = None if filter_paper == "All papers" else filter_paper

    if st.button("🗑 Clear conversation", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()

    # Render conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            render_citations(msg.get("citations", []))
            if "reasoning_steps" in msg:
                render_reasoning_steps(msg["reasoning_steps"])

    # Chat input
    if prompt := st.chat_input("Ask a question about your research papers…"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                # Build chat history for the agent
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]  # exclude the current message
                ]

                if st.session_state.agent_mode:
                    data, err = api_post(
                        "agent",
                        {"question": prompt, "chat_history": history},
                        timeout=180,
                    )
                elif multi_doc:
                    data, err = api_post(
                        "multi-doc",
                        {"question": prompt},
                    )
                else:
                    data, err = api_post(
                        "query",
                        {
                            "question": prompt,
                            "top_k": 10,
                            "filter_source": source_filter,
                        },
                    )

            if err:
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": f"Error: {err}"})
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                if "reasoning_steps" in data:
                    render_reasoning_steps(data["reasoning_steps"])

                mode_label = (
                    "Agent (multi-hop)" if st.session_state.agent_mode
                    else "Multi-doc" if multi_doc
                    else "RAG"
                )
                steps_label = (
                    f" | Steps: {data.get('total_steps', 0)}"
                    if st.session_state.agent_mode else ""
                )
                st.caption(
                    f"Mode: {mode_label} | Chunks used: {data['chunks_used']}{steps_label}"
                )

                saved = {
                    "role": "assistant",
                    "content": data["answer"],
                    "citations": data.get("citations", []),
                }
                if "reasoning_steps" in data:
                    saved["reasoning_steps"] = data["reasoning_steps"]
                st.session_state.messages.append(saved)


# ===========================================================================
# TAB 2 — Compare Papers
# Covers: paper comparison, multi-document reasoning
# ===========================================================================

with tab2:
    st.markdown("#### 📊 Compare Two Research Papers")
    st.caption("Select two uploaded papers to get a structured side-by-side comparison.")

    completed = [d["filename"] for d in st.session_state.documents if d["status"] == "completed"]

    if len(completed) < 2:
        st.info("Upload at least two research papers to use this feature.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            paper1 = st.selectbox("Paper 1", completed, key="cmp_p1")
        with col_b:
            options_b = [p for p in completed if p != paper1]
            paper2 = st.selectbox("Paper 2", options_b, key="cmp_p2")

        if st.button("📊 Compare Papers", use_container_width=True):
            with st.spinner(f"Comparing '{paper1}' vs '{paper2}'…"):
                data, err = api_post("compare", {"paper1": paper1, "paper2": paper2}, timeout=120)

            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")


# ===========================================================================
# TAB 3 — Literature Survey & Research Gaps
# Covers: literature survey generation, research gap identification
# ===========================================================================

with tab3:
    st.markdown("#### 📚 Literature Survey & Research Gaps")

    sub1, sub2 = st.tabs(["📝 Literature Survey", "🔭 Research Gaps"])

    with sub1:
        st.caption(
            "Generate a structured literature survey from your uploaded papers. "
            "Optionally specify a topic to focus the survey."
        )
        topic = st.text_input(
            "Topic (optional)",
            placeholder="e.g. multimodal retrieval-augmented generation",
        )
        top_k_survey = st.slider("Chunks to retrieve", 10, 50, 30, key="survey_topk")

        if st.button("📝 Generate Literature Survey", use_container_width=True):
            with st.spinner("Generating literature survey…"):
                data, err = api_post(
                    "literature-survey",
                    {"topic": topic, "top_k": top_k_survey},
                    timeout=180,
                )
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")

    with sub2:
        st.caption(
            "Identify research gaps, limitations, and future directions "
            "from the uploaded papers."
        )
        gap_paper = st.selectbox(
            "Focus on a specific paper (or all)",
            ["All papers"] + [d["filename"] for d in st.session_state.documents if d["status"] == "completed"],
            key="gap_paper",
        )
        gap_source = None if gap_paper == "All papers" else gap_paper

        if st.button("🔭 Identify Research Gaps", use_container_width=True):
            with st.spinner("Analysing research gaps…"):
                data, err = api_post(
                    "research-gaps",
                    {"source_file": gap_source},
                    timeout=120,
                )
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")


# ===========================================================================
# TAB 4 — Search & Explain
# Covers: semantic search, concept explanation, diagram/table explanation,
#         technical concept explanation
# ===========================================================================

with tab4:
    st.markdown("#### 🔍 Search & Explain")

    sub_search, sub_explain = st.tabs(["🔎 Semantic Search", "💡 Explain Concept / Diagram / Table"])

    with sub_search:
        st.caption(
            "Run a semantic search across your uploaded papers. "
            "Results are ranked by relevance."
        )
        search_query = st.text_input("Search query", placeholder="e.g. attention mechanism transformer")
        search_paper = st.selectbox(
            "Filter to paper",
            ["All papers"] + [d["filename"] for d in st.session_state.documents if d["status"] == "completed"],
            key="search_paper",
        )
        search_topk = st.slider("Results", 3, 20, 10, key="search_topk")
        search_source = None if search_paper == "All papers" else search_paper

        if st.button("🔎 Search", use_container_width=True) and search_query.strip():
            with st.spinner("Searching…"):
                data, err = api_post(
                    "query",
                    {
                        "question": search_query,
                        "top_k": search_topk,
                        "filter_source": search_source,
                    },
                )
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")

    with sub_explain:
        st.caption(
            "Enter a concept, term, equation, diagram description, or table name "
            "to get a detailed explanation grounded in the uploaded papers."
        )
        concept = st.text_input(
            "Concept / term / diagram",
            placeholder="e.g. cross-attention, Figure 3, Table 2 results, BLEU score",
        )
        explain_paper = st.selectbox(
            "Filter to paper (optional)",
            ["All papers"] + [d["filename"] for d in st.session_state.documents if d["status"] == "completed"],
            key="explain_paper",
        )
        explain_source = None if explain_paper == "All papers" else explain_paper

        if st.button("💡 Explain", use_container_width=True) and concept.strip():
            with st.spinner(f"Explaining '{concept}'…"):
                data, err = api_post(
                    "explain",
                    {"concept": concept, "source_file": explain_source},
                )
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")


# ===========================================================================
# TAB 5 — Trends & Recommendations
# Covers: research trend analysis, related paper recommendation,
#         summarization
# ===========================================================================

with tab5:
    st.markdown("#### 📈 Trends & Recommendations")

    sub_trends, sub_recommend, sub_summary = st.tabs([
        "📈 Research Trends",
        "🌟 Paper Recommendations",
        "📋 Summarize",
    ])

    with sub_trends:
        st.caption(
            "Analyse methodological trends, performance evolution, "
            "and emerging research directions across all uploaded papers."
        )
        if st.button("📈 Analyse Research Trends", use_container_width=True):
            with st.spinner("Analysing trends across all papers…"):
                data, err = api_post("trends", {}, timeout=180)
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")

    with sub_recommend:
        st.caption(
            "Describe your research interest and get recommendations "
            "for the most relevant uploaded papers."
        )
        interest = st.text_area(
            "Your research interest",
            placeholder="e.g. I'm interested in retrieval-augmented generation for scientific documents",
            height=100,
        )
        if st.button("🌟 Get Recommendations", use_container_width=True) and interest.strip():
            with st.spinner("Finding the best papers for your interest…"):
                data, err = api_post("recommend", {"interest": interest})
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")

    with sub_summary:
        st.caption("Generate a concise structured summary of one or all uploaded papers.")
        summary_paper = st.selectbox(
            "Paper to summarize",
            ["All papers"] + [d["filename"] for d in st.session_state.documents if d["status"] == "completed"],
            key="summary_paper",
        )
        summary_source = None if summary_paper == "All papers" else summary_paper

        if st.button("📋 Summarize", use_container_width=True):
            with st.spinner(f"Summarizing {'all papers' if not summary_source else summary_source}…"):
                data, err = api_post(
                    "summarize",
                    {"source_file": summary_source, "top_k": 20},
                )
            if err:
                st.error(err)
            else:
                st.markdown(data["answer"])
                render_citations(data.get("citations", []))
                st.caption(f"Chunks used: {data['chunks_used']}")
