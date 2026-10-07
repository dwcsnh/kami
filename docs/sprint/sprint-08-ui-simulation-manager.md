# Sprint 08 — Giao diện Simulation manager

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | UI-2, UI-3, UI-4, UI-5, FLEET-3, POL-4, POL-5 |
| Phụ thuộc | Sprint 07 |
| Backlog đầu vào | [sprint-07-backlog.md](../backlog/sprint-07-backlog.md) |
| Implementation plan | [sprint-08-plan.md](../implementation-plan/sprint-08-plan.md) (chưa có) |

## Mục tiêu

Người dùng không cần viết code để **quản lý fleet, policy, kịch bản, chạy mô phỏng và xem metric**, toàn bộ qua
giao diện web dùng API của Sprint 07.

## Phạm vi

Bốn trang (và điều hướng chung):

1. **Kịch bản mô phỏng** (UI-2): danh sách, tạo/sửa, chạy, xem run đang chạy.
2. **Fleet** (UI-3): fleet, loại xe, trạm sạc.
3. **Policy** (UI-4): plugin, policy group, bật/tắt; chừa vị trí cho policy agent (Sprint 10).
4. **Metric** (UI-5): xem và so sánh các run.

## Ngoài phạm vi

- Bản đồ visualizer và live metric trên bản đồ (Sprint 09).
- Policy agent (Sprint 10).
- Đăng nhập/phân quyền.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S08-1 | Khung ứng dụng: điều hướng giữa 4 trang, chỉ báo toàn cục "đang có run chạy" (tên kịch bản, tiến độ) hiển thị ở mọi trang (RUN-2) |
| S08-2 | Trang kịch bản: danh sách (tên, cập nhật lần cuối, run gần nhất, trạng thái); form tạo/sửa gồm bản đồ/zone, khung giờ, demand (preset hoặc tham số), thời tiết/sự cố, **chọn fleet** (một hoặc nhiều), **chọn policy group**, seed; nút chạy (bị khoá khi đang có run khác chạy), nút huỷ; lịch sử run của kịch bản |
| S08-3 | Trang fleet: CRUD fleet (tên, thành phần loại xe × số lượng, sản phẩm, phân bố ban đầu, ca); CRUD loại xe (tên, nhóm, số chỗ, quãng đường tối đa, pin, sạc); CRUD trạm sạc (bảng; chọn vị trí trên bản đồ là tuỳ chọn) |
| S08-4 | Trang policy: danh sách plugin (built-in và tuỳ biến, nhóm, phiên bản); form tham số **sinh tự động từ `params_schema`**; xem mã nguồn plugin tuỳ biến (chỉ đọc hoặc soạn thảo cơ bản với bước kiểm tra của Sprint 06); CRUD policy group (thêm/xoá/sắp xếp thành viên, bật/tắt từng thành viên, hiển thị lỗi xung đột); đánh dấu group "baseline hệ thống" (POL-5) |
| S08-5 | Trang metric: chọn một run xem metric tổng hợp + biểu đồ theo thời gian + phân rã theo zone/fleet/loại xe/sản phẩm; chọn nhiều run để so sánh (bảng chênh lệch, màu theo chiều "tốt hơn", cảnh báo không ghép cặp); xuất CSV |
| S08-6 | Xử lý lỗi và trạng thái trống ở mọi trang; xác nhận trước khi xoá; không mất dữ liệu form khi lỗi kiểm tra |
| S08-7 | Tài liệu: hướng dẫn sử dụng UI (`docs/engine/21-ui-guide.md` hoặc `docs/user-guide.md`), có ảnh chụp màn hình |

## Acceptance criteria

- [ ] AC08-1 Từ UI, người dùng tạo loại xe, fleet, policy group, kịch bản, rồi chạy kịch bản và xem metric mà không
      dùng CLI — kịch bản kiểm thử end-to-end được ghi lại trong plan.
- [ ] AC08-2 Mọi thay đổi trên UI được lưu vào DB và còn nguyên sau khi tải lại trang và khởi động lại service.
- [ ] AC08-3 Form tham số policy được sinh từ `params_schema`; nhập sai kiểu/ngoài khoảng bị báo lỗi tại trường.
- [ ] AC08-4 Bật/tắt thành viên của policy group trên UI thay đổi đúng cấu hình run được chụp snapshot.
- [ ] AC08-5 Khi một run đang chạy, mọi trang hiển thị chỉ báo; nút chạy kịch bản khác bị khoá hoặc báo bận.
- [ ] AC08-6 Trang metric so sánh được ≥ 2 run, hiển thị chênh lệch và cảnh báo khi không cùng kịch bản/seed.
- [ ] AC08-7 Giao diện dùng được trên màn hình laptop phổ biến (≥ 1280px) không vỡ bố cục.

## Rủi ro & câu hỏi mở

- Chọn công nghệ frontend (requirements Q5) trong plan.
- Soạn thảo mã plugin trong trình duyệt có thể để sau (backlog) nếu Sprint 10 cung cấp luồng tạo qua agent.
