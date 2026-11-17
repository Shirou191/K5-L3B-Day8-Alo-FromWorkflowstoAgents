# Team

## Thông tin nhóm

- Tên nhóm: Alo
- Số thành viên: 1 (làm một mình do không tìm được đồng đội)
- Lớp: L3B
- Repo nhóm: `K5-L3B-DAY08-Alo-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: https://github.com/Shirou191/K5-Day8-Alo-FromWorkflowstoAgents, `main`, d7a5ede

## Thành viên

| STT | Họ tên | MSSV | Email | GitHub | Vai trò |
| --: | ------ | ---- | ----- | ------ | ------- |
|   1 | Phan Đào Minh Quân | 2A202603971 |  | Phan Đào Minh Quân (Shirou191) | Toàn bộ: workflow, single, orchestrator, ledger/crash, evaluation, báo cáo |

Gợi ý chia vai:

- Nhóm 6 người: integration; workflow; single agent; orchestrator; ledger/policy/crash; eval/report.
- Nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation.

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| --- | --- | --- | --- |
| Phan Đào Minh Quân (Shirou191) | Toàn bộ: 3 shape, test, benchmark, báo cáo | d7a5ede (feat: implement workflow, single, orchestrator shapes) | src/tests/test_team_shapes.py (27 test) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

Sao chép mục dưới đây cho từng thành viên.

## 2A202603971_PhanDaoMinhQuan

Báo cáo đầy đủ: [report/team/2A202603971_PhanDaoMinhQuan.md](report/team/2A202603971_PhanDaoMinhQuan.md)

### Phần việc phụ trách

- Toàn bộ bài (nhóm 1 người): ba shape, test, crash suite, benchmark, ADR, research card, báo cáo nhóm.

### Đóng góp cụ thể

- d7a5ede: `src/lab8/shapes/workflow.py`, `single.py`, `orchestrator.py`; `src/tests/test_team_shapes.py` (27 test); `src/reports/benchmark.json`, `crash.json`, `ablation_r2_seed55.json`.
- e40eb3b: ADR, research card, báo cáo nhóm, bảng đóng góp.

### Bằng chứng

- Ma trận student 248/248 passed; cổng host 81 passed; crash 20/20; `check_submission` 0 FAIL.
