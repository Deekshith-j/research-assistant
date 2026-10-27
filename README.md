# Asterline Research Assistant

A multi-agent assistant that answers questions about the Asterline Labs documentation with cited, grounded answers,
and remembers selected context per user across sessions.

- **Grounded answers.** Every fact is cited by chunk ID and title. Conflicting documents are resolved by date, scope
  and explicit supersession, and missing information is stated rather than guessed.
- **Five agents** (LangGraph): Memory Agent, Coordinator, Research Agent, Analyst, Verifier.
- **Per-user memory.** Remembers profile, preferences and ongoing work, with correction, forgetting and strict user
  isolation. Secrets and sensitive data are never stored, and memory is never used as evidence.
- **Local retrieval.** fastembed `bge-small` embeddings, a Chroma vector store and BM25 keyword search.
- **Web UI.** Chat with clickable citations, an agent-trace timeline, and a memory manager.
- **Tracing.** Every agent step is traced in LangSmith.

## Setup

Requirements: Python 3.10+ (tested on 3.11). Internet access is needed on the first run (to download the embedding
model) and for the Groq API.

```bash
python -m venv .venv
```
```bash
.venv\Scripts\activate
```
(macOS/Linux: `source .venv/bin/activate`)
```bash
pip install -r requirements.txt
```
```bash
copy .env.example .env
```
(macOS/Linux: `cp .env.example .env`)

Add your keys to `.env`:

| Variable | Where to get it | Cost |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | Free tier, no card (rate limits apply) |
| `LANGSMITH_API_KEY` | https://smith.langchain.com → Settings → API Keys | Free developer plan |

## Run

```bash
python run.py
```

Open http://localhost:8000.
- The first launch downloads the embedding model (~130 MB) and builds the vector index (~30 s).
- Pick a demo user in the sidebar (alice / bob / carol); each has separate conversations and memories.
- API docs are at http://localhost:8000/docs.

### Examples

| Ask | What happens |
|---|---|
| "What is the weekly on-call stipend?" | The newer handbook ($175) supersedes the runbook ($140); both are cited |
| "What is the AQL timeout?" → "and in version 2.2?" | The follow-up question is resolved from the conversation |
| "When will the Asia-Pacific region launch?" | It states that no date has been announced |
| "I support EU customers on the Team plan", then in a new conversation: "How long are my customers' run records searchable?" | The memory is used: 180 days, cited from the documents |
| "Correction: they're on Enterprise now" / "What do you remember about me?" / "Forget what plan my customers use" | The memory is corrected, listed, then deleted (also possible in the **Memory** tab) |

## How it works

```
Message → redact secrets → Memory Agent (recall) → [Memory Agent (update) ‖ Coordinator (route + plan)]
        → Research Agent (hybrid retrieval) → Analyst (cited draft) → Verifier ─┬─ pass → answer + sources
                                                   ↑ revise ────────────────────┤
                         ↑ retrieve more ───────────────────────────────────────┘
```

| Agent | Role |
|---|---|
| Memory Agent | Recalls the user's memories; decides what to add, correct or forget |
| Coordinator | Routes the message; rewrites follow-ups into standalone questions; plans searches |
| Research Agent | Retrieves evidence (vector + BM25, fused with RRF, plus neighbouring chunks) |
| Analyst | Writes the answer from evidence only, with inline `[chunk_id]` citations |
| Verifier | Checks every citation and claim; sends the draft back for revision or more retrieval |

- **Memory vs evidence.** User memories are shown to the agents as context, never as evidence. Only corpus chunks can
  be cited.
- **Storage policy.** It is enforced in code (`assistant/memory/policy.py`): no credentials, sensitive personal data
  or company facts.
- **Corrections and forgetting.** A correction keeps a superseded copy visible in the Memory tab. Forgetting
  permanently deletes the memory and its history.
- **Isolation.** All data access goes through `Store.for_user(user_id)`.
- **Reliability.** Rate-limited or failing models are retried, then replaced by a fallback model. If none are
  available, the most relevant cited passages are shown, and memory viewing and "forget everything" keep working.

More detail: [docs/DESIGN.md](docs/DESIGN.md).

## Tests and evaluation

```bash
python -m pytest -q
```
```bash
python -m eval.run_retrieval_eval
```
```bash
python -m eval.run_eval
```
```bash
python -m eval.run_acceptance
```

| Command | Covers | Needs API key |
|---|---|---|
| `pytest` | Memory isolation, corrections, forgetting, storage policy, secret redaction, citation rules, API, offline memory | No |
| `eval.run_retrieval_eval` | Retrieval recall: vector vs BM25 vs hybrid | No |
| `eval.run_eval` | 27 research questions and 10 multi-turn memory scenarios | Yes |
| `eval.run_acceptance` | 15-turn, 3-user conversation including an app restart | Yes |

Results and analysis: [docs/EVALUATION.md](docs/EVALUATION.md).

## Configuration

All settings are read from `.env`; see `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_MAIN_MODEL` | `openai/gpt-oss-120b` | Analyst and Verifier |
| `GROQ_FAST_MODEL` | `openai/gpt-oss-20b` | Coordinator and Memory Agent |
| `GROQ_FALLBACK_MODELS` | `qwen/qwen3.8-27b` | Used when the models above are rate-limited |
| `LANGSMITH_PROJECT` | `asterline-research-assistant` | LangSmith project for traces |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Local embedding model |
| `RETRIEVAL_TOP_K` | `8` | Chunks retrieved per search |

Groq's free tier limits each model to about 200k tokens per day.

## Project structure

```
run.py                      starts the API and web UI on port 8000
assistant/
  api.py                    REST API; serves the built UI
  service.py                runs one conversation turn
  graph.py                  connects the agents (LangGraph)
  agents/                   the agents, prompts and memory-intent rules
  knowledge/                corpus loading and hybrid retrieval
  memory/                   per-user SQLite store and storage policy
  llm.py                    Groq access with retries and fallback
  redaction.py              removes secrets from user messages
  config.py                 settings
frontend/                   React + TypeScript UI (dist/ is pre-built)
data/corpus.jsonl           knowledge base (75 chunks, 25 documents)
eval/                       evaluation cases, scripts and results
tests/                      unit and API tests
docs/                       design and evaluation notes
```

### Frontend development

The built UI in `frontend/dist` is served by `python run.py`, so Node.js is only needed to change the UI. Keep
`python run.py` running, then in a second terminal:

```bash
cd frontend
```
```bash
npm install
```
```bash
npm run dev
```

The dev server runs on http://localhost:5173 with hot reload. Run `npm run build` to update `frontend/dist`.

## Notes

- Runs locally. The user selector simulates separate users; there is no authentication.
- All users and data are synthetic. `.env` and `storage/` are git-ignored.
