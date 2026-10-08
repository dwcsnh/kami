# Sprint 09 — Giao diện Simulation manager & visualizer live

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | UI-1 (chế độ live, tích hợp), UI-2, UI-3, UI-5, FLEET-3, PERF-4 |
| Phụ thuộc | Sprint 03 (visualizer), Sprint 08 |
| Backlog đầu vào | [sprint-08-backlog.md](../backlog/sprint-08-backlog.md) |
| Implementation plan | [sprint-09-plan.md](../implementation-plan/sprint-09-plan.md) (chưa có) |

## Mục tiêu

Người dùng không cần viết code để **quản lý fleet, kịch bản, chạy mô phỏng và xem metric**, toàn bộ qua
giao diện web dùng API của Sprint 08, và **xem trực tiếp** run đang chạy trên bản đồ (visualizer của Sprint 03 chuyển
sang đọc stream/API thay cho file fixture).

## Phạm vi

Bốn trang (và điều hướng chung):

1. **Kịch bản mô phỏng** (UI-2): danh sách, tạo/sửa, chạy, xem run đang chạy.
2. **Fleet** (UI-3): fleet, loại xe, trạm sạc.
3. **Metric** (UI-5): xem và so sánh các run.
4. **Visualizer** (UI-1): visualizer của Sprint 03 ghép vào ứng dụng, có chế độ live và phát lại run đã lưu.

## Ngoài phạm vi

- Đăng nhập/phân quyền.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S09-1 | Khung ứng dụng: điều hướng giữa 4 trang, chỉ báo toàn cục "đang có run chạy" (tên kịch bản, tiến độ) hiển thị ở mọi trang (RUN-2) |
| S09-2 | Trang kịch bản: danh sách (tên, cập nhật lần cuối, run gần nhất, trạng thái); form tạo/sửa gồm bản đồ/zone, khung giờ, demand (preset hoặc tham số), thời tiết/sự cố, **chọn fleet** (một hoặc nhiều), cấu hình matching và pricing (bảng giá, chiến lược), seed; nút chạy (bị khoá khi đang có run khác chạy), nút huỷ; lịch sử run của kịch bản |
| S09-3 | Trang fleet: CRUD fleet (tên, thành phần loại xe × số lượng, sản phẩm, phân bố ban đầu, ca); CRUD loại xe (tên, nhóm, số chỗ, quãng đường tối đa, pin, sạc); CRUD trạm sạc (bảng; chọn vị trí trên bản đồ là tuỳ chọn) |
| S09-5 | Trang metric: chọn một run xem metric tổng hợp + biểu đồ theo thời gian + phân rã theo zone/fleet/loại xe/sản phẩm; chọn nhiều run để so sánh (bảng chênh lệch, màu theo chiều "tốt hơn", cảnh báo không ghép cặp); xuất CSV |
| S09-6 | Xử lý lỗi và trạng thái trống ở mọi trang; xác nhận trước khi xoá; không mất dữ liệu form khi lỗi kiểm tra |
| S09-7 | Tài liệu: hướng dẫn sử dụng UI (`docs/engine/22-ui-guide.md` hoặc `docs/user-guide.md`), có ảnh chụp màn hình, gồm cả visualizer |
| S09-8 | Ghép visualizer của Sprint 03 thành một trang của ứng dụng (dùng chung khung, điều hướng, chỉ báo run); mở từ danh sách run hoặc từ chỉ báo "đang có run chạy" |
| S09-9 | Chế độ live: đọc stream của Sprint 08 (S08-6) — xe, vệt đường chạy và bảng metric cập nhật liên tục trong lúc run chạy; khi run kết thúc chuyển được sang phát lại |
| S09-10 | Chế độ phát lại run đã lưu qua API quỹ đạo (S08-9) thay cho file fixture |
| S09-11 | Lọc theo fleet/loại xe/sản phẩm trên bản đồ ở cả live và phát lại; lớp khách đang chờ (màu theo thời gian chờ) |
| S09-12 | Đo PERF-4: engine khi bật stream vẫn nhanh hơn thời gian thực theo hệ số đã chốt (requirements Q1) |

## Acceptance criteria

- [ ] AC09-1 Từ UI, người dùng tạo loại xe, fleet, trạm sạc, kịch bản, rồi chạy kịch bản và xem metric mà không
      dùng CLI — kịch bản kiểm thử end-to-end được ghi lại trong plan.
- [ ] AC09-2 Mọi thay đổi trên UI được lưu vào DB và còn nguyên sau khi tải lại trang và khởi động lại service.
- [ ] AC09-5 Khi một run đang chạy, mọi trang hiển thị chỉ báo; nút chạy kịch bản khác bị khoá hoặc báo bận.
- [ ] AC09-6 Trang metric so sánh được ≥ 2 run, hiển thị chênh lệch và cảnh báo khi không cùng kịch bản/seed.
- [ ] AC09-8 Mở run đang chạy thấy xe di chuyển, vệt đường chạy và metric cập nhật liên tục, khớp số liệu API.
- [ ] AC09-9 Mở run đã xong phát lại được từ đầu đến cuối qua API (không cần file fixture); tua đến thời điểm bất kỳ
      hiển thị đúng trạng thái.
- [ ] AC09-10 Lọc theo fleet/loại xe hoạt động ở cả chế độ live và phát lại.
- [ ] AC09-11 Bật visualizer live, engine vẫn đạt hệ số thời gian thực PERF-4 (chốt ở requirements Q1).
- [ ] AC09-7 Giao diện dùng được trên màn hình laptop phổ biến (≥ 1280px) không vỡ bố cục.

## Rủi ro & câu hỏi mở

- Dùng lại công nghệ frontend, bản đồ (Mapbox) và design tokens (light mode, màu chủ đạo xanh Tiffany) đã chốt ở Sprint 03.
- Đẩy snapshot của nhiều nghìn xe qua stream có thể nặng: phối hợp với S08-6 (giảm tần suất, lọc theo khung nhìn, nén).
