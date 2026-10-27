# Evaluation

All numbers below are reproducible with the commands shown. Result files are in `eval/results/`.

## 1. What is measured and why

| Suite | What | Why it matters for this assignment |
|---|---|---|
| **Retrieval** (`eval/run_retrieval_eval.py`, no LLM) | Recall@4/8 and MRR of hand-labelled gold chunks for 26 questions, vector vs BM25 vs hybrid | An answer can't be grounded if the right chunk is never retrieved. Free and deterministic, so it isolates retrieval from the LLM |
| **Research, end-to-end** (`eval/run_eval.py --suite research`) | 27 questions in 7 categories: lookup, multi-hop, incident, conflict, temporal, false-premise, unanswerable | Trustworthy research: correct content, valid citations, conflicts resolved, gaps admitted |
| **Memory, end-to-end** (`eval/run_eval.py --suite memory`) | 10 multi-turn scenarios with assertions on the database and on answers | Memory is 25% of the grade: cross-session recall, correction, forgetting, isolation, secrets, sensitive data, memory ≠ evidence, follow-ups |
| **Unit tests** (`pytest`) | 20 tests: isolation, correction chains, forget + audit scrub, policy, redaction, citation rules | The guarantees that must hold every time, regardless of the LLM |

**Research metrics per case**

- `retrieval_recall`: share of the gold chunks found in the evidence the agents actually used.
- `citations_valid`: every `[chunk_id]` in the answer was retrieved, so no invented IDs.
- `cites_gold`: an answerable question cites at least one gold chunk.
- `content_ok`: the required facts appear, as any-of keyword groups such as `["175"]` or `["21 days", "21-day"]`, and no forbidden phrase does.
- `abstain_ok`: unanswerable questions admit the gap, and answerable ones are not refused.
- `passed`: all of the above.

**Memory checks**: `memory_contains`, `memory_not_contains` (optionally including superseded rows), `audit_not_contains`,
`transcript_not_contains`, `answer_contains`, `answer_not_contains`, and memory counts. Every run uses a fresh database and fresh users.

**Known blind spots of the checker**

- Keyword checks can't judge reasoning quality or tone.
- An answer can be correct but worded in a way no keyword group anticipates.
- Gold labels were written by one person.
- The LLM is non-deterministic, so a single run is one sample.

## 2. Results

| Run | Research passed | Gold recall | Citations valid | Memory passed |
|---|---|---|---|---|
| Baseline (`e2e_*_baseline`) | 16/27 | 0.92 | 27/27 | 9/10 |
| Baseline answers re-scored with the fixed checker (`--rescore`) | 26/27 | 0.92 | 27/27 | 9/10 |
| Improved (`e2e_*_improved`) | 26/27 | 0.96 | 27/27 | 10/10 |
| "Final" re-run (`e2e_*_final`) | **invalid**: Groq daily token quota ran out at R04 (see §5) | | | |

The **improved run is the result of record**. Its re-score with the stricter scorer (degraded answers never pass) is
still 26/27. The R16 citation fix was confirmed afterwards by a targeted run (`e2e_*_r16check`: R01, R16, R17, R18 → 4/4).

Retrieval-only (`eval/results/retrieval.md`, raw question, top 8):

| mode | recall@8 | all gold@8 | MRR |
|---|---|---|---|
| vector | 0.962 | 0.962 | 0.891 |
| BM25 | 0.942 | 0.923 | 0.885 |
| **hybrid** (used) | **0.981** | 0.962 | 0.879 |

Vector-only search completely misses "What caused INC-2025-12?" because embeddings don't separate incident IDs well. BM25
alone misses paraphrased questions such as R25/R26. Hybrid search has the best recall, which is why it is the default.

## 3. Failure analysis of the baseline

The baseline scored 16/27. Reading every failing answer and its trace gave four root causes:

