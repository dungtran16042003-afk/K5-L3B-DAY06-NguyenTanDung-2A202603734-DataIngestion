"""Chroma persistent vector store: one collection per strategy, cosine space.

Stable chunk IDs make upsert idempotent -> re-ingest never duplicates.
Search filters on metadata (strategy C) via Chroma `where`; scores are cosine
similarity (1 - cosine distance)."""
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from .models import Chunk

STRATEGIES = ("A", "B", "C")


class ChromaStore:
    def __init__(self, persist_dir: Path, dimensions: int) -> None:
        self.dimensions = dimensions
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )

    def collection(self, strategy: str):
        return self.client.get_or_create_collection(
            name=f"day6_{strategy}", metadata={"hnsw:space": "cosine"})

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"chunks/vectors length mismatch: {len(chunks)} vs {len(vectors)}")
        for v in vectors:
            if len(v) != self.dimensions:
                raise ValueError(f"vector dim {len(v)} != configured {self.dimensions}")
        self.collection(strategy).upsert(
            ids=[f"{strategy}:{c.chunk_id}" for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[self._meta(c) for c in chunks],
        )

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where = None
        if filters:
            where = {k: {"$eq": v} for k, v in filters.items()}
        res = self.collection(strategy).query(
            query_embeddings=[query_vector], n_results=top_k, where=where)
        hits = []
        for i, chunk_id in enumerate(res["ids"][0]):
            distance = res["distances"][0][i]
            hits.append({
                "chunk_id": chunk_id,
                "text": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": round(float(distance), 4),
                "similarity": round(1.0 - float(distance), 4),
            })
        return hits

    def count(self, strategy: str) -> int:
        return self.collection(strategy).count()

    @staticmethod
    def _meta(c: Chunk) -> dict[str, Any]:
        m = dict(c.metadata)
        m["document_id"] = c.document_id
        m["source"] = c.source
        m["page"] = c.page
        return m
