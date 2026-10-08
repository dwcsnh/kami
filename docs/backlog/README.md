# Backlog

Sau mỗi sprint viết một file `sprint-NN-backlog.md` (kể cả khi trống) ghi lại những gì **chưa xong hoàn toàn**:
phần chưa thể làm (đợi module/sprint khác), phần đang dùng mock/dữ liệu giả, nợ kỹ thuật, acceptance criteria chỉ
đạt một phần, và số liệu mốc (benchmark) để sprint sau so sánh. Sprint kế tiếp **phải** tham chiếu file này ở mục
"Backlog đầu vào" và implementation plan của nó phải nói rõ xử lý mục nào.

| Sprint | Backlog | Số mục còn mở |
|---|---|---|
| 01 | [sprint-01-backlog.md](sprint-01-backlog.md) | 8 |
| 02 | [sprint-02-backlog.md](sprint-02-backlog.md) | 12 |

## Quy ước

- Mã mục: `BNN-k` (NN = sprint phát sinh). Mục được chuyển tiếp giữ nguyên mã gốc.
- Loại: `Chờ phụ thuộc` · `Mock` · `Nợ kỹ thuật` · `AC một phần` · `Ý tưởng`.
- Mức độ: `Chặn` (sprint đích không thể nghiệm thu nếu chưa xử lý) · `Cao` · `Thấp`.
- Khi xử lý xong một mục ở sprint sau, cập nhật cột trạng thái trong file backlog gốc (`Đã xử lý ở Sprint MM`)
  thay vì xoá dòng.

## Mẫu

```markdown
# Backlog sau Sprint NN — <Tên>

| | |
|---|---|
| Sprint | [sprint-NN-<slug>.md](../sprint/sprint-NN-<slug>.md) |
| Plan | [sprint-NN-plan.md](../implementation-plan/sprint-NN-plan.md) |
| Ngày kết thúc | YYYY-MM-DD |

## Trạng thái acceptance criteria
| AC | Kết quả (Đạt / Một phần / Không) | Bằng chứng / ghi chú |

## Mục còn mở
| Mã | Loại | Mức độ | Mô tả | Lý do chưa làm | Sprint dự kiến xử lý | Trạng thái |

## Mock đang dùng
| Thành phần | Mock gì | Thay bằng gì, khi nào |

## Số liệu mốc
<kết quả benchmark: wall-clock, sự kiện/giây, RAM đỉnh; metric vận hành chính>
```
