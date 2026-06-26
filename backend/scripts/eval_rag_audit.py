#!/usr/bin/env python3
"""Evaluate end-to-end RAG audit accuracy against gold_cases.jsonl.

Usage:
    cd backend && python scripts/eval_rag_audit.py --runs 3
    cd backend && python scripts/eval_rag_audit.py --rule-based-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from statistics import mean

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "tests" / "eval"))

from rag_eval_utils import (  # noqa: E402
    DEFAULT_GOLD_PATH,
    RESULTS_DIR,
    audit_matches_gold,
    case_input_to_audit_kwargs,
    filter_cases,
    load_gold_cases,
    write_csv_report,
    write_html_report,
)
from app.services.treatment_audit import analyze_treatment  # noqa: E402


def _run_case(case: dict, runs: int) -> dict:
    audit_gold = case.get("audit_gold") or {}
    kwargs = case_input_to_audit_kwargs(case)
    run_results = []

    for _ in range(runs):
        result = analyze_treatment(**kwargs)
        run_results.append(audit_matches_gold(result, audit_gold))

    pass_at_1 = run_results[0]["passed"] if run_results else False
    pass_at_k = any(item["passed"] for item in run_results)
    recalls = [item["recall"] for item in run_results if item["recall"] is not None]

    return {
        "case_id": case.get("id"),
        "source": case.get("source"),
        "rule_based_only": bool(audit_gold.get("rule_based_only")),
        "pass_at_1": pass_at_1,
        f"pass_at_{runs}": pass_at_k,
        "mean_recall": round(mean(recalls), 3) if recalls else "",
        "expected_flag_types": ", ".join(audit_gold.get("expected_flag_types") or []),
        "actual_flag_types": ", ".join(run_results[0].get("actual_flag_types") or []),
        "expected_misses": ", ".join(run_results[0].get("expected_misses") or []),
        "forbidden_hits": ", ".join(run_results[0].get("forbidden_hits") or []),
        "alignment_match": run_results[0].get("alignment_match"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate end-to-end RAG audit accuracy.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_GOLD_PATH)
    parser.add_argument("--output", type=Path, default=RESULTS_DIR)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--source", choices=["guideline_derived", "clinician"], default=None)
    parser.add_argument("--rule-based-only", action="store_true")
    parser.add_argument("--ids", nargs="*", default=None)
    args = parser.parse_args()

    cases = filter_cases(
        load_gold_cases(args.cases),
        source=args.source,
        rule_based_only=True if args.rule_based_only else None,
        case_ids=args.ids,
    )
    if not cases:
        raise SystemExit("No gold cases matched the filters.")

    rows = []
    for case in cases:
        row = _run_case(case, max(args.runs, 1))
        rows.append(row)
        print(
            f"[{'PASS' if row['pass_at_1'] else 'FAIL'}] {row['case_id']} "
            f"pass@{args.runs}={row[f'pass_at_{args.runs}']}",
            file=sys.stderr,
        )

    total = len(rows)
    summary = {
        "total": total,
        "pass_at_1": sum(1 for row in rows if row["pass_at_1"]) / total,
        f"pass_at_{args.runs}": sum(1 for row in rows if row[f"pass_at_{args.runs}"]) / total,
        "rule_based_cases": sum(1 for row in rows if row["rule_based_only"]),
    }

    stamp = date.today().isoformat()
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / f"audit_{stamp}.json"
    csv_path = args.output / f"audit_{stamp}.csv"
    html_path = args.output / f"audit_{stamp}.html"

    payload = {"summary": summary, "cases": rows}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv_report(rows, csv_path)
    write_html_report("RAG Audit Evaluation", summary, rows, html_path)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {json_path}", file=sys.stderr)
    print(f"Wrote {csv_path}", file=sys.stderr)
    print(f"Wrote {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
