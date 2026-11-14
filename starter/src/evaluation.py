"""Evaluate retrieval hits and keep full per-question traces.

A hit = retrieved chunk is from the gold (document, page) AND contains the
normalized gold evidence quote (or an accepted alternative). No LLM judge,
no inferring manual labels here.
"""
import re
from typing import Any

from .ingestion import normalize_text


def match_key(text: str) -> str:
    """Whitespace-insensitive matching key: unit text keeps paragraph newlines,
    benchmark quotes are written as single lines."""
    return re.sub(r"\s+", " ", normalize_text(text))


def _gold_list(question: dict[str, Any]) -> list[dict[str, Any]]:
    golds = [{"source_id": question["gold_source_id"], "page": question["gold_page"],
              "evidence": question["evidence_quote"]}]
    golds.extend(question.get("alt_gold", []))
    return golds


def _is_hit(hit: dict[str, Any], golds: list[dict[str, Any]]) -> bool:
    meta = hit["metadata"]
    text = match_key(hit["text"])
    return any(
        meta.get("document_id") == g["source_id"]
        and meta.get("page") == g["page"]
        and match_key(g["evidence"]) in text
        for g in golds
    )


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    golds = _gold_list(question)
    hit_flags = [_is_hit(h, golds) for h in hits]
    return {
        "question_id": question["id"],
        "hit_at_1": hit_flags[0] if hit_flags else False,
        "evidence_hit_at_3": any(hit_flags[:3]),
        "gold_units": [{"source_id": g["source_id"], "page": g["page"]} for g in golds],
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 / Evidence Hit@3 per (strategy, split) with n/N counts."""
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for t in traces:
        buckets.setdefault((t["strategy"], t["split"]), []).append(t)
    summary = {}
    for (strategy, split), rows in sorted(buckets.items()):
        n = len(rows)
        summary[f"{strategy}_{split}"] = {
            "n": n,
            "hit1": f"{sum(r['hit_at_1'] for r in rows)}/{n}",
            "hit3": f"{sum(r['evidence_hit_at_3'] for r in rows)}/{n}",
        }
    return summary
