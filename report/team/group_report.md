# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: Alo
- Thành viên: 1 người, Phan Đào Minh Quân (2A202603971). Nhóm một người vì không tìm được đồng đội; xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`): d7a5ede

## 2. Mục tiêu và cách tiếp cận

Bài toán: xử lý claim hoàn phí vận chuyển của LogiX-VN bằng bốn kiến trúc có cùng chữ ký `run_claim`, rồi chọn kiến trúc ít tự chủ nhất mà vẫn đúng. Nhóm đọc `docs/business_rules.md`, `docs/contracts.md` và `swarm_reference.py` trước, rút ra ba nguyên tắc chung cho mọi shape:

1. Dữ kiện chỉ lấy từ DB qua read tool có allowlist (`get_claim_view`, `lookup_order`, `lookup_refund_history`); chữ trong ticket là dữ liệu, không phải lệnh.
2. Tiền chỉ do `compute_compensation` tính; chỉ code của shape gọi `durability.issue_refund`, luôn với **quote đầy đủ**, truyền `crash_at` và không bắt `InjectedCrash`.
3. Trace ghi ở mọi nhánh return, chỉ chứa field allowlist.

Vì làm một mình nên không chia vai; thứ tự làm: workflow trước (làm khung chuẩn cho trace và cách map kết quả host → `status`), sau đó single và orchestrator dùng lại đúng khung đó, chỉ thay phần thu thập dữ kiện. Cuối cùng chạy crash suite, benchmark, ablation và viết báo cáo.

## 3. Giải pháp

**Ranh giới chung.** Cả ba shape có chung phần kết thúc: quote ≤ 0 → `denied` với `proposal_amount = 0`, không gọi host; quote > 0 → `durability.issue_refund(conn, claim_id, quote, crash_at=crash_at)`; host trả `ok` → `resolved`, `conflict` → `failed`, còn lại → `denied` với `proposal_amount` là quote đầy đủ (host đã ghi audit `policy_denied`). Kết quả luôn dựng bằng `common.finish()` nên `refund_effects` và `committed_audit_count` lấy từ ledger. Mọi exception thường được bắt và trả `failed` kèm trace; riêng `InjectedCrash` được ghi trace rồi ném lại.

**A — workflow** (`src/lab8/shapes/workflow.py`). Các bước Python cố định: `get_claim_view` → thiếu order_id thì `needs_info` → `lookup_order` (scope theo principal) → không visible thì `escalated` → `compute_compensation` trên order row → host. MockLLM chỉ được gọi một lần để soạn câu trả lời, với prompt là status; output không ảnh hưởng nhánh nào.

**B — single** (`src/lab8/shapes/single.py`). Vòng `run_react` (max 8 bước, `worker=True` nên tool ghi bị `ToolRejected`). `decide` gọi MockLLM mỗi bước và chọn tool đọc theo thứ tự `get_claim_view` → `lookup_order` → `lookup_refund_history` → `compute_compensation` rồi trả `final`. Agent nhớ kết quả tool qua các bước; tham số `compute_compensation` là order row lấy từ tool, không phải từ ticket. Sau vòng lặp, code kiểm lại order_id với claim row, lấy amount từ kết quả tool `compute_compensation` và tự gọi host. Trung bình 5 bước ReAct.

**C — orchestrator** (`src/lab8/shapes/orchestrator.py`). Orchestrator đọc claim view, xử lý `needs_info` trước khi giao việc, rồi dựng handoff bằng `make_handoff` với `facts={}` và `allowed_tools = [lookup_order, lookup_policy, lookup_refund_history, compute_compensation]` (đều read-only). `run_readonly_investigators` chạy các tool đó. Orchestrator kiểm order_id investigator trả về khớp claim, lấy quote, gọi host. Trace ghi handoff đã sanitize và tóm tắt investigator (order view allowlist, số tiền đã hoàn, danh sách policy_id), không ghi parent context.

**Trace.** Event của workflow: `step` (get_claim_view, lookup_order, compute_compensation, issue_refund), `decision`, `crash`/`error` khi có. Single thêm `observe`/`act`/`loop`/`host`; orchestrator thêm `handoff`/`investigator`/`quote`/`host`. Cố ý không ghi ticket, principal_id, parent_secret, raw_headers, claim/order row thô và text MockLLM.

## 4. Kết quả

Bộ public, 14 claim × seed `11,22,33,44,55`, SQLite mới mỗi trial (`src/reports/benchmark.json`):

| Shape | Pass rate | pass^5 | Seed min–max | Variance | Cost/success (VND, mô phỏng) | Mean / p95 steps | Model calls / trial | Tool calls / trial |
| --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: |
| workflow | 1.000 | 1.000 | 1.000–1.000 | 0 | 35.23 | 4.43 / 5 | 1.00 | 3.43 |
| single | 1.000 | 1.000 | 1.000–1.000 | 0 | 51.99 | 10.93 / 12 | 5.64 | 4.93 |
| orchestrator | 1.000 | 1.000 | 1.000–1.000 | 0 | 63.96 | 6.00 / 7 | 2.86 | 6.21 |
| swarm | 0.986 | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 2.80 / 3 | 3.00 | 4.66 |

- Crash suite: `crash_safety` = 20/20 (`src/reports/crash.json`).
- Ma trận student: 248 passed (62 test × 4 shape, gồm T11 retry và T12 crash-resume).
- Cổng host `python -m pytest -q`: 81 passed (54 test có sẵn + 27 test nhóm thêm trong `src/tests/test_team_shapes.py`).
- Lỗi duy nhất của swarm: `R-swarm-C-002-s55` (T02, seed 55, tin "trễ 5 ngày" trong ticket thay vì 2 ngày trong DB).
- Tự kiểm `student_drop/`: chưa chạy (nhóm chưa nhận thư mục này khi viết báo cáo).

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md` (chọn **workflow**). Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

