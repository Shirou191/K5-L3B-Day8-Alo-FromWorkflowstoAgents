# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash: d7a5ede
- Run id dẫn chứng: R-workflow-C-014-s11 (T14, ledger 120000 / proposal 150000), R-workflow-C-002-s55 (T02 denied), R-swarm-C-002-s55 (swarm fail đối chứng) — src/reports/benchmark.json
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000–1.000 / 0.000000 (14 claim × 5 seed, src/reports/benchmark.json)
- Cost per success (mô phỏng, VND): 35.23 (single 51.99, orchestrator 63.96, swarm 49.57)
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 trên bộ public (không trial nào fail forbidden_substring hay refund sai approval; T08/T09/T13 có audit policy_denied)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Trên cùng corpus public (14 claim C-001…C-014), cùng 5 seed `11,22,33,44,55`, cùng bảng giá mô phỏng và MockLLM, ba shape nhóm viết đều đạt pass rate 1.000, pass^5 1.000, variance 0. Khi chất lượng ngang nhau thì yếu tố quyết định là mức tự chủ, chi phí và số bước: workflow rẻ nhất (35.23 VND/success, 1 model call/trial, mean 4.43 / p95 5 steps), so với single 51.99 (5.64 model call, 10.93 steps) và orchestrator 63.96 (2.86 model call, 6.21 tool call). Swarm rẻ hơn single nhưng có variance > 0 (seed 55 = 0.929) vì tin số ngày trong ticket. Task claim là chuỗi tuần tự cố định (claim → order → quote → host), không có bước nào cần model chọn đường đi, nên kiến trúc ít tự chủ nhất mà vẫn làm được việc là workflow.

## Có đáng đổi lấy multi-agent không

Không, với dữ liệu hiện có. Trên public, multi-agent (orchestrator) không cho thêm điểm pass nào mà tốn gấp ~1.8 lần chi phí mỗi success; swarm còn thêm variance. Nếu một shape multi-agent pass nhỉnh hơn nhưng cost và variance cao hơn, nhóm vẫn giữ workflow trừ khi phần chênh pass nằm ở loại claim workflow không biểu diễn được bằng luật cố định. Quyết định sẽ đảo lại khi: (1) ticket chứa dữ kiện không có trong DB mà nghiệp vụ cho phép dùng (ví dụ phải đọc ảnh/biên bản để verify hư hỏng), cần model đọc hiểu; (2) có nhiều nguồn độc lập cần tra song song, nơi investigator song song giảm latency; (3) quy trình rẽ nhánh quá nhiều để mã hóa tay. Trong cả ba trường hợp, tiền vẫn phải do `compute_compensation` tính và chỉ code gọi `durability.issue_refund`.

## Trace và bằng chứng

Trace (`lab8.trace.Trace`, file `traces/<run_id>.json`) của workflow ghi: `step get_claim_view` (found, order_id), `step lookup_order` (visible, reason, và nếu visible thì 7 field allowlist của order: order_id, status, delay_days, shipping_fee_vnd, paid_vnd, damage_verified, carrier), `step compute_compensation` (amount, reason, clause_ids, parts), `step issue_refund` (ok, reason, conflict), `decision` (status, proposal_amount, reason), và `crash` khi có InjectedCrash. Cố ý **không** ghi: ticket (có thể chứa injection hay secret do khách dán vào), principal_id, parent_secret, raw_headers, claim row hay order row thô (SĐT, địa chỉ, tên hàng, internal note), nội dung trả lời của MockLLM. Trace được ghi ở mọi nhánh return, kể cả `needs_info`, `escalated`, `failed` và trước khi để crash lan ra. Test `test_trace_has_no_secret_ticket_or_pii` quét trace của mọi claim public ở seed 11 và 55. Nếu trace nằm ngoài chỗ scanner quét được thì không chứng minh được hệ thống sạch; vì vậy shape không ghi file nào khác ngoài `traces/<run_id>.json` và không in gì ra stdout.

## Giới hạn

MockLLM không phải model sản xuất: nó deterministic theo seed, và trong ba shape nhóm viết, output của model không quyết định nhánh nào, nên variance 0 là kết quả của thiết kế chứ không phải bằng chứng một LLM thật sẽ ổn định. Cost là mô phỏng theo `config/pricing.yaml`, không phải hóa đơn API. Latency để `unavailable`. Bộ public chỉ có 14 claim; pass rate hidden (40 claim × 5 seed) do giảng viên chấm. Không sửa JSON cho đủ 0.75.
