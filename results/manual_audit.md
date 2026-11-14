# Manual audit — 5 evaluation dimensions

Người chấm: tác giả bài làm (self-audit). Nguy cơ thiên lệch: người chấm là người
viết pipeline và viết bộ câu hỏi, không chấm mù; nhãn chỉ dựa trên text chunk và
định nghĩa thang điểm trong GUIDE.md, xem trước khi biết điểm từng chiến lược.

## 1. Retrieval accuracy (tự động, results/metrics.json)

| Strategy | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 |
|---|---|---|---|---|
| A | 8/15 | 14/15 | 3/5 | 5/5 |
| B | 13/15 | 14/15 | 3/5 | 5/5 |
| C | 13/15 | 14/15 | 3/5 | 5/5 |

## 2. Chunk coherence — 10 vị trí giữa unit (cùng 10 vị trí cho A và B)

Thang: 0 = vị trí bị cắt giữa ý/không hiểu; 1 = hiểu một phần, thiếu ngữ cảnh
(chunk bắt đầu giữa câu, thiếu chủ thể); 2 = tự hiểu, giữ trọn ý (chunk chứa đầu
đoạn/câu chứa vị trí). Quy tắc chốt trước khi chấm: 2 nếu chunk chứa ĐẦU câu/đoạn
chứa vị trí; 1 nếu vị trí nằm trong chunk nhưng đầu câu bị cắt ở window trước;
0 nếu chính dòng vị trí bị chia đôi qua 2 chunk.

| Vị trí | A label | A lý do | B label | B lý do |
|---|---|---|---|---|
| alice:p1:mid | 1 | window bắt đầu giữa câu, chủ thể "Alice" bị cắt ở window trước | 2 | chứa nguyên đoạn văn từ đầu |
| alice:p2:mid | 2 | đầu câu chứa vị trí nằm trong window | 2 | nguyên đoạn |
| alice:p3:mid | 1 | window bắt đầu giữa từ ("rst thought"), đầu câu bị cắt | 2 | nguyên đoạn |
| alice:p4:mid | 2 | đầu câu "if you drink much..." nằm trong window | 2 | nguyên đoạn |
| alice:p5:mid | 2 | đầu câu chứa vị trí nằm trong window | 2 | nguyên đoạn |
| alice:p6:mid | 0 | dòng vị trí bị chia đôi qua c1/c2 ("and h" cắt giữa lời thoại) | 2 | nguyên đoạn |
| alice:p7:mid | 2 | đầu câu chứa vị trí nằm trong window | 2 | nguyên đoạn |
| alice:p8:mid | 2 | đầu đoạn nằm trong window | 2 | chunk bắt đầu đúng đầu đoạn |
| alice:p9:mid | 0 | dòng vị trí cắt giữa line ("splashing about in" hết chunk) | 2 | nguyên đoạn |
| alice:p10:mid | 2 | đầu câu chứa vị trí nằm trong window | 2 | nguyên đoạn |

**Coherence trung bình: A = 14/20 = 1.4/2 · B = 20/20 = 2.0/2**

## 3. Metadata usefulness — 5 câu test × top-3 × 3 chiến lược = 45 bản ghi

Kiểm tra `document_id`, `source`, `page`, `book` có mặt và đúng với nguồn của chunk:
- Trường đủ: 45/45 (không bản ghi thiếu trường — Chroma lưu đầy đủ metadata khi upsert)
- Giá trị đúng so với nguồn: 45/45 (metadata sinh trực tiếp từ unit khi chunk, không có sai)
- Filter compliance (chiến lược C, 4 câu filter): top-3 tuân thủ filter 4/4
  (q11 book=dracula ✓, q12 book=sherlock ✓, q13 book=alice ✓, q19 book=dracula ✓)
- Trường hữu ích: `book` cho phép C giới hạn top-3 trong đúng 1 sách (4/4) và
  `page`+`source` truy vết được unit gốc cho mọi chunk. Hạn chế: corpus chỉ có
  1 trường lọc phân biệt được (book); chưa thử tổ hợp nhiều trường.

