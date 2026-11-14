"""Gemini embedding via REST (no SDK): gemini-embedding-001, batched.

Documents use task_type RETRIEVAL_DOCUMENT, queries RETRIEVAL_QUERY, per model
docs. outputDimensionality=768 (Matryoshka truncation, officially supported) to
keep the store light. No mock fallback: API errors propagate to the caller.
"""
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}"
# Small batches: free-tier TPM quota is per minute, and ~50 long texts in one
# request can exceed it (429). 10 texts + pauses keeps each request small.
BATCH_SIZE = 10
PAUSE_SECONDS = 3


class GeminiEmbedder:
    def __init__(self, model_name: str | None = None, dims: int | None = None) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY missing in starter/.env")
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        self.dimensions = dims or int(os.getenv("EMBEDDING_DIMS", "768"))
        self.calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            out.extend(self._batch(batch, "RETRIEVAL_DOCUMENT"))
            time.sleep(PAUSE_SECONDS)
        return out

    def embed_query(self, question: str) -> list[float]:
        return self._batch([question], "RETRIEVAL_QUERY")[0]

    def _batch(self, texts: list[str], task_type: str) -> list[list[float]]:
        payload = {"requests": [
            {"model": f"models/{self.model_name}",
             "content": {"parts": [{"text": t}]},
             "taskType": task_type,
             "outputDimensionality": self.dimensions}
            for t in texts
        ]}
        for attempt in range(5):
            resp = requests.post(
                API_URL.format(model=self.model_name, method="batchEmbedContents"),
                json=payload, headers={"x-goog-api-key": self.api_key}, timeout=120)
            self.calls += 1
            if resp.status_code == 200:
                vectors = [e["values"] for e in resp.json()["embeddings"]]
                if len(vectors) != len(texts) or any(len(v) != self.dimensions for v in vectors):
                    raise RuntimeError(f"Unexpected embedding response shape for {len(texts)} texts")
                return vectors
            if resp.status_code in (429, 500, 503) and attempt < 6:
                wait = min(2 ** attempt * 5, 60)
                print(f"    rate-limited ({resp.status_code}), waiting {wait}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
        raise RuntimeError("unreachable")
