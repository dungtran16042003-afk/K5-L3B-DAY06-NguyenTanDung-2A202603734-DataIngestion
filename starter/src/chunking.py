"""Chunking strategies: A fixed-size windows, B paragraph grouping."""
import re

from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Strategy A: hard character windows, may cut mid-sentence by design."""
    step = size - overlap
    chunks = []
    start, seq = 0, 0
    while start < len(page.text):
        window = page.text[start:start + size]
        if window.strip():
            chunks.append(_make_chunk(page, seq, window,
                                      {"strategy": "A", "size": size, "overlap": overlap}))
            seq += 1
        start += step
    return chunks


def by_paragraph(page: DocumentPage, max_size: int = 900) -> list[Chunk]:
    """Strategy B: group whole paragraphs up to max_size; split oversized
    paragraphs at sentence boundaries so no chunk exceeds the limit."""
    paragraphs = [p for p in page.text.split("\n\n") if p.strip()]
    groups, current = [], []
    for para in paragraphs:
        if not current and len(para) > max_size:
            groups.extend(_split_long_paragraph(para, max_size))
            continue
        if current and sum(len(p) for p in current) + len(para) + 2 > max_size:
            groups.append("\n\n".join(current))
            current = []
        current.append(para)
    if current:
        groups.append("\n\n".join(current))
    return [_make_chunk(page, seq, text, {"strategy": "B", "max_size": max_size})
            for seq, text in enumerate(groups) if text.strip()]


def _split_long_paragraph(para: str, max_size: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", para)
    parts, current = [], ""
    for sent in sentences:
        if current and len(current) + len(sent) + 1 > max_size:
            parts.append(current)
            current = ""
        current = (current + " " + sent).strip()
    if current:
        parts.append(current)
    return parts


def _make_chunk(page: DocumentPage, seq: int, text: str, extra: dict) -> Chunk:
    metadata = dict(page.metadata)
    metadata.update(extra)
    return Chunk(
        chunk_id=f"{page.document_id}:p{page.page}:c{seq}",
        document_id=page.document_id, source=page.source, page=page.page,
        text=text, metadata=metadata,
    )
