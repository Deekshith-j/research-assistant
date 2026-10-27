# AI-use disclosure

**Tool used:** Claude Code (Anthropic, Claude Opus model) as a coding assistant.

**What it helped produce**
- Reading the assignment PDF and extracting the embedded `corpus.jsonl` attachment unchanged.
- Proposing the architecture (agents, memory model, hybrid retrieval) and writing the first version of the code,
  prompts, unit tests, evaluation cases/runners and documentation.

**How the output was checked**
- Unit tests (`pytest`) for memory isolation, correction, forgetting, policy rejections, secret redaction and citation rules.
- Ran the retrieval evaluation and the end-to-end evaluation; failures were inspected in the result files and in
  LangSmith traces, and fixes were re-evaluated (see `docs/EVALUATION.md`).
- Gold chunk IDs and expected answers in `eval/` were checked by hand against the corpus.
- Manually exercised the UI: conversations, follow-ups, memory add/correct/forget, user switching, restart persistence.
- Reviewed the code to be able to explain every module in the walkthrough.

<!-- Edit this file to reflect your own review process before submitting. -->
