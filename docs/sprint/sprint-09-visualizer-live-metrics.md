# Sprint 09 — Simulation visualizer & live metric

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | UI-1, MAP-2 (hiển thị), PERF-4 |
| Phụ thuộc | Sprint 02 (quỹ đạo), Sprint 07 (stream, API quỹ đạo), Sprint 08 (khung UI) |
| Backlog đầu vào | [sprint-08-backlog.md](../backlog/sprint-08-backlog.md) |
| Implementation plan | [sprint-09-plan.md](../implementation-plan/sprint-09-plan.md) (chưa có) |

## Mục tiêu

Người dùng **nhìn thấy** mô phỏng trên bản đồ Hà Nội: xe di chuyển theo đường thật với màu theo trạng thái, khách
chờ, trạm sạc, cùng **bảng metric live**; xem được cả run đang chạy (live) và run đã xong (phát lại).

## Phạm vi

- Trang visualizer trong ứng dụng của Sprint 08.
- Chế độ live (đọc stream Sprint 07) và chế độ phát lại (đọc quỹ đạo đã lưu).
- Bảng live metric đặt cạnh bản đồ.

## Ngoài phạm vi

- Chỉnh sửa kịch bản trực tiếp trên bản đồ.
- Hiển thị 3D, mô phỏng vi mô làn đường.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S09-1 | Bản đồ nền Hà Nội có lớp mạng đường của kịch bản và ranh giới zone (bật/tắt được) |
| S09-2 | Lớp xe: vị trí nội suy theo lộ trình thật, màu theo trạng thái (rảnh, đi đón, chở khách, đi sạc, đang sạc, nghỉ), lọc theo fleet/loại xe/sản phẩm |
| S09-3 | Lớp khách đang chờ (màu theo thời gian chờ) và lớp trạm sạc (độ đầy cổng, hàng đợi) |
| S09-4 | Lớp nhiệt (heatmap) tuỳ chọn: cầu, cung rảnh, hệ số surge, mức tắc đường theo zone |
| S09-5 | Bảng live metric: số request, tỷ lệ hoàn thành/hủy, thời gian chờ p50/p90, tỷ lệ xe rảnh/đang sạc, doanh thu, hệ số giá trung bình; biểu đồ theo thời gian mô phỏng |
| S09-6 | Chế độ phát lại: thanh thời gian, play/pause, tua, tốc độ phát (1×…nhiều trăm×); đồng bộ bản đồ và metric theo thời điểm đang xem |
| S09-7 | Chi tiết khi nhấp: xe (fleet, loại, SOC, trạng thái, chuyến hiện tại), khách (thời gian chờ, giá offer), trạm sạc |
| S09-8 | Hiệu năng hiển thị: mượt với ~8k xe; engine khi bật stream vẫn đạt hệ số thời gian thực của PERF-4 |
| S09-9 | Tài liệu: bổ sung hướng dẫn visualizer vào tài liệu UI |

## Acceptance criteria

- [ ] AC09-1 Mở run đang chạy thấy xe di chuyển và metric cập nhật liên tục, khớp với số liệu API.
- [ ] AC09-2 Mở run đã xong phát lại được từ đầu đến cuối; tua đến thời điểm bất kỳ hiển thị đúng trạng thái.
- [ ] AC09-3 Xe di chuyển trên đường của mạng (không đi xuyên khối nhà); trạng thái màu khớp event log tại cùng thời điểm.
- [ ] AC09-4 Với `hanoi_greensm_day` (~8k xe), hiển thị đạt tối thiểu ~30 fps trên máy dev ở mức thu phóng toàn thành phố
      (con số chốt trong plan).
- [ ] AC09-5 Bật visualizer, engine vẫn đạt hệ số thời gian thực PERF-4 (chốt ở requirements Q1).
- [ ] AC09-6 Lọc theo fleet/loại xe hoạt động ở cả chế độ live và phát lại.

## Rủi ro & câu hỏi mở

- Dung lượng quỹ đạo của một ngày với 8k xe: cần giản lược (chỉ lưu node chuyển hướng, nén) — phối hợp với S07-9.
- Bản đồ nền (tile) cần nguồn được phép sử dụng; chốt trong plan.
