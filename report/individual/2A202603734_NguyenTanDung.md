# Báo cáo cá nhân — Day 6

Học viên: **Nguyễn Tấn Dũng — 2A202603734 — L3B**

## Dữ liệu và pipeline
- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:** 3 tiểu thuyết public domain từ Project Gutenberg: *Alice's Adventures in Wonderland* (ebook #11), *The Adventures of Sherlock Holmes* (#1661), *Dracula* (#345). Văn bản chữ thuần, không hình ảnh/bảng biểu. Không có phân trang PDF nên dùng **pseudo-page**: ~27.000 ký tự đầu mỗi sách (sau khi bỏ boilerplate Gutenberg và mục lục), cắt tại ranh giới đoạn văn thành các unit ≥1.500 ký tự chuẩn hóa (~1.800 ký tự/unit) → **35 units, 80.930 ký tự**. Chi tiết trong [data/manifest.json](../../data/manifest.json) (source_id, url, license, accessed_at, số ký tự từng unit, quy tắc tính).
- **Chuẩn hóa, lỗi và giới hạn:** Unicode NFC, bỏ ký tự gạch dưới nghiêng của Gutenberg, tag `[Illustration]`, gộp space/xuống dòng; bỏ mục lục bằng heuristic (≥5 dòng heading sát nhau đầu file). Giới hạn: chỉ lấy phần đầu mỗi sách (27k ký tự) — corpus không phủ toàn bộ tác phẩm; không có OCR (text thuần).
- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:** `gemini-embedding-001` (Gemini API, REST, outputDimensionality=768; taskType RETRIEVAL_DOCUMENT cho chunk, RETRIEVAL_QUERY cho query; batch 10 + backoff khi 429). Store: **chromadb 1.5.9** PersistentClient tại `starter/.chroma/`, 3 collection `day6_A/B/C`, space cosine (exact HNSW search). Lệnh chạy: `python -m src.run ingest|verify|run` (xem starter/README.md). Chi phí: 0 USD (free tier), ~75 API calls, 312s.
- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:** `document_id`, `source`, `page` (unit index) gắn từ unit khi chunk; trường lọc **`book`** (alice/sherlock/dracula) — giá trị có thật từ nguồn, phân biệt rõ 3 miền nội dung, cho phép giới hạn truy xuất trong 1 sách.

## Cấu hình và benchmark
- **A / B / C:**
  - **A** — fixed-size 500 ký tự, overlap 50; không filter.
  - **B** — nhóm nguyên đoạn văn ≤900 ký tự (đoạn quá dài tách tại ranh giới câu); không filter.
  - **C** — chunk giống hệt B; chỉ khác: áp filter `book` khi câu hỏi cung cấp (4/20 câu).
- **≥20 câu:** 20 câu (15 dev / 5 test, tách cố định trước khi chạy thử), loại: direct (7), paraphrase (5), conditional (4), **filter (4 — q11, q12, q13 dev; q19 test)**. Mỗi câu có `expected_answer`, `gold_source_id`, `gold_page`, `evidence_quote`; evidence được **kiểm chứng tự động** (`src.run verify`: quote whitespace-insensitive phải nằm trong gold unit — 20/20 OK). Xem [benchmark/questions.json](../../benchmark/questions.json).
- **Tiêu chí chọn chiến lược đã chốt trước khi xem test:** ưu tiên (1) Evidence Hit@3, (2) Hit@1, (3) coherence, (4) chi phí embedding.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 8/15 | 14/15 | 199 | 112.8s | 0 USD |
| A | test | 3/5 | 5/5 | 199 | (gộp) | 0 USD |
| B | dev | 13/15 | 14/15 | 118 | 64.4s | 0 USD |
| B | test | 3/5 | 5/5 | 118 | (gộp) | 0 USD |
| C | dev | 13/15 | 14/15 | 118 | 74.3s | 0 USD |
| C | test | 3/5 | 5/5 | 118 | (gộp) | 0 USD |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1.4 (10 vị trí) | 15/15 | N/A (không filter) | 0:0, 1:0, 2:5 → 2.0 |
| B | 2.0 (10 vị trí) | 15/15 | N/A (không filter) | 0:0, 1:0, 2:5 → 2.0 |
| C | 2.0 (10 vị trí) | 15/15 | 4/4 (q11, q12, q13, q19) | 0:0, 1:0, 2:5 → 2.0 |

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Trace top-3 đầy đủ: [results/traces.json](../../results/traces.json); metrics tổng: [results/metrics.json](../../results/metrics.json); kiểm tra nạp lại không nhân đôi: [results/reload_check.txt](../../results/reload_check.txt).
- Nhãn thủ công 5 khía cạnh: [results/manual_audit.md](../../results/manual_audit.md) (người chấm = tác giả, ghi rõ nguy cơ thiên lệch); mẫu sinh tự động: [results/audit_samples.json](../../results/audit_samples.json), [results/filter_compliance.json](../../results/filter_compliance.json).
- Mẫu coherence: **10 vị trí giữa unit** (dòng chứa điểm giữa, sort theo document_id+page), cùng 10 vị trí cho A và B; dùng probe 25 ký tự đầu dòng để tìm chunk bao phủ (vì window A có thể cắt giữa dòng).

## Phân tích và kết luận
- **So sánh A–B:** A (+69% chunk: 199 vs 118) cắt giữa câu → Hit@1 dev giảm 8/15 vs 13/15, coherence 1.4 vs 2.0; 2/2 vị trí bị chia đôi dòng thuộc A; ví dụ thất bại đặc trưng **q07** (dracula:p1): trích dẫn ~250 ký tự vắt qua 2 window → không chunk nào chứa đủ evidence (mất Hit@3 duy nhất của A). **So sánh B–C:** 16/20 câu không filter → C chạy y hệt B (kết quả giống từng câu); 4 câu filter C tuân thủ 4/4 và không mất hit — chứng minh metadata `book` hữu ích mà không gây side-effect.
- **Chiến lược chọn:** B (và C khi câu hỏi có ngữ cảnh sách) — cùng Hit@3, Hit@1 và coherence cao hơn, chi phí thấp hơn A. Điều kiện áp dụng: corpus có trường metadata phân biệt được và câu hỏi nêu rõ phạm vi.
- **Ví dụ sai:** (1) A/q07 — evidence bị chia đôi qua window, chi tiết ở manual_audit.md; (2) B+C/q12 (sherlock:p9) — chunk p9 được rút là nửa đầu unit, không chứa câu "the Langham" → Hit@3 = 0, trong khi A lại hit top-1.
- **Hạn chế:** chỉ lấy 27k ký tự đầu mỗi sách (không phủ toàn tác phẩm); test chỉ 5 câu → không kết luận tổng quát; chấm tay do chính tác giả thực hiện (thiên lệch không mù); grounding đều 2.0 vì test đều là câu dễ và Hit@3 = 5/5; chi phí đo trên free tier nên không phản ánh giá thương mại.
- **Nếu làm lại:** lấy corpus đầy đủ hơn hoặc nhiều đầu sách; thêm trường metadata thứ hai (section) để thử filter phức tạp hơn; tăng test lên ≥10 câu có câu khó; thử hybrid BM25+dense (mở rộng tùy chọn của lab).
