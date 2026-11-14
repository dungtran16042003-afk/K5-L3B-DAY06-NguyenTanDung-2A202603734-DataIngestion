# Starter · Chroma (lite, no Docker)

Bộ khởi động **đã hiện thực** cho lab cá nhân, phương án "lite" theo hướng dẫn:
**Chroma embedded** (lưu bền vững trên đĩa, vector search cosine, metadata filter)
thay cho PostgreSQL + pgvector/Docker. Không cần Docker, không cần server, không
cần key ngoài Gemini API.

## Cấu trúc

```text
starter/
├── .env.example           # cấu hình mẫu; copy thành .env rồi điền GEMINI_API_KEY
├── requirements.txt       # chromadb, requests, python-dotenv
├── src/
│   ├── models.py          # DocumentPage / Chunk (giữ traceability)
│   ├── ingestion.py       # đọc/normalize sách Gutenberg -> units ≥1500 ký tự + manifest
│   ├── chunking.py        # A: fixed 500/50 · B: paragraph ≤900
│   ├── embeddings.py      # Gemini REST (batch 10 + retry khi 429)
│   ├── store.py           # Chroma persistent, 1 collection/strategy, upsert idempotent
│   ├── evaluation.py      # Hit@1 / Evidence Hit@3 + matcher whitespace-insensitive
│   ├── audit.py           # sinh mẫu chấm tay (coherence/metadata/grounding)
│   └── run.py             # 3 stage: ingest | verify | run
├── data/                  # để trống (corpus nằm ở ../data/books)
└── .chroma/               # dữ liệu vector (gitignored, tạo khi chạy)
```

## Chạy

```bash
cd starter
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1  (macOS/Linux: source .venv/bin/activate)
python -m pip install -r requirements.txt
# copy .env.example thành .env và điền GEMINI_API_KEY

.venv/Scripts/python -m src.run ingest    # đọc corpus, ghi data/manifest.json + results/units_readable.md
.venv/Scripts/python -m src.run verify    # kiểm chứng 20/20 evidence nằm đúng gold unit
.venv/Scripts/python -m src.run run       # chunk -> embed -> store A/B/C -> trace -> metrics
.venv/Scripts/python -m src.audit         # sinh results/audit_samples.json + filter_compliance.json
```

(Khi venv đã kích hoạt thì chỉ cần `python -m src.run ...`.)

## Embedding model & store

- **Model:** `gemini-embedding-001` qua REST API, `outputDimensionality=768`,
  `taskType` = `RETRIEVAL_DOCUMENT` cho chunk / `RETRIEVAL_QUERY` cho câu hỏi.
  Batch 10 text/request + backoff khi 429 (quota phút của free tier).
- **Store:** chromadb `PersistentClient` tại `starter/.chroma/`, 3 collection
  `day6_A/B/C`, space `cosine`. Stable chunk IDs (`<strategy>:<doc>:p<page>:c<seq>`)
  → upsert lại không nhân đôi (đã kiểm chứng: results/reload_check.txt).

## Chi phí & thời gian

Free tier Gemini embedding → chi phí 0 USD. Toàn bộ pipeline ~5 phút trên máy
local (312s: 435 vectors, 75 API calls, gồm thời gian chờ retry).
