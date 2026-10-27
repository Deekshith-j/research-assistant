"""Streamlit UI for the Asterline research assistant.

Launch:  streamlit run app.py

Layout
  Sidebar  - user selector (synthetic demo users), conversation list, system status
  Chat tab - conversation with sources, warnings and the agent trace per answer
  Memory   - inspect / add / edit / delete what is remembered about the selected user
"""

from __future__ import annotations

import os

import streamlit as st

from assistant.llm import llm_available
from assistant.memory.store import MemoryRejected
from assistant.service import AssistantService

# Synthetic demo users (the assignment asks for synthetic user data only).
DEMO_USERS = {
    "alice": "Alice - Support engineer",
    "bob": "Bob - Solutions architect",
    "carol": "Carol - Engineering manager",
}

st.set_page_config(page_title="Asterline Research Assistant", page_icon=":mag:", layout="wide")


@st.cache_resource(show_spinner="Loading local embedding model and vector index (first run downloads ~130 MB)...")
def get_service() -> AssistantService:
    """One service per process: the embedding model and graph are loaded only once."""
    return AssistantService()


service = get_service()


# ============================================================================ sidebar
with st.sidebar:
    st.header("Asterline Assistant")

    # --- User selector: switching user switches every piece of stored context ---
    user_id = st.selectbox("Signed in as (demo)", list(DEMO_USERS), format_func=DEMO_USERS.get)
    user = service.user(user_id)
    if st.session_state.get("user_id") != user_id:
        st.session_state.user_id = user_id
        st.session_state.session_id = None  # never carry a session over to another user

    # --- Conversations of this user ---
    st.subheader("Conversations")
    if st.button("+ New conversation", width="stretch"):
        st.session_state.session_id = user.create_session().id

    sessions = user.list_sessions()
    if sessions and not st.session_state.get("session_id"):
        st.session_state.session_id = sessions[0].id  # resume the latest one (continuity)
    if not sessions:
        st.session_state.session_id = user.create_session().id
        sessions = user.list_sessions()

    labels = {s.id: f"{s.title}  ·  {s.updated_at[:10]}" for s in sessions}
    st.session_state.session_id = st.radio(
        "Pick a conversation", list(labels), format_func=labels.get,
        index=list(labels).index(st.session_state.session_id) if st.session_state.session_id in labels else 0,
        label_visibility="collapsed",
    )
    if st.button("Delete this conversation", width="stretch"):
        user.delete_session(st.session_state.session_id)
        st.session_state.session_id = None
        st.rerun()

    # --- Status of external services ---
    st.divider()
    st.caption("Status")
    st.write(("✅" if llm_available() else "❌") + " Groq LLM key")
    tracing = os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(os.getenv("LANGSMITH_API_KEY"))
    st.write(("✅" if tracing else "⚪") + f" LangSmith tracing ({os.getenv('LANGSMITH_PROJECT', 'default')})")


session_id: str = st.session_state.session_id
chat_tab, memory_tab = st.tabs(["💬 Chat", "🧠 Memory"])


# ============================================================================ chat tab
def show_text(text: str) -> None:
    """Render chat text as Markdown with dollar signs escaped.

    Streamlit treats text between two '$' as LaTeX, which swallowed prices such as
    "$175 ... $140" (found during the browser check).
    """
    st.markdown(text.replace("$", r"\$"))


def render_answer_details(meta: dict) -> None:
    """Sources, warnings and the agent trace under an assistant message."""
    for w in meta.get("warnings", []):
        st.warning(w)
    if meta.get("citations"):
        with st.expander(f"Sources ({len(meta['citations'])})"):
            for c in meta["citations"]:
                st.markdown(f"- `{c['chunk_id']}` — **{c['title']}** (published {c['published']})")
    if meta.get("trace"):
        with st.expander("Agent trace"):
            st.code("\n".join(meta["trace"]), language="text")


with chat_tab:
    if not llm_available():
        st.error("No GROQ_API_KEY found. Copy `.env.example` to `.env`, add a free key from "
                 "https://console.groq.com and restart. Retrieval still works without it.")

    # Replay the stored conversation (survives app restarts).
    for msg in user.get_messages(session_id):
        with st.chat_message(msg.role):
            show_text(msg.content)
            if msg.role == "assistant":
                render_answer_details(msg.meta)

    if prompt := st.chat_input("Ask about Asterline docs, or tell me what to remember / forget"):
        with st.chat_message("user"):
            show_text(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Agents are researching..."):
                result = service.ask(user_id, session_id, prompt)
            show_text(result.answer)
            render_answer_details({"warnings": result.warnings, "citations": result.citations,
                                   "trace": result.trace})
            st.caption(f"status: {result.status} · {result.latency_s}s")
        st.rerun()  # refresh sidebar title + replay from storage


# ============================================================================ memory tab
with memory_tab:
    st.subheader(f"What I remember about {DEMO_USERS[user_id].split(' - ')[0]}")
    st.caption("Memories personalise answers but are never used as evidence for company facts. "
               "Only this user can see them.")

    memories = user.list_memories()
    if not memories:
        st.info("Nothing remembered yet. Tell me things like “I support EU customers on the Team plan”.")

    # Each memory: editable text (= correction), delete (= forget).
    for m in memories:
        col_text, col_save, col_del = st.columns([6, 1, 1])
        new_text = col_text.text_input(f"{m.kind} · {m.id}", value=m.content, key=f"mem_{m.id}")
        if col_save.button("Save", key=f"save_{m.id}") and new_text.strip() != m.content:
            try:
                user.correct_memory(m.id, new_text)
                st.rerun()
            except MemoryRejected as exc:
                st.error(f"Not saved: {exc}")
        if col_del.button("Forget", key=f"del_{m.id}"):
            user.forget_memory(m.id)
            st.rerun()

    with st.form("add_memory", clear_on_submit=True):
        st.markdown("**Add a memory manually**")
        kind = st.selectbox("Kind", ["profile", "preference", "work_context"])
        text = st.text_input("Content")
        if st.form_submit_button("Remember") and text.strip():
            try:
                user.add_memory(kind, text, source_session=session_id)
                st.rerun()
            except MemoryRejected as exc:
                st.error(f"Not saved: {exc}")

    if memories and st.button("Forget everything about me", type="primary"):
        user.forget_all()
        st.rerun()

    with st.expander("Correction history and audit log"):
        superseded = [m for m in user.list_memories(include_superseded=True) if m.status == "superseded"]
        st.markdown("**Superseded (corrected) memories** — kept until you forget them, never used by the agents.")
        for m in superseded:
            st.markdown(f"- ~~{m.content}~~ ({m.updated_at[:16]})")
        st.markdown("**Recent memory events** — forgotten content is not kept.")
        st.dataframe(user.memory_events(), width="stretch")
