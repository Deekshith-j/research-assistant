"""Retrieval-only evaluation (no LLM, no API key, fully reproducible).

Compares vector-only, BM25-only and hybrid retrieval on the research cases using
the gold chunk ids. This is the experiment behind the "vector -> hybrid" improvement
described in docs/EVALUATION.md.

Run:  python -m eval.run_retrieval_eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from assistant.knowledge.retriever import get_retriever

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
MODES = ("vector", "bm25", "hybrid")
KS = (4, 8)


def evaluate() -> dict:
    cases = [c for c in json.loads((EVAL_DIR / "research_cases.json").read_text()) if c["gold"]]
    retriever = get_retriever()
    report: dict = {"n_cases": len(cases), "modes": {}}

    for mode in MODES:
        per_case, totals = [], {f"recall@{k}": 0.0 for k in KS} | {f"all_gold@{k}": 0 for k in KS} | {"mrr": 0.0}
        for case in cases:
            ranked = [s.chunk.chunk_id for s in retriever.search(case["question"], k=max(KS), mode=mode)]
            gold = set(case["gold"])
            row = {"id": case["id"], "category": case["category"], "top": ranked[:max(KS)]}
            for k in KS:
                found = gold & set(ranked[:k])
                row[f"recall@{k}"] = len(found) / len(gold)
                totals[f"recall@{k}"] += row[f"recall@{k}"]
                totals[f"all_gold@{k}"] += int(found == gold)
            # Mean reciprocal rank of the first gold chunk.
            first = next((i for i, cid in enumerate(ranked, 1) if cid in gold), None)
            row["rr"] = 1 / first if first else 0.0
            totals["mrr"] += row["rr"]
            row["missed@8"] = sorted(gold - set(ranked[:8]))
            per_case.append(row)

        n = len(cases)
        summary = {key: round(val / n, 3) for key, val in totals.items()}
        report["modes"][mode] = {"summary": summary, "cases": per_case}
    return report


def to_markdown(report: dict) -> str:
    lines = [f"# Retrieval evaluation ({report['n_cases']} cases with gold chunks)\n",
             "| mode | recall@4 | recall@8 | all gold@4 | all gold@8 | MRR |", "|---|---|---|---|---|---|"]
    for mode, data in report["modes"].items():
        s = data["summary"]
        lines.append(f"| {mode} | {s['recall@4']} | {s['recall@8']} | {s['all_gold@4']} | {s['all_gold@8']} | {s['mrr']} |")
    for mode, data in report["modes"].items():
        misses = [c for c in data["cases"] if c["missed@8"]]
        lines.append(f"\n## {mode}: cases missing a gold chunk in the top 8 ({len(misses)})\n")
        lines += [f"- {c['id']} ({c['category']}): missed {c['missed@8']}; got {c['top']}" for c in misses] or ["- none"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    RESULTS_DIR.mkdir(exist_ok=True)
    rep = evaluate()
    (RESULTS_DIR / "retrieval.json").write_text(json.dumps(rep, indent=2))
    md = to_markdown(rep)
    (RESULTS_DIR / "retrieval.md").write_text(md, encoding="utf-8")
    print(md)
