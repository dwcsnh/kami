# Sprint 11 — Tích hợp & nghiệm thu end-to-end

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | Toàn bộ [requirements.md](../requirements.md) |
| Phụ thuộc | Sprint 01–09 (Sprint 07, 10 đã xoá) |
| Backlog đầu vào | [sprint-09-backlog.md](../backlog/sprint-09-backlog.md) và **mọi mục còn mở** trong các backlog trước |
| Implementation plan | [sprint-11-plan.md](../implementation-plan/sprint-11-plan.md) (chưa có) |

## Mục tiêu

Xác nhận kami 0.2 đáp ứng toàn bộ yêu cầu khi **mọi tính năng cùng bật** ở quy mô GreenSM Hà Nội, xử lý các mục
backlog còn mở (hoặc chuyển chúng có chủ đích sang giai đoạn sau), và hoàn thiện tài liệu.

## Phạm vi

- Kịch bản nghiệm thu end-to-end đầy đủ.
- Đo lại hiệu năng với sạc, pricing, stream cùng bật.
- Gom và xử lý backlog còn mở.
- Rà soát tài liệu.

## Ngoài phạm vi

- Tính năng mới không có trong requirements.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S11-1 | Tổng hợp mọi mục còn mở trong `docs/backlog/*`: phân loại làm ngay trong sprint này / chuyển giai đoạn sau (ghi lý do) |
| S11-2 | Kịch bản nghiệm thu: qua UI, tạo 2 fleet (bike + car nhiều loại), trạm sạc, bảng giá theo sản phẩm và một chiến lược dynamic pricing; chạy ngày thường Hà Nội quy mô GreenSM; xem visualizer live; so sánh với run baseline trên trang metric |
| S11-3 | Đo lại PERF-1/PERF-2/PERF-4 với mọi tính năng bật; tối ưu nếu không đạt |
| S11-4 | Kiểm tra tái lập (NFR-1) và truy vết (NFR-4) trên run nghiệm thu: chạy lại từ snapshot cho kết quả giống hệt |
| S11-5 | Kiểm tra tương thích (NFR-2, NFR-5): ví dụ và CLI của 0.1 vẫn chạy; engine dùng được không cần DB/UI |
| S11-6 | Rà soát tài liệu: `README.md`, `docs/engine/*`, `docs/requirements.md` (đánh dấu trạng thái từng yêu cầu), hướng dẫn UI, `17-limitations-roadmap.md` |
| S11-7 | Báo cáo nghiệm thu: bảng yêu cầu → bằng chứng (test, ảnh chụp, số liệu benchmark) |

## Acceptance criteria

- [ ] AC11-1 Kịch bản nghiệm thu S11-2 chạy trọn vẹn qua UI không lỗi.
- [ ] AC11-2 Mọi yêu cầu trong requirements.md có trạng thái Đạt / Đạt một phần (có lý do) / Chuyển giai đoạn sau,
      kèm bằng chứng trong báo cáo nghiệm thu.
- [ ] AC11-3 PERF-1, PERF-2, PERF-4 đạt với mọi tính năng bật (hoặc sai lệch được người dùng chấp nhận bằng văn bản).
- [ ] AC11-4 Không còn mục backlog "chặn" (blocking) nào chưa xử lý.
- [ ] AC11-5 Chạy lại run nghiệm thu từ snapshot cho metric giống hệt.
- [ ] AC11-6 Toàn bộ test pass; ví dụ 0.1 chạy được.

## Rủi ro & câu hỏi mở

- Tích luỹ nợ từ các sprint trước có thể vượt sức chứa của một sprint: S11-1 cần ưu tiên rõ ràng với người dùng.
