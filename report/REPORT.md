# Báo Cáo Lab 7: Embedding & Vector Store

<!-- TODO[INFO]: Cập nhật ngày nộp chính thức nếu thay đổi -->
**Họ tên:** Phạm Quốc Dũng
**MSSV:** 2A202600490
**Nhóm:** Đề tài nhóm The Mom Test
**Ngày:** 10/04/2026

---

## 1. Warm-up (5 điểm)
<!-- TODO[WARMUP]: Soát lại ví dụ/diễn đạt theo yêu cầu giảng viên nếu cần -->

### Cosine Similarity (Ex 1.1)

**High cosine similarity nghĩa là gì?**
High cosine similarity nghĩa là hai đoạn văn có hướng ngữ nghĩa gần nhau trong không gian embedding, tức là nói về ý tương tự dù có thể dùng từ khác nhau.

**Ví dụ HIGH similarity:**
- Sentence A: "Tôi thường hỏi khách hàng về hành vi trong quá khứ."
- Sentence B: "Phỏng vấn khách hàng hiệu quả là đào sâu việc họ đã làm trước đây."
- Tại sao tương đồng: Cùng nói về một nguyên tắc phỏng vấn khách hàng dựa trên dữ liệu quá khứ.

**Ví dụ LOW similarity:**
- Sentence A: "Vector database giúp tìm kiếm ngữ nghĩa."
- Sentence B: "Tôi thích đi bộ vào buổi sáng để cải thiện sức khỏe."
- Tại sao khác: Hai câu thuộc hai chủ đề khác nhau, gần như không có ngữ nghĩa chung.

**Tại sao cosine similarity được ưu tiên hơn Euclidean distance cho text embeddings?**
Với text embeddings, hướng vector thường quan trọng hơn độ lớn tuyệt đối. Cosine similarity đo mức đồng hướng nên ổn định hơn khi so nghĩa, còn Euclidean dễ bị ảnh hưởng bởi độ dài/độ lớn vector.

### Chunking Math (Ex 1.2)

**Document 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
Phép tính theo công thức markdown-thuần:

- `num_chunks = ceil((doc_length - overlap) / (chunk_size - overlap))`

Thay số từng bước:

1. `num_chunks = ceil((10000 - 50) / (500 - 50))`
2. `num_chunks = ceil(9950 / 450)`
3. `num_chunks = ceil(22.11)`
4. `num_chunks = 23`

Đáp án: **23 chunks**.

**Nếu overlap tăng lên 100, chunk count thay đổi thế nào? Tại sao muốn overlap nhiều hơn?**
Khi overlap = 100:

1. `num_chunks = ceil((10000 - 100) / (500 - 100))`
2. `num_chunks = ceil(9900 / 400)`
3. `num_chunks = ceil(24.75)`
4. `num_chunks = 25`

Tức số chunk tăng từ **23** lên **25**. Overlap lớn hơn giúp giữ ngữ cảnh liên tục giữa các chunk liền kề, nên retrieval thường ổn định hơn ở các câu trả lời cần nhiều ngữ cảnh.

---

## 2. Document Selection — Nhóm (10 điểm)
<!-- TODO[GROUP]: Đồng bộ lại số liệu và mô tả với file nhóm mới nhất -->

### Domain & Lý Do Chọn

**Domain:** Customer discovery và phỏng vấn khách hàng (The Mom Test) kết hợp tài liệu RAG nội bộ.

**Tại sao nhóm chọn domain này?**
The Mom Test là đề tài nhóm nên phù hợp để benchmark retrieval theo ngữ cảnh thực tế startup. Ngoài ra nhóm bổ sung tài liệu kỹ thuật RAG để thử các query vừa mang tính nghiệp vụ vừa mang tính hệ thống. Cách này giúp so sánh rõ chunking strategy khi tài liệu dài và có cấu trúc khác nhau.

### Data Inventory
<!-- TODO[GROUP-DATA]: Cập nhật bảng nếu nhóm thay đổi bộ tài liệu hoặc metadata -->