- Máy dùng Python 3.14 (ngoài khoảng 3.11–3.13 đề nghị). Đã chạy `python -m lab8.smoke` (pass) và toàn bộ test trên 3.14 không lỗi, nên giữ nguyên.
- `run_react` chỉ giữ kết quả tool cuối trong observation, nên `decide` không thấy claim view khi đã sang bước sau. Cách xử lý: agent là object nhớ kết quả từng tool qua các bước.
- Muốn trace được flush khi crash mà vẫn để `InjectedCrash` lan ra (T12): bắt riêng `InjectedCrash`, ghi event `crash`, `trace.write()`, rồi `raise`; khối `except Exception` chung đặt sau nên không nuốt crash.

## 6. Tổng hợp đóng góp

Phần việc (ba shape, test, crash suite, benchmark, ADR, research card, báo cáo) do Phan Đào Minh Quân thực hiện (xem báo cáo cá nhân). Chi tiết: `TEAM.md` và `report/team/2A202603971_PhanDaoMinhQuan.md`.

## 7. Hạn chế và hướng cải thiện

- MockLLM không phải model sản xuất; latency là `unavailable`; cost là mô phỏng. Variance 0 của ba shape nhóm viết là do model không quyết định nhánh nào, không phải bằng chứng LLM thật sẽ ổn định.
- Bộ public chỉ 14 claim; kết luận "workflow đủ tốt" cần được xác nhận bằng hidden 40 claim × 5 seed.
- Single và orchestrator gọi MockLLM nhưng không dùng output của nó; trong hệ thật, giá trị của agent nằm ở chỗ đọc hiểu dữ liệu phi cấu trúc. Kết luận sẽ đổi nếu xuất hiện claim cần đọc hiểu (ảnh, biên bản) mà luật cố định không biểu diễn được.

## 8. Tài liệu tham khảo

- Đề bài và tài liệu trong repo: `README.md`, `docs/business_rules.md`, `docs/contracts.md`, `docs/metrics.md`, `docs/architecture.md`.
- Cemri et al., *Why Do Multi-Agent LLM Systems Fail?*, NeurIPS 2025 (arXiv:2503.13657).