| # | Cases | What happened | Type |
|---|---|---|---|
| 1 | R01 R02 R13 R15 R18 | gpt-oss cites as `【pricing:0】` (full-width brackets). The parser only knew `[...]`, so the **UI showed no Sources** even though the model had cited correctly | **System bug** |
| 2 | R04 R05 R08 R17 R25 | Correct answers marked wrong: the model wrote `4 minutes` with a narrow no-break space (U+202F), `20‑day` with a non-breaking hyphen, `25 %`, and "does not publish" (not in the abstention phrase list) | **Checker bug** |
| 3 | R11 | The answer to "What caused INC-2025-12?" was vague ("a bug in dedup logic"). The cause chunk `incident-12:1` never mentions "INC-2025-12", and the Coordinator's four ID-heavy queries crowded it out (gold recall 0.0) | **Retrieval** |
| 4 | M03 | After the memory was correctly updated to "Enterprise", the question about "my customers' retention" got "not documented". `pricing:1` (Enterprise 540 days) was missing from round 1, and the Verifier accepted the abstention without searching again | **Retrieval + verification** |

To separate measurement from behaviour, the **unchanged baseline answers** were re-scored after fixing the checker.
The result was 26/27. So most baseline "failures" were measurement errors, and the real system failures were #1 (user-visible), #3 and #4.

## 4. Improvements driven by the findings

**A. Citation normalisation** (`verifier.normalize_citations`, applied in the Analyst). Full-width brackets are rewritten
to `[...]`, so the Sources list, the Verifier rule check and the evaluation all see the same citations. A regression test was added.

**B. Sibling expansion in retrieval** (`HybridRetriever.expand_siblings`). The other chunks of the 3 best-ranked
documents are added to the evidence. Before changing the agent, I replayed the Coordinator's *actual* baseline queries
offline (`python -m eval.replay_planned_queries <baseline results.json>`):

| strategy | mean gold recall | cases missing gold | evidence size |
|---|---|---|---|
| equal weights (baseline) | 0.923 | R09, R11, R25 | 8.0 |
| extra queries weighted 0.5 | 0.923 | R09, R11, R25 | 8.0 |
| **equal weights + siblings** | **0.962** | R09, R25 | 12.1 |

My first hypothesis, that the extra queries out-vote the main question and should be down-weighted, made **no**
difference and was rejected. Sibling expansion fixed R11 for about 4 extra chunks per prompt. In the improved run R11
answers with the actual cause (Heron changed result ordering, which broke position-based deduplication) and cites `incident-12:1`.

**C. "Second look" before abstaining** (Verifier). If the draft says information is missing and only one search has
run, the Verifier sends it back to the Research Agent. The second search uses the standalone question alone with a
deeper cut-off, because extra queries can crowd out the right chunk. Offline, that query alone ranks `pricing:1` 4th.
Honest attribution: in the improved run M03 passed **without** needing the second look. The Coordinator's rewrite
("searchable run-record retention period for Enterprise customers") found `pricing:1` in round 1. M03's pass therefore
partly reflects run-to-run variation in the query plan. The second look is a safety net, and it visibly fires on R27
(see trace below). Trade-off: truly unanswerable questions (R26, R27) cost one more Analyst + Verifier pass.

**D. Prompt tweaks from the smoke-test trace.**
- The Coordinator now uses memory only when the question refers to the user's own situation. Before, it turned
  "what is the on-call stipend?" into "stipend for Team plan customers".
- The Verifier no longer demands citations for "not documented" statements. Before, it triggered a pointless revision.

**Outcome:**
- Gold recall went from 0.92 to 0.96.
- Memory scenarios went from 9/10 to 10/10.
- R11 is fixed by sibling expansion, which is deterministic and confirmed offline.
- M03 passes, but partly through query-plan variation (see C).
- Answers now always show their Sources.

## 5. Representative failure after the improvements

**R16 (improved run): correct answer, no Sources.** The answer ("$175, replacing the earlier $140 [...]") was right,
but the model wrote `– handbook:1` without brackets. My rule check passed it anyway, because it also counted chunk IDs in
the structured `claims` list, which the user never sees. Fix: the rule now requires inline `[chunk_id]` citations in the
answer text, so such drafts go back to the Analyst (regression test `test_claims_without_inline_citations_are_flagged`).
A targeted re-run of R01/R16/R17/R18 passed 4/4.

