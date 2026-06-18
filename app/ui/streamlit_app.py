"""Streamlit UI — Enterprise Advanced RAG Copilot."""

import streamlit as st
import httpx
import asyncio
import json

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="K8s SRE Copilot",
    page_icon="⎈",
    layout="wide",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_sql" not in st.session_state:
    st.session_state.pending_sql = None
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())


def get_token(username: str, password: str) -> str | None:
    try:
        r = httpx.post(f"{API_BASE}/auth/token", json={"username": username, "password": password})
        if r.status_code == 200:
            return r.json()["access_token"]
    except Exception:
        pass
    return None


def ask(query: str) -> dict:
    r = httpx.post(
        f"{API_BASE}/chat",
        json={"query": query, "session_id": st.session_state.session_id},
        headers={"Authorization": f"Bearer {st.session_state.token}"},
        timeout=60,
    )
    return r.json()


def approve_sql(approved: bool) -> dict:
    r = httpx.post(
        f"{API_BASE}/sql/approve",
        json={"session_id": st.session_state.session_id, "approved": approved},
        headers={"Authorization": f"Bearer {st.session_state.token}"},
        timeout=60,
    )
    return r.json()


def health_check() -> dict:
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        return r.json()
    except Exception:
        return {"status": "unreachable", "qdrant": False, "postgres": False, "redis": False}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⎈ K8s SRE Copilot")
    st.caption("Enterprise Advanced RAG")
    st.divider()

    # Auth
    if not st.session_state.token:
        st.subheader("🔐 Login")
        username = st.text_input("Username", value="sre-admin")
        password = st.text_input("Password", type="password", value="sre-secret")
        if st.button("Login", use_container_width=True):
            token = get_token(username, password)
            if token:
                st.session_state.token = token
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Login failed")
    else:
        st.success("✅ Authenticated")
        if st.button("Logout", use_container_width=True):
            st.session_state.token = None
            st.rerun()

    st.divider()

    # Health status
    st.subheader("🩺 System Health")
    if st.button("Check Health", use_container_width=True):
        h = health_check()
        st.json(h)

    st.divider()

    # Info
    st.subheader("📚 Architecture")
    st.markdown("""
- **LangGraph** State Machine
- **HyDE** → Hybrid Retrieval
- **RRF** → Cross-Encoder Rerank
- **CRAG** → Web Fallback (Tavily)
- **Self-RAG** Reflection Loop
- **Text2SQL** + HITL Approval
- **5-Tier Redis** Cache
- **9-Layer** Guardrails
    """)

    if st.button("🗑 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_sql = None
        st.rerun()


# ── Main area ─────────────────────────────────────────────────────────────────
st.title("⎈ Kubernetes SRE Copilot")
st.caption("Ask anything about your cluster — docs, metrics, troubleshooting")

# Show chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            with st.expander("📊 Metadata"):
                st.json(msg["meta"])

# SQL Approval widget
if st.session_state.pending_sql:
    st.warning("⚠️ SQL query requires your approval before execution:")
    st.code(st.session_state.pending_sql, language="sql")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve & Execute", use_container_width=True):
            result = approve_sql(True)
            st.session_state.pending_sql = None
            answer = result.get("answer", "")
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "meta": result.get("metadata"),
            })
            st.rerun()
    with col2:
        if st.button("❌ Reject", use_container_width=True):
            approve_sql(False)
            st.session_state.pending_sql = None
            st.session_state.messages.append({
                "role": "assistant",
                "content": "SQL execution was cancelled.",
            })
            st.rerun()

# Chat input
if not st.session_state.token:
    st.info("👈 Please log in from the sidebar to start chatting.")
else:
    query = st.chat_input("Ask about your K8s cluster...")
    if query:
        # Show user message
        st.session_state.messages.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        # Call API
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = ask(query)
                    answer = result.get("answer", "No answer returned.")
                    meta = result.get("metadata", {})
                    intent = result.get("intent", "rag")

                    # Intent badge
                    badge = {"rag": "🔍 RAG", "sql": "🗄 SQL", "hybrid": "🔀 Hybrid"}.get(intent, intent)
                    st.caption(badge)

                    st.markdown(answer)

                    # Sources
                    sources = result.get("sources", [])
                    if sources:
                        with st.expander(f"📎 Sources ({len(sources)})"):
                            for s in sources:
                                st.write(f"- `{s.get('source', 'unknown')}` (score: {s.get('score', 0):.3f})")

                    # Metadata
                    if meta:
                        with st.expander("📊 Pipeline Metadata"):
                            st.json(meta)

                    # HITL SQL approval
                    if result.get("sql_pending_approval"):
                        st.session_state.pending_sql = result.get("generated_sql")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "meta": meta,
                    })

                except Exception as e:
                    err = f"❌ API error: {e}"
                    st.error(err)
                    st.session_state.messages.append({"role": "assistant", "content": err})
