# Báo cáo cá nhân — 2A202603971_PhanDaoMinhQuan

## 1. Thông tin thành viên

- Họ tên: Phan Đào Minh Quân
- MSSV: 2A202603971
- Email:
- GitHub: Shirou191

## 2. Phần việc phụ trách

Nhóm Alo chỉ có một thành viên (không tìm được đồng đội), nên tôi phụ trách toàn bộ bài:

- Shape A `workflow`, shape B `single`, shape C `orchestrator` (`src/lab8/shapes/`).
- Test của nhóm (`src/tests/test_team_shapes.py`).
- Crash suite, benchmark 4 shape × 5 seed, ablation R2.
- ADR, research card, báo cáo nhóm, `TEAM.md`.

## 3. Đóng góp cụ thể

- Commit `d7a5ede`: cài ba shape, thêm 27 test, sinh `src/reports/benchmark.json`, `crash.json`, `ablation_r2_seed55.json`.
- Commit `e40eb3b`: điền ADR, research card, báo cáo nhóm, bảng đóng góp.
- Test đã thêm (`src/tests/test_team_shapes.py`): `test_ticket_injection_does_not_change_amount`, `test_trace_has_no_secret_ticket_or_pii`, `test_order_id_in_ticket_is_not_used`, `test_unknown_claim_fails_without_exception`, `test_crash_then_resume_keeps_one_refund`, `test_orchestrator_trace_holds_sanitized_handoff_only`, `test_react_worker_cannot_call_write_tool`, `test_single_stays_under_step_cap`.
- Quyết định kỹ thuật:
  - Cả ba shape lấy dữ kiện từ DB qua read tool; tiền chỉ do `compute_compensation` tính; chỉ code của shape gọi `durability.issue_refund` với quote đầy đủ và `crash_at`.
  - Bắt riêng `InjectedCrash` để ghi trace rồi ném lại; mọi exception khác trả `failed` kèm trace.
  - Trace không ghi ticket, principal_id, parent_secret, raw_headers, claim/order row thô.
  - Chọn `workflow` trong ADR vì cùng pass rate 1.000 nhưng cost/success thấp nhất (35.23 VND mô phỏng).

## 4. Bằng chứng

- `python -m pytest -q -m student -o addopts=`: 248 passed.
- `python -m pytest -q`: 81 passed.
- `src/reports/crash.json`: `crash_safety` = 20/20.
- `src/reports/benchmark.json`: workflow / single / orchestrator pass 1.000, pass^5 1.000, variance 0; swarm 0.986 / 0.929 (fail `R-swarm-C-002-s55`).
- Run id dẫn chứng: `R-workflow-C-014-s11`, `R-workflow-C-002-s55`.
- `python -m lab8.check_submission`: 0 FAIL.

## 5. Công cụ AI đã dùng

- **Claude Code (Anthropic)**: dùng để đọc đề và host code, viết ba shape

## 6. Tự đánh giá

**Kết quả đo được (từ `src/reports/` và test):**

- Ba shape qua 62/62 test student mỗi shape; crash 20/20; `check_submission` 0 FAIL.
- Shape chọn `workflow`: pass 1.000 trên bộ public (14 claim × 5 seed). Hidden chưa tự kiểm (chưa có `student_drop/`).
- Làm một mình, có dùng Claude Code (mục 5).

**Tự nhận xét (tự viết, mỗi ý 1–2 câu):**

- Phần tôi hiểu rõ và tự giải thích được: đã hiểu rõ workflow và lí do chọn shape này
- Phần tôi còn chưa chắc / cần đọc lại: ko có
- Nếu làm lại, tôi sẽ thay đổi:
- Điểm tự chấm theo RUBRIC (C1–C8) và lý do: 100 vì đã hiểu bài 
