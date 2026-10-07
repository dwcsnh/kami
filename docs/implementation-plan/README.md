# Implementation plan

Mỗi sprint trong [`../sprint/`](../sprint/README.md) có **một** file plan ở đây, đặt tên `sprint-NN-plan.md`.
Plan mô tả **cách làm** cho các hạng mục và acceptance criteria của sprint. Quy trình ở [AGENTS.md](../../AGENTS.md):
plan phải được người dùng **duyệt** trước khi bắt đầu viết code.

| Sprint | Plan | Trạng thái |
|---|---|---|
| 01 | [sprint-01-plan.md](sprint-01-plan.md) | Đã thực hiện |

Trạng thái plan: `Nháp` → `Chờ duyệt` → `Đã duyệt` (ghi ngày và người duyệt) → `Đã thực hiện`. Plan đã duyệt mà cần
đổi hướng đáng kể thì sửa plan, ghi vào mục "Lịch sử thay đổi" và xin duyệt lại phần thay đổi.

## Mẫu

```markdown
# Implementation plan — Sprint NN: <Tên>

| | |
|---|---|
| Sprint | [sprint-NN-<slug>.md](../sprint/sprint-NN-<slug>.md) |
| Backlog đầu vào | [sprint-(NN-1)-backlog.md](../backlog/sprint-(NN-1)-backlog.md) — các mục được xử lý trong plan này: <mã> |
| Trạng thái | Nháp / Chờ duyệt / Đã duyệt (YYYY-MM-DD) / Đã thực hiện |

## 1. Tóm tắt hướng tiếp cận
## 2. Quyết định kỹ thuật          (lựa chọn, phương án đã cân nhắc, lý do; câu hỏi mở cần người dùng chốt)
## 3. Thay đổi theo module          (file/module mới hoặc sửa, interface công khai thay đổi)
## 4. Kế hoạch theo hạng mục        (mỗi SNN-k: các bước, thứ tự, phụ thuộc)
## 5. Kiểm chứng acceptance criteria (mỗi ACNN-k: test/lệnh/bằng chứng sẽ dùng)
## 6. Mock & phần dự kiến chưa làm  (sẽ ghi vào backlog nếu xác nhận)
## 7. Rủi ro & phương án dự phòng
## 8. Lịch sử thay đổi
```
