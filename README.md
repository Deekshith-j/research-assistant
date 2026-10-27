# Asterline Research Assistant

A multi-agent assistant that answers questions about the (fictional) Asterline Labs documentation with
**cited, grounded answers**, and **remembers selected context per user** across sessions.

- 5 cooperating agents in a LangGraph workflow: Memory Agent, Coordinator, Research Agent, Analyst, Verifier
- Local embeddings (fastembed `bge-small`) + local vector store (Chroma) + BM25 hybrid search
- Per-user memory in SQLite with correction, forgetting, a policy gate and strict user isolation
- React web UI (served by a FastAPI backend) with chat, citation chips, sources, agent trace, and a memory inspector
- LangSmith tracing of every agent step

Read the [design note](docs/DESIGN.md) for architecture and trade-offs, and [EVALUATION.md](docs/EVALUATION.md)
for results.

## Setup

Requirements: Python 3.10+ (tested on 3.11), internet for the first run (embedding model download) and for Groq.

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

Then edit `.env`:

| Variable | Where to get it | Cost |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | Free tier, no card. Limits apply (see below) |
| `LANGSMITH_API_KEY` | https://smith.langchain.com → Settings → API Keys | Free developer plan |

## Launch (one command)

```bash
python run.py
```

Then open http://localhost:8000. The first launch downloads the embedding model (~130 MB) and builds the vector
index (~30 s). Later launches reuse `storage/`. Pick a demo user in the sidebar (alice / bob / carol); each has
separate conversations and memories.

Node.js is **not** needed to run the app: the React UI is pre-built into `frontend/dist` and served by the Python
backend. API docs are at http://localhost:8000/docs.

### Changing the frontend (optional, needs Node.js 20+)

Keep `python run.py` running for the API, then in a second terminal:

```bash
cd frontend
```
```bash
npm install
```
```bash
npm run dev
```

Vite serves the UI with hot reload on http://localhost:5173 and forwards `/api` calls to port 8000.
Run `npm run build` to update `frontend/dist`, and `npm run lint` to lint.

### Things to try

- "What is the weekly on-call stipend?" → conflicting documents, newer handbook wins, both cited
- "What is the AQL timeout?" then "and in version 2.2?" → follow-up
- "I support EU customers on the Team plan" → open the **Memory** tab; start a new conversation and ask
  "How long are my customers' run records searchable?"
- "Correction: they're on Enterprise now" / "Forget what plan my customers use" / "What do you remember about me?"
- Switch to another user → none of the first user's memories are visible

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

`pytest` and the retrieval evaluation need no API key. The end-to-end evaluation calls Groq. One full run uses roughly
100k tokens on the fast model, and the free tier allows 200k per model per day, so plan on **about one full run per day**.
Use `--suite research|memory`, `--only R16 M04`, and `--delay 3` for smaller runs.

## Project layout

```
run.py                      entry point: API + web UI on port 8000
assistant/
  api.py                    FastAPI REST API (per-user routes) + serves the built UI
  config.py                 settings from .env
  redaction.py              secret removal before LLM / storage / traces
  llm.py                    Groq access: retries, fallback, typed outputs
  service.py                one conversation turn (used by UI and eval)
  graph.py                  LangGraph wiring of the agents
  agents/                   memory_agent, coordinator, researcher, analyst, verifier, responder, prompts
  knowledge/                corpus loader + hybrid retriever (Chroma + BM25)
  memory/                   SQLite store (per-user) + storage policy
frontend/                   React + TypeScript (Vite)
  src/App.tsx               shell: user, conversation and tab state
  src/api.ts, types.ts      typed client for the REST API
  src/components/           Sidebar, ChatView, AnswerMessage (citations), MemoryPanel
  dist/                     pre-built UI served by run.py (committed)
data/corpus.jsonl           the unchanged corpus (75 chunks)
eval/                       test cases, scenarios, runners, results
tests/                      unit tests (no API key needed)
docs/                       design note, evaluation report, AI-use disclosure
```

## Costs and limits

Everything runs locally except the LLM calls (Groq) and trace upload (LangSmith), both on free plans. Groq's free tier
limits requests and tokens per minute/day per model; the app retries on HTTP 429 (honouring `Retry-After`), falls back
to the second model, and finally shows the top cited passages instead of failing. To use other Groq models, set
`GROQ_MAIN_MODEL` / `GROQ_FAST_MODEL` in `.env`.

## Privacy notes

All demo users and data are synthetic. Secrets typed into the chat are replaced with `[REDACTED_SECRET]` before they
reach the model, the database or LangSmith. `.env` and `storage/` are git-ignored.
