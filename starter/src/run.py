"""Day 06 pipeline entry point.

Stages:
  ingest   load corpus -> units + manifest + readable dump (for writing questions)
  verify   check every benchmark evidence quote really sits in its gold unit
  run      chunk -> embed -> store A/B/C -> reload check -> benchmark -> traces

Run from repo root:  starter/.venv/Scripts/python -m src.run <stage>
(on macOS/linux: starter/.venv/bin/python -m src.run <stage>)
"""
import json
import sys
import time
from pathlib import Path

from . import ingestion
from .chunking import by_paragraph, fixed_size
from .embeddings import GeminiEmbedder
from .evaluation import evaluate_query, match_key, summarize
from .models import Chunk, DocumentPage
from .store import ChromaStore

STARTER = Path(__file__).resolve().parents[1]
REPO = STARTER.parent
DATA = REPO / "data"
RESULTS = REPO / "results"
QUESTIONS = REPO / "benchmark" / "questions.json"
CHROMA_DIR = STARTER / ".chroma"


def stage_ingest() -> list[DocumentPage]:
    pages = ingestion.load_corpus(REPO)
    ingestion.write_manifest(pages, DATA / "manifest.json")
    RESULTS.mkdir(exist_ok=True)
    dump = RESULTS / "units_readable.md"
    lines = [f"# Corpus units ({len(pages)} units)\n"]
    for p in pages:
        lines.append(f"\n## [{p.document_id}] page {p.page} — {p.metadata['unit_chars']} chars\n")
        lines.append(p.text)
    dump.write_text("\n".join(lines), encoding="utf-8")
    total = sum(p.metadata["unit_chars"] for p in pages)
    print(f"ingest OK: {len(pages)} units, {total} chars -> data/manifest.json, {dump}")
    return pages


def stage_verify() -> None:
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    pages = {(p.document_id, p.page): p for p in ingestion.load_corpus(REPO)}
    failures = 0
    for q in questions:
        golds = [{"source_id": q["gold_source_id"], "page": q["gold_page"],
                  "evidence": q["evidence_quote"]}] + q.get("alt_gold", [])
        ok = False
        for g in golds:
            page = pages.get((g["source_id"], g["page"]))
            if page and match_key(g["evidence"]) in match_key(page.text):
                ok = True
            else:
                print(f"  MISS {q['id']} gold {g['source_id']} p{g['page']}")
        status = "OK " if ok else "FAIL"
        failures += 0 if ok else 1
        print(f"{status} {q['id']} [{q['split']}] {len(golds)} gold(s)")
    if failures:
        sys.exit(f"{failures} question(s) have unverified evidence - fix before running")
    print(f"verify OK: {len(questions)} questions, all evidence found in gold units")


def stage_run() -> None:
    RESULTS.mkdir(exist_ok=True)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    pages = ingestion.load_corpus(REPO)

    t0 = time.perf_counter()
    chunks_A, chunks_B = [], []
    for p in pages:
        chunks_A.extend(fixed_size(p, size=500, overlap=50))
        chunks_B.extend(by_paragraph(p, max_size=900))
    # C = B's chunks verbatim (same text/vectors); C only differs by filtering at search time
    chunks_C = [Chunk(chunk_id=c.chunk_id, document_id=c.document_id, source=c.source,
                      page=c.page, text=c.text,
                      metadata={**c.metadata, "strategy": "C"})
                for c in chunks_B]

    embedder = GeminiEmbedder()
    store = ChromaStore(CHROMA_DIR, embedder.dimensions)
    stats = {}
    for name, chunks in (("A", chunks_A), ("B", chunks_B), ("C", chunks_C)):
        t = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in chunks])
        store.upsert(name, chunks, vectors)
        lengths = sorted(len(c.text) for c in chunks)
        stats[name] = {
            "chunk_count": len(chunks),
            "total_chars": sum(lengths),
            "min_len": lengths[0], "median_len": lengths[len(lengths) // 2],
            "max_len": lengths[-1],
            "ingest_seconds": round(time.perf_counter() - t, 1),
        }
        print(f"strategy {name}: {len(chunks)} chunks embedded+stored in {stats[name]['ingest_seconds']}s")

    # reload/idempotency check: re-upsert strategy B for one book, count must not change
    before = store.count("B")
    alice_pages = [p for p in pages if p.document_id == "alice"]
    rechunks = [c for p in alice_pages for c in by_paragraph(p, max_size=900)]
    store.upsert("B", rechunks, embedder.embed_documents([c.text for c in rechunks]))
    after = store.count("B")
    reload_ok = before == after
    (RESULTS / "reload_check.txt").write_text(
        f"Re-ingested alice into B: count {before} -> {after} "
        f"({'no duplication, OK' if reload_ok else 'DUPLICATION DETECTED'})\n", encoding="utf-8")
    print(f"reload check: {before} -> {after} ({'OK' if reload_ok else 'FAILED'})")

    traces = []
    query_cache: dict[str, list[float]] = {}
    for q in questions:
        if q["question"] not in query_cache:
            query_cache[q["question"]] = embedder.embed_query(q["question"])
        qvec = query_cache[q["question"]]
        for strategy in ("A", "B", "C"):
            use_filter = q.get("filter") if strategy == "C" else None
            hits = store.search(strategy, qvec, top_k=3, filters=use_filter)
            result = evaluate_query(q, hits)
            traces.append({
                "strategy": strategy, "split": q["split"], **result,
                "question": q["question"], "filter_applied": use_filter,
                "expected_answer": q["expected_answer"],
                "top3": hits,
            })
            time.sleep(0.3)

    (RESULTS / "traces.json").write_text(
        json.dumps(traces, indent=2, ensure_ascii=False), encoding="utf-8")
    metrics = {
        "model": embedder.model_name, "dimensions": embedder.dimensions,
        "embedding_api_calls": embedder.calls,
        "store": f"chromadb persistent @ {CHROMA_DIR.name}/, cosine",
        "strategies": stats, "reload_ok": reload_ok,
        "metrics": summarize(traces),
    }
    (RESULTS / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(metrics["metrics"], indent=2))
    print(f"done: results/traces.json, results/metrics.json "
          f"(total {time.perf_counter() - t0:.0f}s, {embedder.calls} API calls)")


def main() -> None:
    stages = {"ingest": stage_ingest, "verify": stage_verify, "run": stage_run}
    if len(sys.argv) != 2 or sys.argv[1] not in stages:
        sys.exit(f"usage: python -m src.run {{{'|'.join(stages)}}} (from starter/)")
    stages[sys.argv[1]]()


if __name__ == "__main__":
    main()