**Metadata đủ và đúng: 45/45 · Filter tuân thủ: 4/4**

## 4. Grounding quality — 5 câu test × 3 chiến lược (thang 0–2 trên top-3)

0 = không có bằng chứng; 1 = có nhưng thiếu điều kiện/ngữ cảnh; 2 = đủ để trả lời
và truy nguồn. Lý do chung: mọi câu test đều có ít nhất 1 chunk trong top-3 chứa
đủ evidence đã kiểm chứng (Evidence Hit@3 = 5/5 ở cả 3 chiến lược).

| Câu | A | B | C | Lý do |
|---|---|---|---|---|
| q16 | 2 | 2 | 2 | top-1 chứa trọn câu Deutsch + bản dịch |
| q17 | 2 | 2 | 2 | top-1 chứa câu tiếng Pháp + cảnh tượng chuột sợ |
| q18 | 2 | 2 | 2 | top-1 (A) / top-2 (B, C) chứa trọn lời Holmes về data |
| q19 | 2 | 2 | 2 | top-1 chứa trích Crucifix |
| q20 | 2 | 2 | 2 | top-1/top-3 chứa đoạn lễ cưới St. Monica |

**Grounding trung bình: A = B = C = 2.0/2 (10/10 mỗi chiến lược)** — lưu ý test
chỉ 5 câu và đều là câu dễ; không suy rộng ra bộ khó hơn.

## 5. Data strategy impact

- **A–B (thay chunking):** A = 199 chunks vs B = 118 chunks (+69% chunk, +69% chi
  phí embedding cho A). A cắt giữa câu → dev Hit@1 giảm rõ (8/15 vs 13/15) và
  coherence giảm (1.4 vs 2.0); 2/2 vị trí bị chia đôi dòng đều thuộc A. Ví dụ
  thất bại đặc trưng của A: q07 — evidence "paprika hendl" nằm vắt qua 2 window
  nên không chunk nào trong top-3 chứa đủ (Evidence Hit@3 duy nhất A mất).
  Ngược lại A vẫn thắng q12 (hit ngay top-1) nhờ window nhỏ khớp chính xác câu.
- **B–C (thay metadata filter):** C = B về chunking; khác duy nhất là filter khi
  câu hỏi cung cấp `book`. 16/20 câu không filter → C chạy như B, kết quả giống
  hệt nhau. Trên 4 câu filter, C đạt 4/4 tuân thủ filter và giữ hit như B — filter
  không làm mất kết quả đúng, chứng minh metadata `book` thực sự hữu ích.
- **Kết luận:** chọn B (hoặc C) làm chiến lược chính: cùng Hit@3, Hit@1 và
  coherence cao hơn A rõ rệt, chi phí embedding thấp hơn. C chỉ vượt B khi câu hỏi
  có ngữ cảnh sách (filter) — về nguyên tắc B+C là cấu hình nên dùng.
- **Sai số mẫu nhỏ:** 5 câu test không đủ để tuyên bố chiến lược tốt nhất tổng
  quát; mọi kết luận chỉ trong phạm vi corpus 3 sách này.

## Ví dụ lỗi chi tiết (có ID câu, nguồn)

1. **A / q07** (`dracula:p1`): hỏi món ăn của Harker ở Klausenburgh. Top-3 của A
   gồm 2 chunk p1 không chứa trích dẫn và 1 chunk p5; trích dẫn "…called
   "paprika hendl"…" dài ~250 ký tự, bị window 500/50 cắt nên không chunk nào
   chứa đủ → Evidence Hit@3 = 0. B giữ nguyên đoạn → hit.
2. **B+C / q12** (`sherlock:p9`): hỏi tên giả của Vua ở London. Top-3 gồm p7, p6,
   p9; chunk p9 được rút là nửa đầu unit (trước câu "the Langham") nên không chứa
   evidence → Evidence Hit@3 = 0. A (window 500) lại hit top-1 chính xác câu đó.