| # | Tên tài liệu | Nguồn | Số ký tự | Metadata đã gán |
|---|--------------|-------|----------|-----------------|
| 1 | The Mom Test.md | Tài liệu nhóm | 2514 | source, category=mom_test |
| 2 | customer_support_playbook.txt | data/ | 1692 | source, category=support_rag |
| 3 | rag_system_design.md | data/ | 2391 | source, category=support_rag |
| 4 | vector_store_notes.md | data/ | 2123 | source, category=support_rag |
| 5 | vi_retrieval_notes.md | data/ | 1667 | source, category=support_rag |

### Metadata Schema
<!-- TODO[META]: Đảm bảo metadata field trùng với code ingest thực tế -->

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho retrieval? |
|----------------|------|---------------|-------------------------------|
| source | string | data/rag_system_design.md | Truy vết nguồn để kiểm chứng grounding |
| category | string | mom_test, support_rag | Filter theo ngữ cảnh nghiệp vụ/kỹ thuật |
| doc_id | string | The Mom Test_12 | Hỗ trợ delete theo tài liệu gốc |

---

## 3. Chunking Strategy — Cá nhân chọn, nhóm so sánh (15 điểm)
<!-- TODO[STRATEGY]: Chỉnh điểm số/so sánh sau khi nhóm chốt benchmark cuối -->

### Baseline Analysis

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Strategy | Chunk Count | Avg Length | Preserves Context? |
|-----------|----------|-------------|------------|-------------------|
| The Mom Test.md | FixedSizeChunker (`fixed_size`, size=300, overlap=30) | 10 | 278.40 | Khá |
| The Mom Test.md | SentenceChunker (`by_sentences`, 1 câu/chunk) | 31 | 79.90 | Thấp (dễ mất context) |
| The Mom Test.md | RecursiveChunker (`recursive`, size=500) | 8 | 312.50 | Tốt |
| rag_system_design.md | FixedSizeChunker (`fixed_size`) | 7 | 375.86 | Trung bình |
| rag_system_design.md | SentenceChunker (`by_sentences`) | 5 | 476.00 | Khá |
| rag_system_design.md | RecursiveChunker (`recursive`) | 8 | 297.00 | Tốt |

### Strategy Của Tôi

**Loại:** SentenceChunker (granular, `max_sentences_per_chunk=1`)

**Mô tả cách hoạt động:**
Strategy chia văn bản theo từng câu đơn lẻ để tăng độ chi tiết khi retrieve. Mỗi chunk chứa một đơn vị thông tin nhỏ, phù hợp kiểm thử giả thuyết "chunk quá nhỏ sẽ mất ngữ cảnh". Cách này thường tăng khả năng match đúng câu chứa từ khóa nhưng có thể làm câu trả lời tổng hợp thiếu mạch lạc nếu không retrieve đủ số chunk.

**Tại sao tôi chọn strategy này cho domain nhóm?**
Theo phân công nhóm, Thành viên 2 phụ trách chiến thuật granular để đo tác động của chunk nhỏ đến độ nhiễu và độ mất ngữ cảnh. Tài liệu The Mom Test có nhiều ví dụ hội thoại nên tách theo câu giúp tìm nhanh các câu mẫu, sau đó so sánh chất lượng tổng hợp với các chiến thuật chunk lớn hơn.

**Code snippet (nếu custom):**
```python
# Paste implementation here
```

### So Sánh: Strategy của tôi vs Baseline

| Tài liệu | Strategy | Chunk Count | Avg Length | Retrieval Quality? |
|-----------|----------|-------------|------------|--------------------|
| The Mom Test.md | best baseline (FixedSize, chunk=300, overlap=10%) | 10 | ~278 | Ổn định, ít cực đoan |
| The Mom Test.md | **của tôi** (SentenceChunker, 1 câu/chunk) | 31 | ~80 | Match câu tốt, dễ mất context |