**Rate limit during the final run, and a scorer flaw it exposed.** A third full run was started to confirm the R16 fix.
Groq's free tier allows 200,000 tokens per day per model; one full run uses roughly 100k on the fast model, and this was
the third run that day. From case R04 on, every call returned HTTP 429 (`tokens per day`). The system behaved as designed:
- the Coordinator fell back to searching with the raw question;
- the Memory Agent skipped (no memory changes);
- the Analyst returned the top passages with citations, labelled "not a verified answer".

But the scorer reported **25/27 passed**, because those raw passages happen to contain the expected keywords. That is
a measurement error: a degraded answer must never count. The scorer now fails any turn with status `error`. Re-scored,
that run is 3/27 (all other failures are quota errors), and the improved run is unchanged at 26/27. Memory scenarios in
that run failed for the same reason: with no LLM, the Memory Agent cannot extract memories. That is fail-safe (nothing
is stored wrongly) but means no personalisation while the provider is down.

Other remaining weak spots seen in traces:
- **R09** and **R25** retrieve only half the gold chunks. The answers are still correct, because the other gold chunk carries the same fact.
- **Latency** is about 20–25 s per research turn: 4 LLM calls, up to 6 with loops, on a free tier.
- **Memory extraction** depends on the 20B model. Borderline statements can be saved or missed; the policy gate only blocks clear cases.

## 6. LangSmith traces

Project: `asterline-research-assistant`. Every turn is a root run `assistant_turn`, with child spans per agent
(`recall_memories`, `update_memories` ‖ `plan`, `research` → `hybrid_search`, `analyse`, `verify`, `finalize_*`) and
metadata `user_id` / `session_id`. Links (times UTC, 2026-10-27):

| What it shows | Link |
|---|---|
| ✅ Conflict resolved: stipend $175 supersedes $140, both cited | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dda-155a-77b2-8152-8c6af8608833) |
| ✅ R11 after the fix: sibling expansion brings in the cause chunk | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dd8-7cf9-74e4-8d37-7d8b8145e62d) |
| ✅ M03: memory ("supports Enterprise") turns "my customers" into an Enterprise question → 540 days | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de1-2ea1-7156-8fb2-b8ac93969e93) |
| ✅ Forget request routed to the Memory Agent | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de1-d5b6-749a-8201-0c67e9b7381e) |
| ✅ Isolation: Bob asks about "his" customer, gets nothing of Alice's | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de2-395f-75b2-a2b3-aea7bd34b5ff) |
| ✅ Secret redacted before tracing: the input shows `[REDACTED_SECRET]` | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17de2-634c-760d-a2a9-b64923c3ae32) |
| ✅ Unanswerable (R27): Verifier forces a second look (`retrieve_more` → research round 2), then accepts the gap | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dde-bd33-733b-8772-a97142d9f00d) |
| ❌ **Failed case**: baseline R11, cause chunk never retrieved, vague answer passed by the Verifier | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dc9-d706-70d6-80be-665dc3ccb097) |
| ❌ **Provider failure**: configured models retired (HTTP 404); every agent degraded gracefully and the user got cited passages | [run](https://smith.langchain.com/o/d1361e29-3cd5-4b5a-a7bd-5ae79eed3328/projects/p/438723af-320f-47bc-9716-7c713727d8f7/r/01a17dc4-cd7f-74c3-a48b-6ccf2b2f8791) |

## 7. Reproduce

```bash
python -m pytest -q
```
```bash
python -m eval.run_retrieval_eval
```
```bash
python -m eval.run_eval --tag mine
```
```bash
python -m eval.replay_planned_queries eval/results/<baseline-run>/results.json
```
```bash
python -m eval.run_eval --rescore eval/results/<run>/results.json
```
