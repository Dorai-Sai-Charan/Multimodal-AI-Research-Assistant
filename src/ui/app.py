"""
Streamlit UI for the Multimodal AI Research Assistant.
Provides a chat interface with document upload capabilities.
"""

import streamlit as st
import requests
import os

# Backend API URL
API_URL = os.getenv("API_URL", "http://localhost:8000/api")

# --- Page Configuration ---
st.set_page_config(
    page_title="🔬 AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #888;
        margin-bottom: 2rem;
    }
    .citation-box {
        background-color: #1e1e2e;
        border-left: 4px solid #764ba2;
        padding: 10px 15px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.85rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #1e1e2e, #2d2d3f);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #333;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #764ba2;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #888;
    }
    .doc-card {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 8px 0;
        border: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)


# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "documents" not in st.session_state:
    st.session_state.documents = []


def refresh_documents():
    """Fetch document list from the API."""
    try:
        resp = requests.get(f"{API_URL}/documents", timeout=10)
        if resp.status_code == 200:
            st.session_state.documents = resp.json()
    except requests.exceptions.ConnectionError:
        st.session_state.documents = []


# --- Sidebar ---
with st.sidebar:
    st.markdown('<p class="main-header">🔬 Research Assistant</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Upload papers & ask questions</p>', unsafe_allow_html=True)

    # File Upload
    st.markdown("### 📄 Upload Documents")
    uploaded_file = st.file_uploader(
        "Upload a research paper (PDF)",
        type=["pdf"],
        help="Upload PDF files to analyze",
    )

    if uploaded_file is not None:
        if st.button("📥 Process Document", use_container_width=True):
            with st.spinner("🔄 Ingesting document... This may take a moment."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    resp = requests.post(f"{API_URL}/upload", files=files, timeout=120)
                    if resp.status_code == 200:
                        result = resp.json()
                        st.success(
                            f"✅ **{result['filename']}** processed!\n\n"
                            f"📄 Pages: {result['total_pages']} | "
                            f"🧩 Chunks: {result['total_chunks']}"
                        )
                        refresh_documents()
                    else:
                        st.error(f"❌ Upload failed: {resp.json().get('detail', 'Unknown error')}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to the API server. Make sure it's running on port 8000.")

    st.divider()

    # Document List
    st.markdown("### 📚 Uploaded Documents")
    refresh_documents()

    if st.session_state.documents:
        for doc in st.session_state.documents:
            status_emoji = "✅" if doc["status"] == "completed" else "⏳" if doc["status"] == "processing" else "❌"
            with st.container():
                st.markdown(
                    f'<div class="doc-card">'
                    f'{status_emoji} <strong>{doc["filename"]}</strong><br>'
                    f'<span style="color:#888">📄 {doc["total_pages"]} pages | 🧩 {doc["total_chunks"]} chunks</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("No documents uploaded yet. Upload a PDF to get started!")

    st.divider()

    # Stats
    st.markdown("### 📊 Stats")
    total_docs = len(st.session_state.documents)
    total_chunks = sum(d.get("total_chunks", 0) for d in st.session_state.documents)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{total_docs}</div>'
            f'<div class="stat-label">Documents</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="stat-card"><div class="stat-value">{total_chunks}</div>'
            f'<div class="stat-label">Chunks</div></div>',
            unsafe_allow_html=True,
        )


# --- Main Chat Interface ---
st.markdown('<p class="main-header">🔬 Multimodal AI Research Assistant</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">'
    "Ask questions about your research papers. I'll find answers with citations."
    "</p>",
    unsafe_allow_html=True,
)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "citations" in message and message["citations"]:
            with st.expander("📎 Sources & Citations"):
                for citation in message["citations"]:
                    section_text = f" — Section: {citation['section']}" if citation.get("section") else ""
                    st.markdown(
                        f'<div class="citation-box">'
                        f'📄 **{citation["source_file"]}** — Page {citation["page_number"]}'
                        f'{section_text}'
                        f' (Relevance: {citation["relevance_score"]:.1%})'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

# Chat input
if prompt := st.chat_input("Ask a question about your research papers..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("🧠 Thinking..."):
            try:
                # Detect if summarize request
                is_summarize = any(
                    kw in prompt.lower()
                    for kw in ["summarize", "summary", "overview", "key points"]
                )

                if is_summarize:
                    resp = requests.post(
                        f"{API_URL}/summarize",
                        json={"top_k": 20},
                        timeout=60,
                    )
                else:
                    resp = requests.post(
                        f"{API_URL}/query",
                        json={"question": prompt, "top_k": 10},
                        timeout=60,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    st.markdown(data["answer"])

                    # Show citations
                    if data.get("citations"):
                        with st.expander("📎 Sources & Citations"):
                            for citation in data["citations"]:
                                section_text = f" — Section: {citation['section']}" if citation.get("section") else ""
                                st.markdown(
                                    f'<div class="citation-box">'
                                    f'📄 **{citation["source_file"]}** — Page {citation["page_number"]}'
                                    f'{section_text}'
                                    f' (Relevance: {citation["relevance_score"]:.1%})'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                    # Save assistant message
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": data["answer"],
                        "citations": data.get("citations", []),
                    })

                    # Show metadata
                    st.caption(f"📊 Used {data['chunks_used']} chunks | Intent: {data['intent']}")
                else:
                    error_msg = f"❌ Error: {resp.json().get('detail', 'Unknown error')}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except requests.exceptions.ConnectionError:
                error_msg = "❌ Cannot connect to the API server. Make sure it's running with `python -m src.main`"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