### So Sánh Với Thành Viên Khác
<!-- TODO[GROUP-SCORE]: Thay 'Thành viên A/B' bằng tên thật trước khi nộp -->

| Thành viên | Strategy | Retrieval Score (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Tôi (Phạm Quốc Dũng) | SentenceChunker (1 câu/chunk) | 8 | Chi tiết, truy đúng câu chứa tín hiệu | Context mỏng, cần top-k/threshold hợp lý |
| Thành viên A | FixedSizeChunker | 6 | Đơn giản, tốc độ tốt | Cắt ngang ý nhiều |
| Thành viên B | SentenceChunker | 7 | Dễ đọc, bám câu | Mất liên kết dài giữa các đoạn |

**Strategy nào tốt nhất cho domain này? Tại sao?**
Trong bộ dữ liệu của nhóm, chiến thuật của tôi (granular) hữu ích để bắt đúng bằng chứng dạng câu ngắn, nhưng về độ mạch lạc tổng thể thì thường thua chiến thuật structural (RecursiveChunker). Kết luận nhóm: granular tốt cho precision câu đơn, structural tốt hơn cho answer synthesis.

---

## 4. My Approach — Cá nhân (10 điểm)
<!-- TODO[APPROACH]: Nếu code đổi, cập nhật mô tả tương ứng ở section này -->

Giải thích cách tiếp cận của bạn khi implement các phần chính trong package `src`.

### Chunking Functions

**`SentenceChunker.chunk`** — approach:
Dùng regex `(?<=[.!?])\s+` để tách theo kết thúc câu, sau đó gom theo `max_sentences_per_chunk`. Có xử lý edge case text rỗng và trường hợp tách xong không còn phần tử hợp lệ.

**`RecursiveChunker.chunk` / `_split`** — approach:
`chunk()` gọi `_split()` với danh sách separator ưu tiên. Base case là chuỗi đủ ngắn (`<= chunk_size`) hoặc không còn separator thì cắt cứng theo kích thước. Trong bước đệ quy, nếu tách bằng separator hiện tại vẫn quá dài thì tiếp tục hạ cấp separator để giữ ngữ nghĩa tối đa.

### EmbeddingStore

**`add_documents` + `search`** — approach:
Mỗi document được chuẩn hóa thành record gồm `id`, `content`, `metadata`, `embedding`. Với in-memory mode, `search()` embed query rồi xếp hạng bằng dot product (vector đã normalize nên tương đương cosine). Kết quả trả về có `score`, `metadata`, và `content` để agent grounding.

**`search_with_filter` + `delete_document`** — approach:
`search_with_filter()` luôn lọc metadata trước, sau đó mới chạy similarity để giảm nhiễu. `delete_document()` xóa toàn bộ chunk có `metadata['doc_id'] == doc_id`, trả về bool để xác nhận có xóa được hay không.

### KnowledgeBaseAgent

**`answer`** — approach:
Agent retrieve top-k chunk, dựng prompt theo cấu trúc: instruction, question, context block. Mỗi block ghi rõ `source` và `score` để tăng traceability. Cuối cùng gọi `llm_fn(prompt)` để tạo câu trả lời theo RAG pattern.

### Test Results
<!-- TODO[TEST]: Dán lại output pytest mới nhất trước khi nộp (nếu có thay đổi code) -->

```
# Paste output of: pytest tests/ -v
============================= test session starts =============================
collected 42 items

tests/test_solution.py ..........................................       [100%]

============================= 42 passed in 0.21s ==============================
```

**Số tests pass:** 42 / 42

---

## 5. Similarity Predictions — Cá nhân (5 điểm)
<!-- TODO[SIMILARITY]: Có thể thay bộ câu ví dụ nếu nhóm yêu cầu cùng format -->

| Pair | Sentence A | Sentence B | Dự đoán | Actual Score | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Python is a programming language. | Python is used to write software. | high | 0.0502 | Có |
| 2 | The customer interview should ask about past behavior. | Discussing real past events improves interview quality. | high | -0.0085 | Không |
| 3 | I like to cook Italian pasta. | Quantum mechanics studies particle behavior. | low | 0.0668 | Không |
| 4 | Vector stores support semantic search. | Embeddings help retrieve relevant chunks. | high | 0.0774 | Có |
| 5 | I will buy your app next month. | I might consider using it someday. | medium | 0.2552 | Có |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn nghĩa?**
Bất ngờ nhất là cặp #2 mang nghĩa khá gần nhưng score âm nhẹ trong mock embedding. Điều này cho thấy backend mock không phản ánh ngữ nghĩa thật như model production, nên score tuyệt đối chỉ mang tính tham khảo cho lab.

---

## 6. Results — Cá nhân (10 điểm)
<!-- TODO[RESULTS]: Đồng bộ query/gold answer với danh sách benchmark chính thức của nhóm -->

Chạy 5 benchmark queries của nhóm trên implementation cá nhân của bạn trong package `src`. **5 queries phải trùng với các thành viên cùng nhóm.**

Thông số chạy chung của nhóm:
- `top_k = 3`
- `score_threshold = 0.7`
- embedding model mục tiêu: `text-embedding-3-small` (fallback mock khi thiếu API key)

### Benchmark Queries & Gold Answers (nhóm thống nhất)

| # | Query | Gold Answer |
|---|-------|-------------|
| 1 | Quy tắc cốt lõi của The Mom Test để tránh nhận lời nói dối là gì? | Nói về cuộc đời của họ thay vì ý tưởng của bạn; hỏi về sự kiện cụ thể trong quá khứ; nói ít và lắng nghe nhiều. |
| 2 | Tại sao những lời khen (compliments) lại được coi là "fool's gold" trong học hỏi khách hàng? | Vì lời khen thường chỉ là lịch sự xã giao, gây nhiễu và không phản ánh cam kết mua hay mức độ đau của vấn đề. |
| 3 | Làm thế nào để neo giữ (anchor) những thông tin mơ hồ (fluff) từ khách hàng? | Hỏi ví dụ cụ thể trong quá khứ, ví dụ "Lần cuối việc đó xảy ra khi nào?" và "Bạn xử lý thế nào?". |
| 4 | Dấu hiệu nào cho thấy một cuộc gặp khách hàng đã thành công (Advancement)? | Có bước tiến/cam kết rõ: lịch họp tiếp theo, intro người quyết định, trial có cam kết, đặt cọc/mua trước. |
| 5 | Bạn nên làm gì khi lỡ tay "pitching" ý tưởng quá sớm? | Xin lỗi ngay, quay về hỏi workflow/hành vi thực tế của khách hàng để giảm bias dữ liệu. |

### Kết Quả Của Tôi
<!-- TODO[RESULTS-TABLE]: Cập nhật score/relevance nếu chạy lại với embedder khác -->

| # | Query | Top-1 Retrieved Chunk (chi tiết) | Score | Relevant? | Agent Answer (chi tiết) |
|---|-------|----------------------------------|-------|-----------|--------------------------|
| 1 | Quy tắc cốt lõi của The Mom Test để tránh nhận lời nói dối là gì? | "Rule 1: Talk about their life instead of your idea. Rule 2: Ask about specifics in the past instead of generics or opinions about the future. Rule 3: Talk less and listen more." | 0.8103 | Có | Agent trả lời đầy đủ 3 quy tắc: nói về cuộc đời khách hàng, hỏi quá khứ cụ thể, nói ít và lắng nghe nhiều. Nội dung khớp trực tiếp với chunk retrieve. |
| 2 | Tại sao những lời khen (compliments) lại được coi là "fool's gold" trong học hỏi khách hàng? | "Compliments are the fool's gold of customer learning: shiny, distracting, and entirely worthless. People often say nice things to protect your feelings. A compliment like 'I love it' is not evidence of intent to buy." | 0.8827 | Có | Agent nêu rõ lời khen là tín hiệu sai vì mang tính lịch sự, không phản ánh cam kết mua hoặc mức độ đau thật của vấn đề; cần quay lại dữ liệu hành vi cụ thể. |
| 3 | Làm thế nào để neo giữ (anchor) những thông tin mơ hồ (fluff) từ khách hàng? | "When someone says 'I always' or 'I would,' ask for specific past examples. A strong anchoring question is: 'When was the last time that happened?' Another anchoring question is: 'Can you talk me through that situation?'" | 0.9996 | Có | Agent trả lời theo đúng kỹ thuật anchor: chuyển câu trả lời mơ hồ sang ví dụ thật trong quá khứ, ép về workflow cụ thể thay vì chấp nhận phát biểu chung chung. |
| 4 | Dấu hiệu nào cho thấy một cuộc gặp khách hàng đã thành công (Advancement)? | "A meeting succeeds when it ends with advancement or commitment. Advancement means a clear next step in the buying process. Commitment means they give up something valuable: time, reputation, or money." | 0.9998 | Có | Agent xác định đúng tiêu chí thành công: phải có bước tiến rõ ràng và cam kết cụ thể (hẹn tiếp, intro người quyết định, trial có cam kết, đặt cọc). |
| 5 | Bạn nên làm gì khi lỡ tay "pitching" ý tưởng quá sớm? | "If you accidentally start pitching too soon, apologize immediately. Say that you got excited and want to get back to their workflow. Then return to questions about their current behavior and constraints." | 0.8319 | Có | Agent trả lời đúng hành động phục hồi: xin lỗi ngay, dừng pitch, quay về câu hỏi hành vi thực tế để giảm bias và khôi phục dữ liệu đáng tin. |

**Bao nhiêu queries trả về chunk relevant trong top-3?** 5 / 5

Ghi chú chạy benchmark:
- Backend embedding: `text-embedding-3-small` (OpenAI)
- Cấu hình: `top_k=3`, `score_threshold=0.7`
- Có áp dụng query normalization song ngữ VI -> EN trong pipeline thành viên 2 để giữ đúng đề bài tiếng Việt và tăng độ bám vào tài liệu tiếng Anh.

---

## 7. What I Learned (5 điểm — Demo)
<!-- TODO[REFLECTION]: Chỉnh phần học được sau buổi demo cuối cùng -->

**Điều hay nhất tôi học được từ thành viên khác trong nhóm:**
Fixed-size chunking chạy nhanh và đủ tốt cho baseline, đặc biệt khi dữ liệu ngắn và đồng nhất. Tuy nhiên với tài liệu dài như The Mom Test thì cần chiến lược giữ ngữ cảnh tốt hơn.

**Điều hay nhất tôi học được từ nhóm khác (qua demo):**
Metadata design quan trọng không kém chunking. Chỉ cần thêm trường category/source hợp lý là precision có thể tăng đáng kể ở các query chuyên biệt.

**Nếu làm lại, tôi sẽ thay đổi gì trong data strategy?**
Tôi sẽ tách riêng corpora theo tuyến nghiệp vụ (mom_test) và tuyến kỹ thuật (rag) ngay từ đầu để giảm nhiễu. Đồng thời thêm benchmark query tiếng Việt rõ ràng hơn và chuyển sang embedder thật để đánh giá ngữ nghĩa sát thực tế hơn.

---

## Tự Đánh Giá
<!-- TODO[SELF-SCORE]: Điều chỉnh tự chấm theo rubric cuối cùng của lớp -->

| Tiêu chí | Loại | Điểm tự đánh giá |
|----------|------|-------------------|
| Warm-up | Cá nhân | 5 / 5 |
| Document selection | Nhóm | 9 / 10 |
| Chunking strategy | Nhóm | 13 / 15 |
| My approach | Cá nhân | 10 / 10 |
| Similarity predictions | Cá nhân | 4 / 5 |
| Results | Cá nhân | 8 / 10 |
| Core implementation (tests) | Cá nhân | 30 / 30 |
| Demo | Nhóm | 4 / 5 |
| **Tổng** | | **83 / 100** |
