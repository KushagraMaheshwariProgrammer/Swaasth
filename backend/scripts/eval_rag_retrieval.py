#!/usr/bin/env python3
"""Evaluate RAG retrieval layer against gold_cases.jsonl.

Usage:
    cd backend && python scripts/eval_rag_retrieval.py
    cd backend && python scripts/eval_rag_retrieval.py --cases tests/eval/gold_cases.jsonl --output tests/eval/results
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "tests" / "eval"))

from rag_eval_utils import (  # noqa: E402
    DEFAULT_GOLD_PATH,
    RESULTS_DIR,
    aggregate_retrieval_results,
    case_input_to_retrieval_args,
    filter_cases,
    load_gold_cases,
    score_retrieval_case,
    write_csv_report,
    write_html_report,
)
from app.services.stg_retrieval import retrieve_stg_context  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval accuracy.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_GOLD_PATH)
    parser.add_argument("--output", type=Path, default=RESULTS_DIR)
    parser.add_argument("--source", choices=["guideline_derived", "clinician"], default=None)
    parser.add_argument("--ids", nargs="*", default=None)
    args = parser.parse_args()

    cases = filter_cases(load_gold_cases(args.cases), source=args.source, case_ids=args.ids)
    if not cases:
        raise SystemExit("No gold cases matched the filters.")

    results = []
    rows = []
    for case in cases:
        diagnosis, items, symptoms, test_results = case_input_to_retrieval_args(case)
        retrieval = retrieve_stg_context(
            diagnosis,
            items,
            symptoms=symptoms,
            test_results=test_results,
        )
        scored = score_retrieval_case(case, retrieval)
        results.append(scored)
        rows.append(
            {
                "case_id": scored.case_id,
                "source": scored.source,
                "passed": scored.passed,
                "document_hit_at_5": scored.document_hit_at_5,
                "mrr": scored.mrr if scored.mrr is not None else "",
                "corpus_hit": scored.corpus_hit,
                "term_recall": round(scored.term_recall, 3),
                "fallback_correct": scored.fallback_correct,
                "used_fallback": scored.used_fallback,
                "guideline_sources": ", ".join(scored.guideline_sources),
                "primary_chunks": scored.primary_chunk_count,
                "fallback_chunks": scored.fallback_chunk_count,
            }
        )
        print(
            f"[{'PASS' if scored.passed else 'FAIL'}] {scored.case_id} "
            f"hit@5={scored.document_hit_at_5} term_recall={scored.term_recall:.2f}",
            file=sys.stderr,
        )

    summary = aggregate_retrieval_results(results)
    if rows:
        summary["diagnosis_match_rate"] = round(
            sum(1 for row in rows if row.get("document_hit_at_5")) / len(rows),
            3,
        )
        summary["fallback_rate"] = round(
            sum(1 for row in rows if row.get("used_fallback")) / len(rows),
            3,
        )
    stamp = date.today().isoformat()
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / f"retrieval_{stamp}.json"
    csv_path = args.output / f"retrieval_{stamp}.csv"
    html_path = args.output / f"retrieval_{stamp}.html"

    payload = {"summary": summary, "cases": rows}
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_csv_report(rows, csv_path)
    write_html_report("RAG Retrieval Evaluation", summary, rows, html_path)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {json_path}", file=sys.stderr)
    print(f"Wrote {csv_path}", file=sys.stderr)
    print(f"Wrote {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
