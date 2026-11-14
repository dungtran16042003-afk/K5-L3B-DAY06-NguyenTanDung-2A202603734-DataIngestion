"""Read and normalize plain-text books (Project Gutenberg), build traceable units.

Unit = pseudo-page: sequential cut of the body at paragraph boundaries, each with
at least UNIT_MIN_CHARS normalized characters (guide: >=1500). Keeps book id,
page number and char counts for the manifest.
"""
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

from .models import DocumentPage

# Corpus config: which book, where, and how much of it we keep (first N chars of body).
BOOKS = {
    "alice": {
        "title": "Alice's Adventures in Wonderland",
        "path": "data/books/alice.txt",
        "url": "https://www.gutenberg.org/ebooks/11",
        "max_chars": 27000,
    },
    "sherlock": {
        "title": "The Adventures of Sherlock Holmes",
        "path": "data/books/sherlock.txt",
        "url": "https://www.gutenberg.org/ebooks/1661",
        "max_chars": 27000,
    },
    "dracula": {
        "title": "Dracula",
        "path": "data/books/dracula.txt",
        "url": "https://www.gutenberg.org/ebooks/345",
        "max_chars": 27000,
    },
}
UNIT_MIN_CHARS = 1500
UNIT_TARGET_CHARS = 1800


def normalize_text(text: str) -> str:
    """NFC normalize, drop Gutenberg italic underscores and illustration tags,
    tidy whitespace."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\ufeff", "")
    text = text.replace("_", "")
    text = re.sub(r"\[Illustration\]?", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_txt(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Strip Gutenberg boilerplate and table of contents, normalize, cut units."""
    raw = path.read_text(encoding="utf-8")
    body = strip_boilerplate(raw)
    body = skip_toc(body)
    body = normalize_text(body)
    body = body[: BOOKS[document_id]["max_chars"]]
    return cut_units(body, document_id, source)


def strip_boilerplate(raw: str) -> str:
    start = re.search(r"\*\*\* START OF .*?\*\*\*", raw, re.S)
    end = re.search(r"\*\*\* END OF .*?\*\*\*", raw, re.S)
    if start and end:
        return raw[start.end():end.start()].strip()
    return raw.strip()  # no markers found: log caller treats whole file as body


def skip_toc(body: str) -> str:
    """Drop a leading table of contents: a run of >=5 heading-like lines close
    together near the top (real body headings are thousands of chars apart)."""
    head = body[:6000]
    matches = list(re.finditer(r"^[ \t]*(CHAPTER [IVXLC]+.*|[IVXLC]+\. .+?)[ \t]*$", head, re.M))
    if len(matches) >= 5:
        run_end, run_len = matches[0].end(), 1
        for m in matches[1:]:
            if m.start() - run_end > 300:  # gap too big: TOC run ended
                break
            run_end, run_len = m.end(), run_len + 1
        if run_len >= 5:
            return body[run_end:].lstrip("\n ")
    return body


def cut_units(body: str, document_id: str, source: str) -> list[DocumentPage]:
    """Accumulate paragraphs into units of ~UNIT_TARGET chars, min UNIT_MIN_CHARS."""
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    units, current = [], []
    for para in paragraphs:
        current.append(para)
        if sum(len(p) for p in current) >= UNIT_TARGET_CHARS:
            units.append("\n\n".join(current))
            current = []
    if current:  # merge a short trailing remainder into the last full unit
        if units and sum(len(p) for p in current) < UNIT_MIN_CHARS:
            units[-1] += "\n\n" + "\n\n".join(current)
        else:
            units.append("\n\n".join(current))
    pages = []
    for i, text in enumerate(units, start=1):
        if len(text) < UNIT_MIN_CHARS:
            raise ValueError(f"{document_id} unit {i} too short ({len(text)} chars)")
        pages.append(DocumentPage(
            document_id=document_id, source=source, page=i, text=text,
            metadata={"title": BOOKS[document_id]["title"], "book": document_id,
                      "unit_chars": len(text)},
        ))
    return pages


def load_corpus(repo_root: Path) -> list[DocumentPage]:
    pages = []
    for book_id in BOOKS:
        path = repo_root / BOOKS[book_id]["path"]
        pages.extend(load_txt(path, book_id, BOOKS[book_id]["url"]))
    return pages


def write_manifest(pages: list[DocumentPage], out_path: Path) -> None:
    """Manifest per GUIDE: source id, title, url, license, accessed_at, units, chars."""
    by_book: dict[str, list[DocumentPage]] = {}
    for p in pages:
        by_book.setdefault(p.document_id, []).append(p)
    manifest = {
        "generated_at": date.today().isoformat(),
        "selection_rule": (
            "First ~27000 normalized chars of each book body after removing Project "
            "Gutenberg boilerplate and table of contents; units cut at paragraph "
            "boundaries, each >=1500 normalized chars (pseudo-pages)."
        ),
        "unit_rule": (
            "Accumulate paragraphs until ~1800 chars; short trailing remainder merged "
            "into the previous unit. page = 1-based unit index within each book."
        ),
        "sources": [],
    }
    for book_id, book_pages in by_book.items():
        manifest["sources"].append({
            "source_id": book_id,
            "title": BOOKS[book_id]["title"],
            "source_path_or_url": BOOKS[book_id]["url"],
            "local_path": BOOKS[book_id]["path"],
            "license_or_permission": "Public domain in the US; Project Gutenberg License",
            "accessed_at": "2026-11-14",
            "gutenberg_ebook": book_id.replace("alice", "11").replace("sherlock", "1661").replace("dracula", "345"),
            "unit_count": len(book_pages),
            "total_chars": sum(p.metadata["unit_chars"] for p in book_pages),
            "units": [{"page": p.page, "chars": p.metadata["unit_chars"]} for p in book_pages],
        })
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
