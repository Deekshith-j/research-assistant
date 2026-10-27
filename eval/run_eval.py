"""End-to-end evaluation of research quality and memory behaviour (uses the Groq LLM).

Every run uses a brand-new SQLite database, so results don't depend on earlier runs.
Results are written to eval/results/e2e_<timestamp>.json and .md.

Run:
  python -m eval.run_eval                       # everything
  python -m eval.run_eval --suite research      # research cases only
  python -m eval.run_eval --suite memory --only M03 M04
  python -m eval.run_eval --delay 3             # pause between turns (free-tier rate limits)

Research metrics (per case):
  retrieval_recall  share of gold chunks present in the evidence the agents used
  citations_valid   every [chunk_id] in the answer is in the retrieved evidence (no invented ids)
  cites_gold        the answer cites at least one gold chunk (answerable cases)
  content_ok        every "must_include" group matched and no "must_not_include" phrase present
  abstain_ok        unanswerable -> admits it is not documented; answerable -> does not abstain
  passed            all of the above
Memory metrics: each scenario step "check" is pass/fail; a scenario passes if all checks pass.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from assistant.agents.verifier import extract_citations
from assistant.memory.store import Store
from assistant.service import AssistantService, TurnResult

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"

ABSTAIN_PHRASES = ("not documented", "no information", "does not specify", "doesn't specify", "not mentioned",
                   "not specified", "not published", "not been announced", "no announced", "not available in",
                   "do not contain", "does not contain", "doesn't contain", "not covered", "no claims",
                   "cannot find", "could not find", "not stated", "no launch date", "don't have information",
                   "does not publish", "no list price", "no published")

# Models write numbers with typographic characters ("4 minutes", "20‑day", "25 %").
# The baseline run marked correct answers as wrong because of this, so the checker normalises first.
_UNICODE_FIXES = {" ": " ", " ": " ", " ": " ", "‑": "-", "‐": "-", "–": "-", " %": "%"}


def _normalize(text: str) -> str:
    for src, dst in _UNICODE_FIXES.items():
        text = text.replace(src, dst)
    return text.lower()


def _has_any(text: str, options: list[str]) -> bool:
    low = _normalize(text)
    return any(_normalize(o) in low for o in options)


# ============================================================================ research
def score_research(case: dict, r: TurnResult) -> dict:
    gold, evidence = set(case["gold"]), set(r.evidence_ids)
    cited = extract_citations(r.answer)
    abstained = r.status in ("insufficient_evidence", "partial") or _has_any(r.answer, list(ABSTAIN_PHRASES))

    content_ok = all(_has_any(r.answer, group) for group in case.get("must_include", []))
    forbidden = case.get("must_not_include", [])
    if forbidden and _has_any(r.answer, forbidden):
        content_ok = False
    # Answerable questions must not be refused; "partial" is acceptable if the content is right.
    abstain_ok = abstained if case.get("expect_abstain") else r.status != "insufficient_evidence"
    citations_valid = set(cited) <= evidence
    cites_gold = True if (not gold or case.get("expect_abstain")) else bool(gold & set(cited))

    return {
        "id": case["id"], "category": case["category"], "question": case["question"],
        "status": r.status, "retrieval_recall": round(len(gold & evidence) / len(gold), 2) if gold else None,
        "citations_valid": citations_valid, "cites_gold": cites_gold, "content_ok": content_ok,
        # A degraded offline answer (LLM unavailable) can contain the right keywords by luck; never count it.
        "abstain_ok": abstain_ok,
        "passed": r.status != "error" and citations_valid and cites_gold and content_ok and abstain_ok,
        "cited": cited, "evidence": r.evidence_ids, "latency_s": r.latency_s,
        "analyst_passes": sum(t.startswith("AnalystAgent") for t in r.trace),
        "answer": r.answer, "trace": r.trace,
    }


def run_research(svc: AssistantService, cases: list[dict], delay: float) -> list[dict]:
    results = []
    for case in cases:
        user = svc.user(f"eval_{case['id']}")  # fresh user per case: no memory influence
        session = user.create_session()
        try:
            r = svc.ask(user.user_id, session.id, case["question"])
            row = score_research(case, r)
        except Exception as exc:  # keep going; a crash is a failed case, not a failed run
            row = {"id": case["id"], "category": case["category"], "passed": False, "error": repr(exc)}
        results.append(row)
        print(f"{row['id']:>4} {'PASS' if row['passed'] else 'FAIL'}  {row.get('status', 'error')}")
        time.sleep(delay)
    return results


# ============================================================================ memory
def run_check(svc: AssistantService, prefix: str, sessions: dict, step: dict, last: TurnResult | None) -> tuple[bool, str]:
    """Evaluate one scenario check. Returns (passed, detail)."""
    kind = step["check"]
    user = svc.user(f"{prefix}_{step['user']}") if "user" in step else None
    mems = user.list_memories(include_superseded=step.get("include_superseded", False)) if user else []
    mem_text = " | ".join(m.content for m in mems)

    if kind == "memory_contains":
        return _has_any(mem_text, step["any"]), mem_text
    if kind == "memory_not_contains":
        return not _has_any(mem_text, step["none"]), mem_text
    if kind == "memory_kind_contains":
        text = " | ".join(m.content for m in mems if m.kind == step["kind"])
        return _has_any(text, step["any"]), text
    if kind == "memory_count_at_least":
        return len(mems) >= step["n"], f"{len(mems)} memories"
    if kind == "memory_count_at_most":
        return len(mems) <= step["n"], f"{len(mems)} memories"
    if kind == "audit_not_contains":
        text = " | ".join(e["detail"] or "" for e in user.memory_events())
        return not _has_any(text, step["none"]), text
    if kind == "transcript_not_contains":
        sid = sessions[(step["user"], step["session"])]
        text = " | ".join(m.content for m in user.get_messages(sid))
        return not _has_any(text, step["none"]), "transcript checked"
    if kind == "answer_contains":
        return bool(last) and _has_any(last.answer, step["any"]), last.answer if last else ""
    if kind == "answer_not_contains":
        return bool(last) and not _has_any(last.answer, step["none"]), last.answer if last else ""
    raise ValueError(f"unknown check {kind}")


def run_memory(svc: AssistantService, scenarios: list[dict], delay: float) -> list[dict]:
    results = []
    for sc in scenarios:
        prefix = f"mem_{sc['id']}"
        sessions: dict[tuple[str, str], str] = {}
        last: TurnResult | None = None
        steps_out, ok = [], True
        try:
            for step in sc["steps"]:
                if "say" in step:  # a conversation turn
                    user = svc.user(f"{prefix}_{step['user']}")
                    key = (step["user"], step["session"])
                    if key not in sessions:
                        sessions[key] = user.create_session().id
                    last = svc.ask(user.user_id, sessions[key], step["say"])
                    steps_out.append({"say": step["say"], "answer": last.answer, "memory_ops": last.memory_ops,
                                      "trace": last.trace})
                    time.sleep(delay)
                else:  # an assertion
                    passed, detail = run_check(svc, prefix, sessions, step, last)
                    ok &= passed
                    steps_out.append({"check": step["check"], "passed": passed, "detail": detail[:500]})
        except Exception as exc:
            ok = False
            steps_out.append({"error": repr(exc)})
        results.append({"id": sc["id"], "name": sc["name"], "passed": ok, "steps": steps_out})
        print(f"{sc['id']:>4} {'PASS' if ok else 'FAIL'}  {sc['name']}")
    return results


# ============================================================================ report
def summarize(research: list[dict], memory: list[dict]) -> str:
    lines = [f"# End-to-end evaluation ({datetime.now():%Y-%m-%d %H:%M})\n"]
    if research:
        ok = [r for r in research if "error" not in r]
        def rate(key):  # share of cases where a boolean metric is true
            return f"{sum(bool(r[key]) for r in ok)}/{len(ok)}"
        recalls = [r["retrieval_recall"] for r in ok if r["retrieval_recall"] is not None]
        lines += [
            "## Research", "",
            f"- **Passed: {sum(r['passed'] for r in research)}/{len(research)}**",
            f"- Mean retrieval recall of gold chunks: {sum(recalls) / max(len(recalls), 1):.2f}",
            f"- Citations valid: {rate('citations_valid')} · cites gold: {rate('cites_gold')} · "
            f"content correct: {rate('content_ok')} · abstention correct: {rate('abstain_ok')}",
            f"- Mean latency: {sum(r['latency_s'] for r in ok) / max(len(ok), 1):.1f}s · "
            f"turns needing a revision: {sum(r['analyst_passes'] > 1 for r in ok)}",
            "", "| id | category | status | recall | cites valid | cites gold | content | abstain | pass |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in research:
            if "error" in r:
                lines.append(f"| {r['id']} | {r['category']} | ERROR | | | | | | ❌ |")
                continue
            b = lambda v: "✅" if v else "❌"  # noqa: E731
            lines.append(f"| {r['id']} | {r['category']} | {r['status']} | {r['retrieval_recall']} | "
                         f"{b(r['citations_valid'])} | {b(r['cites_gold'])} | {b(r['content_ok'])} | "
                         f"{b(r['abstain_ok'])} | {b(r['passed'])} |")
    if memory:
        lines += ["", "## Memory", "", f"- **Passed: {sum(m['passed'] for m in memory)}/{len(memory)}**", ""]
        for m in memory:
            failed = [s for s in m["steps"] if s.get("passed") is False or "error" in s]
            lines.append(f"- {'✅' if m['passed'] else '❌'} {m['id']} {m['name']}"
                         + (f" — failed: {[s.get('check', s.get('error')) for s in failed]}" if failed else ""))
    return "\n".join(lines) + "\n"


def rescore(results_path: Path) -> None:
    """Apply the current scoring rules to answers saved by an earlier run.

    Used to separate checker fixes from system fixes: the baseline answers are
    re-scored unchanged, so any change in the score comes from the checker alone.
    """
    saved = json.loads(results_path.read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in json.loads((EVAL_DIR / "research_cases.json").read_text())}
    research = [
        score_research(cases[r["id"]], TurnResult(answer=r["answer"], status=r["status"], trace=r["trace"],
                                                  evidence_ids=r["evidence"], latency_s=r["latency_s"]))
        for r in saved["research"] if "answer" in r
    ]
    report = summarize(research, saved.get("memory", []))
    (results_path.parent / "report_rescored.md").write_text(report, encoding="utf-8")
    print(report)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252; answers contain Unicode
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", choices=["research", "memory", "all"], default="all")
    ap.add_argument("--only", nargs="*", help="case/scenario ids to run")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds to wait between turns")
    ap.add_argument("--tag", default="", help="label added to the result file name")
    ap.add_argument("--rescore", metavar="RESULTS_JSON",
                    help="re-score saved research answers with the current checker (no LLM calls)")
    args = ap.parse_args()

    if args.rescore:
        rescore(Path(args.rescore))
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + (f"_{args.tag}" if args.tag else "")
    run_dir = RESULTS_DIR / f"e2e_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    svc = AssistantService(Store(run_dir / "eval.db"))  # isolated, throw-away database

    def select(items):
        return [i for i in items if not args.only or i["id"] in args.only]

    research = memory = []
    if args.suite in ("research", "all"):
        research = run_research(svc, select(json.loads((EVAL_DIR / "research_cases.json").read_text())), args.delay)
    if args.suite in ("memory", "all"):
        memory = run_memory(svc, select(json.loads((EVAL_DIR / "memory_scenarios.json").read_text())), args.delay)

    (run_dir / "results.json").write_text(json.dumps({"research": research, "memory": memory}, indent=2))
    report = summarize(research, memory)
    (run_dir / "report.md").write_text(report, encoding="utf-8")
    print("\n" + report + f"\nSaved to {run_dir}")


if __name__ == "__main__":
    main()
