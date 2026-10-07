# Sprint 03 — Hiệu năng quy mô GreenSM

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | PERF-1, PERF-2, PERF-3 |
| Phụ thuộc | Sprint 01, Sprint 02 |
| Backlog đầu vào | [sprint-02-backlog.md](../backlog/sprint-02-backlog.md) |
| Implementation plan | [sprint-03-plan.md](../implementation-plan/sprint-03-plan.md) (chưa có) |

## Mục tiêu

Mô phỏng **trọn một ngày** tại Hà Nội với **~100.000 request** và **~8.000 xe** trong giới hạn thời gian và bộ nhớ
đã chốt ở PERF-2, mà **không thay đổi kết quả** so với engine trước tối ưu (trên quy mô nhỏ, cùng seed).

## Phạm vi

- Chốt mục tiêu PERF-2 với người dùng (requirements Q1) ở bước lập plan.
- Kịch bản benchmark quy mô GreenSM.
- Profile và tối ưu các điểm nóng của engine ở quy mô lớn.
- Giảm bộ nhớ của event log và trạng thái agent.

## Ngoài phạm vi

- Chạy phân tán nhiều máy.
- Tính năng sạc và pricing mới (Sprint 04, 05). Chi phí tính toán của chúng sẽ được kiểm tra lại ở Sprint 11.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S03-1 | Kịch bản benchmark `hanoi_greensm_day`: 24h, ~100k request phân bố theo giờ/zone, ~8k xe với ca làm việc; thêm vào benchmark harness của Sprint 01 |
| S03-2 | Báo cáo profile ban đầu: thời gian theo nhóm (routing, sinh ứng viên matching, giải gán, behavior/hazard, event log, pooling), RAM theo thành phần |
| S03-3 | Tối ưu sinh ứng viên matching: chỉ mục không gian cho xe rảnh, giới hạn ứng viên theo zone/bán kính |
| S03-4 | Tối ưu routing: cache/bảng travel time theo zone hoặc theo cặp node hay dùng, tận dụng truy vấn nhiều điểm của router C++, tránh tính lại không cần thiết |
| S03-5 | Tối ưu giải gán ở batch lớn: chia bài toán theo vùng hoặc giới hạn kích thước; đảm bảo chất lượng gán không giảm quá ngưỡng cấu hình |
| S03-6 | Tối ưu lập lịch sự kiện hủy/hazard và các tick định kỳ ở quy mô 100k khách |
| S03-7 | Event log dạng ghi dần ra file (streaming) thay vì giữ toàn bộ trong RAM; metric vẫn tính được |
| S03-8 | Kiểm tra tương đương: trên kịch bản nhỏ, metric trước và sau tối ưu giống hệt (hoặc sai khác được giải thích và chấp nhận trong plan) |
| S03-9 | Tài liệu: cập nhật bảng hiệu năng ở `README.md`, `docs/engine/02-engine.md`, `10-matching-pooling-pricing.md`, `13-eventlog.md` |

## Acceptance criteria

- [ ] AC03-1 Mục tiêu PERF-2 (thời gian, RAM, cấu hình máy) được ghi rõ trong implementation plan và đã được người dùng duyệt.
- [ ] AC03-2 `hanoi_greensm_day` chạy xong trọn 24h mô phỏng với ~100k request, ~8k xe, đạt mục tiêu thời gian và RAM.
- [ ] AC03-3 Kết quả benchmark (wall-clock, sự kiện/giây, RAM đỉnh) được ghi vào backlog sprint 03 làm mốc mới.
- [ ] AC03-4 Kiểm tra tương đương ở S03-8 pass và có test tự động.
- [ ] AC03-5 Metric tổng hợp của `hanoi_greensm_day` hợp lý về mặt vận hành (tỷ lệ hoàn thành, thời gian chờ p90,
      tỷ lệ xe rỗng) và được ghi trong backlog để so sánh ở các sprint sau.
- [ ] AC03-6 Cùng seed chạy hai lần cho metric giống hệt (NFR-1).
- [ ] AC03-7 Toàn bộ test cũ pass.

## Rủi ro & câu hỏi mở

- Python thuần có thể không đủ: có thể cần Numba/Cython/thư viện C cho phần nóng. Lựa chọn nằm trong plan.
- Chia nhỏ bài toán gán có thể đổi kết quả so với Hungarian toàn cục; cần định nghĩa ngưỡng chất lượng chấp nhận được.
