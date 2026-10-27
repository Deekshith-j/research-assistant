"""Offline retrieval experiment on the Coordinator's *real* search plans.

The baseline end-to-end run showed lower gold recall (0.92) than searching with the
raw question alone (0.98). This script replays the exact queries the Coordinator
produced in a saved run and compares fusion strategies, without calling the LLM.

Run:  python -m eval.replay_planned_queries eval/results/<run>/results.json
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from assistant.knowledge.retriever import get_retriever

EVAL_DIR = Path(__file__).resolve().parent

# (label, weight of the Coordinator's extra queries, sibling expansion on/off)
STRATEGIES = [
    ("equal weights (baseline)", 1.0, False),
    ("secondary weight 0.5", 0.5, False),
    ("equal weights + siblings", 1.0, True),
    ("secondary weight 0.5 + siblings", 0.5, True),
]


def planned_queries(trace: list[str]) -> list[str]:
    """Pull the round-1 query list out of the ResearchAgent trace line."""
    line = next(t for t in trace if t.startswith("ResearchAgent round 1"))
    return ast.literal_eval(line.split("queries=", 1)[1].split(" -> ", 1)[0])


def main(results_path: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    run = json.loads(Path(results_path).read_text(encoding="utf-8"))
    gold = {c["id"]: set(c["gold"]) for c in json.loads((EVAL_DIR / "research_cases.json").read_text())}
    cases = [(r["id"], planned_queries(r["trace"])) for r in run["research"] if gold.get(r["id"]) and "trace" in r]
    retriever = get_retriever()

    lines = [f"# Replay of planned queries ({len(cases)} cases)\n", "| strategy | mean gold recall | cases missing gold | evidence size |", "|---|---|---|---|"]
    for label, weight, siblings in STRATEGIES:
        recalls, misses, sizes = [], [], []
        for cid, queries in cases:
            res = retriever.multi_search(queries, k=8, secondary_weight=weight)
            if siblings:
                res = retriever.expand_siblings(res)
            got = {r.chunk.chunk_id for r in res}
            recalls.append(len(gold[cid] & got) / len(gold[cid]))
            sizes.append(len(got))
            if gold[cid] - got:
                misses.append(f"{cid}:{sorted(gold[cid] - got)}")
        lines.append(f"| {label} | {sum(recalls) / len(recalls):.3f} | {len(misses)} {misses} | {sum(sizes) / len(sizes):.1f} |")
    report = "\n".join(lines) + "\n"
    (EVAL_DIR / "results" / "replay_planned_queries.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main(sys.argv[1])
