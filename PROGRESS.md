# Project Progress Log

Tracks what has been done on the Batch 5 assignment ("A research assistant that remembers").

## Assignment summary (from the PDF)

Build a **multi-agent research assistant** for the fictional company *Asterline Labs* that:

| Requirement | What it means for us |
|---|---|
| Trustworthy research | Answer only from `corpus.jsonl`, cite chunk IDs + titles, handle conflicts (dates / supersession) and missing info honestly |
| Multi-agent (≥3) | Agents with distinct responsibilities, visible in the LangSmith trace |
| Continuity | Follow-up questions + memory that survives app restart |
| Thoughtful memory | Decide what to store / not store (no secrets), support corrections and "forget", strict per-user isolation |
| Usability | Simple chat UI + a page to view/manage remembered memories, user selector |
| Constraints | Local embeddings + local vector store, LangSmith tracing, no secrets in code/memory/traces, one launch command, handle provider failures / rate limits |
| Memory ≠ evidence | A remembered statement is never proof of a company fact |

**Deliverables:** working repo (unchanged corpus, setup, deps, `.env.example`), design note with architecture diagram + limitations, reproducible evaluation (research + memory) with failures and one improvement, LangSmith links (success + failure case), AI-use disclosure.

**Grading:** Memory 25% · Grounded research 20% · Multi-agent 15% · Evaluation 20% · Observability 10% · Code quality 10%.

## Decisions

| Topic | Choice | Why |
|---|---|---|
| Generation model | Groq free tier: `openai/gpt-oss-120b` (Analyst, Verifier) + `openai/gpt-oss-20b` (Coordinator, Memory Agent, fallback). The Llama models first planned were retired on Groq | Free, fast, no card; two tiers save the daily token budget |
| Embeddings | `BAAI/bge-small-en-v1.5` via fastembed (ONNX, CPU) | Local, light (no PyTorch), good quality |
| Vector store | Chroma (persistent, `storage/chroma`) + BM25, fused with RRF | Local; BM25 catches exact IDs like `INC-2025-12`, `2.3.1` |
| Orchestration | LangGraph | Explicit graph, every node traced in LangSmith |
| Memory store | SQLite, every query scoped by `user_id` | Survives restarts, simple to inspect, isolation by construction |
| UI | React + TypeScript (Vite) served by FastAPI (replaced the first Streamlit version) | Dedicated frontend; built files committed so `python run.py` is still the only launch command |

## Done

- [x] Read and analysed the full assignment PDF (22 pages)
- [x] Extracted the original, unchanged `corpus.jsonl` (75 chunks / 25 docs) into `data/`
- [x] Chose the stack (see Decisions), created `.venv`, installed dependencies
- [x] `assistant/config.py`: all settings from `.env`
- [x] `assistant/redaction.py`: secrets removed before LLM / DB / traces
- [x] `assistant/llm.py`: Groq with retries (honours 429 Retry-After), main → fast fallback, typed outputs
- [x] `assistant/knowledge/`: corpus loader + hybrid retriever (Chroma + BM25 + RRF), auto-rebuilds if the corpus changes
- [x] `assistant/memory/`: SQLite store (sessions, messages, memories, audit), policy gate, correct = supersede, forget = hard delete + audit scrub
- [x] Agents: Memory Agent, Coordinator, Research Agent, Analyst, Verifier, Responder
- [x] `assistant/graph.py`: LangGraph workflow with a parallel step and bounded revise / re-research loops
- [x] `assistant/service.py`: one entry point for UI and evaluation
- [x] `app.py`: Streamlit chat, sources, agent trace, memory tab (edit / forget / forget all / audit)
- [x] `requirements.txt`, `.env.example`, `.gitignore`
- [x] Unit tests: 18 passing (isolation, correction, forget, policy, redaction, citation rules)
- [x] Smoke test: index built (28 s first run), retrieval surfaces both sides of conflicts, offline fallback works when no key is set

- [x] Evaluation suite: 27 research cases (lookup, multi-hop, incident, conflict, temporal, false-premise, unanswerable) + 10 multi-turn memory scenarios
- [x] Retrieval eval (offline) run: vector recall@8 0.962, BM25 0.942, **hybrid 0.981**; vector-only misses INC-2025-12 cause entirely (R11), hybrid fixes it
- [x] `docs/DESIGN.md` (mermaid architecture diagram, agents, memory, trade-offs, limitations), `README.md`, `docs/AI_USE.md`
- [x] Streamlit app boots headlessly with no exceptions; requirements pinned to tested versions

