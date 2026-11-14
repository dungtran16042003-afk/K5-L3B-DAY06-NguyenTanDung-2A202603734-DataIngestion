"""Generate manual audit samples for the three hand-labeled dimensions.

  coherence : same 10 source positions (first 10 unit starts, sorted by unit id)
              -> the A chunk and B chunk covering each position
  metadata  : 5 test questions x top-3 per strategy, checked against gold unit
  grounding : 5 test questions x top-3 per strategy (labels filled by hand)

Run from starter/:  .venv/Scripts/python -m src.audit
Writes results/audit_samples.json for hand labeling.
"""
import json
from pathlib import Path

from . import ingestion
from .chunking import by_paragraph, fixed_size

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "results"
QUESTIONS = REPO / "benchmark" / "questions.json"


def find_covering(chunks, unit_text, probe):
    """Return chunks containing the probe string taken from unit_text."""
    return [c for c in chunks if probe[:60] in c.text.replace("\n", " ") or probe[:60] in c.text]


def main() -> None:
    pages = ingestion.load_corpus(REPO)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    traces = json.loads((RESULTS / "traces.json").read_text(encoding="utf-8"))

    # --- 1. coherence sample: 10 positions = MID-unit lines, sorted by (doc, page).
    # Mid-unit probes avoid the bias of unit starts; probe[:25] still finds the
    # A window even when the window boundary cuts the line itself.
    def tag(chunks, prefix):
        for c in chunks:
            c.chunk_id = f"{prefix}:{c.chunk_id}"
        return chunks

    chunk_A = tag([c for p in pages for c in fixed_size(p, 500, 50)], "A")
    chunk_B = tag([c for p in pages for c in by_paragraph(p, 900)], "B")
    positions = []
    for p in sorted(pages, key=lambda x: (x.document_id, x.page))[:10]:
        mid = len(p.text) // 2
        line_start = p.text.rfind("\n", 0, mid) + 1
        line_end = p.text.find("\n", mid)
        probe = p.text[line_start:line_end if line_end != -1 else len(p.text)][:60]
        a_hits = [c.chunk_id for c in chunk_A if probe[:25] in c.text]
        b_hits = [c.chunk_id for c in chunk_B if probe[:25] in c.text]
        positions.append({
            "position_id": f"{p.document_id}:p{p.page}:mid",
            "unit_text_mid": probe,
            "A_chunks_covering": a_hits, "A_label": None, "A_reason": None,
            "B_chunks_covering": b_hits, "B_label": None, "B_reason": None,
        })

    # --- 2. metadata + 3. grounding samples: test questions, top-3 per strategy
    test_ids = {q["id"] for q in questions if q["split"] == "test"}
    meta_rows, ground_rows = [], []
    gold_by_id = {q["id"]: q for q in questions}
    for t in traces:
        if t["split"] != "test" or t["question_id"] not in test_ids:
            continue
        q = gold_by_id[t["question_id"]]
        for rank, hit in enumerate(t["top3"], start=1):
            m = hit["metadata"]
            correct = (m.get("document_id") == q["gold_source_id"] and m.get("page") == q["gold_page"])
            meta_rows.append({
                "question_id": t["question_id"], "strategy": t["strategy"], "rank": rank,
                "document_id": m.get("document_id"), "source": m.get("source"),
                "page": m.get("page"), "book": m.get("book"),
                "expected_doc": q["gold_source_id"], "expected_page": q["gold_page"],
                "fields_ok": None, "values_correct": correct, "note": None,
            })
        ground_rows.append({
            "question_id": t["question_id"], "strategy": t["strategy"],
            "top3_unit_ids": [f"{h['metadata'].get('document_id')}:p{h['metadata'].get('page')}"
                              for h in t["top3"]],
            "top3_similarity": [h["similarity"] for h in t["top3"]],
            "label": None, "reason": None,  # 0 = no evidence, 1 = incomplete, 2 = sufficient
        })

    audit = {
        "how_to_label": {
            "coherence": "0 = cut mid-idea/missing subject, 1 = partly understandable, 2 = self-contained",
            "metadata": "fields_ok = document_id, source, page (+book filter field) present AND correct vs gold",
            "grounding": "0 = no evidence in top-3, 1 = evidence present but missing a needed condition, 2 = sufficient to answer & traceable",
            "filter_compliance": "computed from traces.json: strategy C top-3 all have book=<filter> ?",
        },
        "coherence_positions": positions,
        "metadata_rows": meta_rows,
        "grounding_rows": ground_rows,
    }
    (RESULTS / "audit_samples.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    # filter compliance for C on the 4 filter questions (computed, not hand-labeled)
    filter_rows = []
    for t in traces:
        if t["filter_applied"]:
            compliant = all(h["metadata"].get("book") == t["filter_applied"]["book"] for h in t["top3"])
            filter_rows.append({"question_id": t["question_id"], "strategy": t["strategy"],
                                "filter": t["filter_applied"], "top3_compliant": compliant})
    (RESULTS / "filter_compliance.json").write_text(
        json.dumps(filter_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"audit samples: {len(positions)} coherence positions, {len(meta_rows)} metadata rows, "
          f"{len(ground_rows)} grounding rows; filter compliance: {sum(r['top3_compliant'] for r in filter_rows)}/{len(filter_rows)}")
    print("-> results/audit_samples.json, results/filter_compliance.json")


if __name__ == "__main__":
    main()
