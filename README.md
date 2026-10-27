# Asterline Research Assistant

**Batch 5 take-home: "A research assistant that remembers".** A multi-agent assistant that helps Asterline Labs
employees get trustworthy, cited answers from the company documentation, and that remembers selected context per user
across sessions and restarts.

- **Grounded answers.** Every fact is cited by chunk ID and title. Conflicts are resolved by date, scope and explicit
  supersession, and gaps are admitted rather than guessed.
- **5 cooperating agents** (LangGraph): Memory Agent, Coordinator, Research Agent, Analyst, Verifier. Each one is a
  visible step in LangSmith.
- **Per-user memory.** Selective storage, corrections, forgetting, a policy gate (no secrets or sensitive data) and
  strict user isolation. Memory is never used as evidence.
- **Local retrieval.** fastembed `bge-small` embeddings, a Chroma vector store and BM25, fused with RRF.
- **Web UI.** Chat with clickable citations that open the source passage, an agent-trace timeline, and a memory
  inspector to view, correct and forget memories.

## Submission contents

The table maps each item in the brief's "What to submit" list to where it is.

| # | Brief asks for | Where |
|---|---|---|
| 1 | Working repository: code, unchanged corpus, setup, dependencies, env example without secrets | This repo · [`data/corpus.jsonl`](data/corpus.jsonl) (byte-identical to the supplied file) · [Setup](#setup) · [`requirements.txt`](requirements.txt) · [`.env.example`](.env.example) |
| 2 | Short design note: agents, information flow, memory, trade-offs, architecture diagram, limitations | [`docs/DESIGN.md`](docs/DESIGN.md) (summary [below](#design-in-brief)) |
| 3 | Evidence that it works: reproducible evaluation, results, failures, one improvement | [`docs/EVALUATION.md`](docs/EVALUATION.md) · [`eval/`](eval/) · results in [`eval/results/`](eval/results/) (summary [below](#evaluation-in-brief)) |
| 4 | Inspectable runs: LangSmith access + links to a success and a difficult/failed case | [LangSmith section](#langsmith-traces) |
| 5 | AI-use disclosure | [`docs/AI_USE.md`](docs/AI_USE.md) |

## Setup

Requirements: Python 3.10+ (tested on 3.11). Internet is needed on the first run (to download the embedding model)
and for the Groq API.

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

Then add your keys to `.env`:

| Variable | Where to get it | Cost / account |
|---|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys | Free tier, no card. Rate limits apply ([see below](#costs-and-limits)) |
| `LANGSMITH_API_KEY` | https://smith.langchain.com → Settings → API Keys | Free developer plan |

Embeddings, the vector store, memory and conversations all run locally and need no account.

## Launch (one command)

```bash
python run.py
```

Open http://localhost:8000.
- The first launch downloads the embedding model (~130 MB) and builds the vector index (~30 s). Later launches
  reuse `storage/`.
- Pick a demo user in the sidebar (alice / bob / carol); each has separate conversations and memories.
- Node.js is **not** needed: the React UI is pre-built into `frontend/dist` and served by the Python backend.
- API docs are at http://localhost:8000/docs.

**Deployment.** The brief states that a local demonstration is sufficient and that deployment and production
authentication are not required, so the app runs locally. The demo user selector simulates separate users and has
no real login, so the app should not be exposed publicly as is.

### Things to try

| Try | Shows |
|---|---|
| "What is the weekly on-call stipend?" | Conflicting documents: the newer handbook ($175) supersedes the runbook ($140); both cited |
| "What is the AQL timeout?" → "and in version 2.2?" | Follow-up questions and versioned facts |
| "When will the Asia-Pacific region launch?" | Honest "not announced", no guessing |
| "I support EU customers on the Team plan", then a **new conversation**: "How long are my customers' run records searchable?" | Memory across sessions: 180 days, personalised but cited from documents |
| "Correction: they're on Enterprise now" / "What do you remember about me?" / "Forget what plan my customers use" | Correct, inspect, forget (also possible in the **Memory** tab) |
| "Remember that Launch includes SAML SSO" | Memory is not evidence: the claim is not stored, and it is corrected with citations |
| Switch user in the sidebar | Isolation: nothing of the other user's context is visible |
| Click a citation chip | The verbatim source passage, with its date and version |

## Design in brief

```
Message → redact secrets → Memory Agent (recall) → [Memory Agent (update) ‖ Coordinator (route + plan)]
        → Research Agent (hybrid retrieval) → Analyst (cited draft) → Verifier ─┬─ pass → answer + sources
                                                   ↑ revise ────────────────────┤
                         ↑ retrieve more ───────────────────────────────────────┘
```

- **Agents.**
  - The Coordinator rewrites follow-ups into standalone questions and plans the searches.
  - The Research Agent retrieves evidence deterministically.
  - The Analyst answers only from the evidence, with inline `[chunk_id]` citations and supersession rules.
  - The Verifier checks every citation (by code and with an LLM) and can send the work back for a revision or more
    retrieval.
  - The Memory Agent decides what to add, correct or forget.
- **Memory vs evidence.** Prompts keep "USER CONTEXT – not evidence" separate from "EVIDENCE". Only retrieved corpus
  chunks can be cited.
- **What is remembered.** Profile, preferences and ongoing work. Never stored: secrets, sensitive personal data,
  company facts or previous answers. This is enforced in code (`memory/policy.py`), not just in the prompt.
- **Corrections and forgetting.** A correction keeps a superseded trail for the user's audit view. Forget is a hard
  delete, including the audit text.
- **Isolation.** Every query is scoped through `Store.for_user(user_id)`; the API cannot reach another user's data.
- **Reliability.** Retries, a 3-model fallback chain, a JSON-mode retry for malformed output, and cited-passage
  fallback answers. Memory viewing and "forget everything" work without the LLM.

Full architecture diagram, trade-offs and limitations: [`docs/DESIGN.md`](docs/DESIGN.md).

## Evaluation in brief

| Suite | What it measures | Result |
|---|---|---|
| Retrieval (offline, no LLM) | Recall of hand-labelled gold chunks, vector vs BM25 vs hybrid | Hybrid recall@8 **0.981** (vector 0.962, BM25 0.942) |
| Research, end to end | 27 questions: lookup, multi-hop, incident, conflict, temporal, false premise, unanswerable | **26/27** passed, citations valid 27/27, gold recall 0.96 |
| Memory, end to end | 10 multi-turn scenarios: recall, preference, correction, forget, isolation, secrets, sensitive data, memory ≠ evidence, follow-up, forget all | **10/10** |
| Acceptance walkthrough | 15 unseen turns, 3 users, mid-session restart, one per brief requirement | **15/15** after fixes |
| Unit/API tests | Isolation, corrections, forget + audit scrub, policy, redaction, citation rules, offline memory | **37 pass** |

**Failures found and the improvements they drove** (details in [`docs/EVALUATION.md`](docs/EVALUATION.md)):
- **Baseline: 16/27.** Reading every failure gave four root causes:
  - a citation-format bug that hid the Sources list;
  - checker bugs (Unicode spacing in numbers);
  - an answer split across chunks (R11);
  - an abstention accepted too early (M03).
- **Fixes:** citation normalisation, sibling-chunk expansion (recall 0.923 → 0.962 when replaying the real query
  plans offline), and a "second look before abstaining" rule.
- **Rejected hypothesis:** down-weighting the planner's extra queries made no difference.
- **Acceptance test:** it then found three more gaps:
  - memory requests depended on the LLM;
  - a correction with empty text was silently lost;
  - the fallback model failed tool calling.

  All three are fixed and covered by tests.

Reproduce:

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

`pytest` and the retrieval evaluation need no API key. The end-to-end evaluation uses roughly 100k Groq tokens per
full run (free tier: 200k per model per day). Use `--suite research|memory`, `--only R16 M04` or `--delay 3` for
smaller runs.

## LangSmith traces

- **Project:** `asterline-research-assistant` ([project link](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7)).
  Access is granted to radialpulse@nxtwave.co.in.
- **Structure:** each conversation turn is a root run `assistant_turn`, with `user_id` and `session_id` metadata.
  Child spans: `recall_memories` → `update_memories` ‖ `plan` → `research` (`hybrid_search`) → `analyse` → `verify`
  → `finalize_*`. Each LLM call is labelled with the model and mode it used.

| Run | What it shows |
|---|---|
| [Conflict resolved](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dda-155a-77b2-8152-8c6af8608833) | ✅ Stipend $175 supersedes $140; both sources cited |
| [Memory used across sessions](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de1-2ea1-7156-8fb2-b8ac93969e93) | ✅ "My customers" resolved to Enterprise from memory → 540 days, cited from documents |
| [Unanswerable question](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dde-bd33-733b-8772-a97142d9f00d) | ✅ Verifier forces a second search before accepting "not documented" |
| [Secret redacted](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de2-634c-760d-a2a9-b64923c3ae32) | ✅ The traced input shows `[REDACTED_SECRET]`, never the key |
| [Isolation](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de2-395f-75b2-a2b3-aea7bd34b5ff) | ✅ Bob asks about "his" customer and gets nothing of Alice's |
| [**Failed case:** baseline R11](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dc9-d706-70d6-80be-665dc3ccb097) | ❌ Cause chunk never retrieved; vague answer passed. Fixed by sibling expansion ([after the fix](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dd8-7cf9-74e4-8d37-7d8b8145e62d)) |
| [**Difficult case:** provider failure](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dc4-cd7f-74c3-a48b-6ccf2b2f8791) | ❌ Configured models retired (HTTP 404); every agent degraded gracefully and the user got cited passages |

More links and the reasoning behind each are in [`docs/EVALUATION.md` §6](docs/EVALUATION.md#6-langsmith-traces).

## AI-use disclosure

Claude Code was used to help design and write the code, tests, evaluation and documentation. The output was checked
with the unit tests, the evaluation and acceptance runs, hand-checked gold labels, manual UI testing and code
review. Full statement: [`docs/AI_USE.md`](docs/AI_USE.md).

## Costs and limits

Everything runs locally except the LLM calls (Groq) and trace upload (LangSmith), both on free plans. Groq's free tier
limits each model to 200k tokens/day, and the fallback model to 8k tokens/minute. On HTTP 429 the app:
1. retries, honouring `Retry-After`;
2. falls back to the second model, then to `GROQ_FALLBACK_MODELS` (default `qwen/qwen3.8-27b`, which has its own quota);
3. if everything is exhausted, shows the top cited passages instead of failing.

Memory viewing and "forget everything" keep working without the LLM, and the Memory tab never needs it. To use other
Groq models, set `GROQ_MAIN_MODEL` / `GROQ_FAST_MODEL` / `GROQ_FALLBACK_MODELS` in `.env`.

Known limitations (full list in [`docs/DESIGN.md`](docs/DESIGN.md#10-limitations)):
- free-tier latency and quotas;
- LLM-based memory extraction can miss borderline cases;
- keyword-based answer checks in the evaluation;
- no real authentication (simulated users).

## Privacy

All demo users and data are synthetic. Secrets typed into the chat are replaced with `[REDACTED_SECRET]` before they
reach the model, the database or LangSmith. `.env` and `storage/` are git-ignored, and no keys are in the code or the
history.

## Project layout

```
run.py                      entry point: API + web UI on port 8000
assistant/
  api.py                    FastAPI REST API (per-user routes) + serves the built UI
  config.py                 settings from .env
  redaction.py              secret removal before LLM / storage / traces
  llm.py                    Groq access: retries, model fallback chain, JSON-mode retry, typed outputs
  service.py                one conversation turn (used by UI and eval)
  graph.py                  LangGraph wiring of the agents
  agents/                   memory_agent, coordinator, researcher, analyst, verifier, responder, intent, prompts
  knowledge/                corpus loader + hybrid retriever (Chroma + BM25)
  memory/                   SQLite store (per-user) + storage policy
frontend/                   React + TypeScript (Vite); dist/ is the pre-built UI served by run.py
data/corpus.jsonl           the unchanged corpus (75 chunks / 25 documents)
eval/                       test cases, scenarios, runners (retrieval, end to end, acceptance), results
tests/                      unit + API tests (no API key needed)
docs/                       DESIGN.md, EVALUATION.md, AI_USE.md
```

### Changing the frontend (optional, needs Node.js 20+)

Keep `python run.py` running, then in a second terminal:

```bash
cd frontend
```
```bash
npm install
```
```bash
npm run dev
```

Vite serves the UI with hot reload on http://localhost:5173 and forwards `/api` calls to port 8000. Run
`npm run build` to update `frontend/dist`.
