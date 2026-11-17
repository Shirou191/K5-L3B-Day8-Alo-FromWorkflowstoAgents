# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R2 · Failure taxonomy |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (MAST), NeurIPS 2025 Datasets & Benchmarks, arXiv:2503.13657; bằng chứng: phân tích trace có chú thích của người trên nhiều framework MAS |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Lỗi của hệ multi-agent gom được thành 3 nhóm: lỗi đặc tả/thiết kế hệ thống, lệch giữa các agent (inter-agent misalignment), và lỗi kiểm chứng/kết thúc task (task verification); phần lớn lỗi đến từ thiết kế hệ thống chứ không chỉ do năng lực model |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Paper đo trên LLM thật (GPT-4 class…) và các framework như ChatDev, MetaGPT, AG2 với task lập trình/toán; lab dùng MockLLM deterministic và 14 claim public, nên chỉ kiểm được việc *phân loại* một lỗi cố ý, không kiểm được tần suất các nhóm lỗi |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Trial fail của swarm ở seed 55 là lỗi *task verification* (không đối chiếu số ngày trong ticket với cột `delay_days`). Đổi swarm → workflow (có bước kiểm chứng cứng bằng DB) ở seed 55 sẽ nâng pass rate từ ~0.93 lên 1.00 (+1 claim / 14) và giảm cost/success |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Cố định: MockLLM, tool manifest 1.1, seed 55, corpus `data/public_claims.jsonl`, `config/pricing.yaml`, evaluator `lab8.metrics.trial_pass`, SQLite mới cho mỗi trial. Biến duy nhất thay đổi: shape (swarm ↔ workflow), tức có hay không bước để ticket ghi đè dữ kiện DB |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: T02 (C-002) swarm trả `resolved` 20000 thay vì `denied`. Đo bằng pass rate ở seed 55, lý do fail trong `trials[].reason`, và cost/success; kèm seed variance từ benchmark 5 seed |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn): `python -m lab8.benchmark --shapes workflow,swarm --cases data/public_claims.jsonl --seeds 55 --out reports/ablation_r2_seed55.json`
- Run id / file report: `src/reports/ablation_r2_seed55.json`; trial fail `R-swarm-C-002-s55` (reason `status resolved != denied`), đối chứng `R-workflow-C-002-s55` pass
- Kết quả so với hypothesis (đúng / sai / không kết luận được), kèm số liệu: **Đúng.** Seed 55: workflow pass 1.000, cost/success 35.23 VND; swarm pass 0.929 (13/14), cost/success 53.23 VND. Lỗi duy nhất là C-002, thuộc nhóm task verification theo MAST: swarm có dữ kiện đúng trong DB nhưng không kiểm chứng số liệu khách tự khai. Benchmark 5 seed (`src/reports/benchmark.json`) xác nhận lỗi chỉ xuất hiện ở seed 55: swarm seed min/max 0.929/1.000, variance 0.000816; workflow variance 0
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Lỗi của swarm là điểm yếu cài sẵn (`REFERENCE_WEAKNESS`), nên ablation chỉ minh họa cách phân loại, không ước lượng được tỉ lệ lỗi verification của LLM thật; n = 1 trial fail.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