- [x] Keys added to `.env` (git-ignored). Default Llama models were retired on Groq → switched to `openai/gpt-oss-120b` / `gpt-oss-20b`
- [x] LangSmith tracing verified (US endpoint), every turn = `assistant_turn` run with per-agent spans
- [x] **Baseline e2e eval**: research 16/27, memory 9/10, citations valid 27/27
- [x] Failure analysis → 4 root causes: full-width citation brackets (UI showed no sources), checker Unicode bugs, sibling chunk missed (R11), premature "not documented" (M03)
- [x] Fixes: citation normalisation (+ regression test), sibling expansion, "second look before abstaining", coordinator/verifier prompt tweaks, checker normalisation + `--rescore`
- [x] Rescored unchanged baseline answers with fixed checker: 26/27 → isolates checker vs system effects
- [x] Offline replay of planned queries: siblings 0.923 → 0.962 recall; down-weighting extra queries had no effect (rejected)
- [x] `git init` (`.env`, `storage/` ignored)

- [x] **Improved e2e eval (result of record)**: research 26/27, gold recall 0.96, citations valid 27/27, memory 10/10
- [x] Round-2 finding R16 (citations only in claims list, not inline) → stricter rule + regression test; targeted re-run 4/4
- [x] "Final" full re-run hit Groq's 200k tokens/day limit at R04 → app degraded gracefully; exposed a scorer flaw (fallback answers counted as passes) → fixed, rescored (improved run unchanged at 26/27)
- [x] `docs/EVALUATION.md`: metrics, results, failure analysis, improvements (incl. one rejected hypothesis), honest attribution, 9 LangSmith links (7 success, 2 failure)
- [x] Browser check: found & fixed `$` prices rendered as LaTeX; Memory tab add works; switching to Bob shows none of Alice's data; conversations persist across restarts
- [x] Pre-commit checks: 20 tests pass, real keys absent from repo, corpus byte-identical to PDF attachment

## To do

- [x] Committed and pushed to https://github.com/Deekshith-j/research-assistant (`.gitattributes` keeps the corpus byte-identical)
- [ ] User: share LangSmith project with radialpulse@nxtwave.co.in (LangSmith → Settings → Members, or share the project)
- [ ] User: push repo to GitHub, review `docs/AI_USE.md`, rotate the API keys after the review (they were pasted in chat)

## Dedicated frontend (replaces Streamlit)

- [x] `assistant/api.py`: FastAPI REST API, every route under `/api/users/{user}/...` and scoped via `Store.for_user`; foreign sessions return 404; policy rejections return 422
- [x] `run.py`: one command, warms up the retriever, serves API + built UI on http://localhost:8000
- [x] `frontend/`: React + TypeScript (Vite): sidebar (user selector, conversations, status), chat (citation chips, status badge, sources, agent trace, pending state), memory inspector (grouped by kind, edit = correction, forget, add, forget all, history + audit)
- [x] `tests/test_api.py`: 4 API tests (CRUD, 422 policy, unknown user, cross-user isolation) → 24 tests pass
- [x] Lint clean (oxlint), type-check + build pass; `dist/` committed so Node isn't needed to run
- [x] Browser check: live follow-up answered with citation; secret rejected in Memory form; Bob sees none of Alice's data; phone width (375 px) fixed (conversation list was hidden); light + dark mode
- [x] Removed `app.py` and Streamlit from requirements; README, DESIGN diagram updated

## Requirement audit + source-passage viewer

- [x] Audited every requirement and deliverable in the brief against the repo: all covered. Still on the user: LangSmith sharing, reviewing `docs/AI_USE.md`, rotating keys
- [x] Added **source-passage viewer**: click a citation chip or source → side panel with the verbatim corpus passage, date, version, category, source URL (`GET /api/chunks/{id}`, `SourcePanel.tsx`). Makes every claim verifiable in one click (grounded research = 20% of the grade)
- [x] API test for the chunk endpoint → 25 tests pass; lint clean; browser-checked (chip, Sources list, Esc, click-outside)
- [x] Design note: added a "User interface" paragraph (API scoping, badges, citation viewer, memory inspector)
