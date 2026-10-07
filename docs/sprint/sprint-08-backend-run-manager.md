# Sprint 08 — Backend service & quản lý lần chạy

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | RUN-1, RUN-2, RUN-3, RUN-4; API cho FLEET-3, POL-3 |
| Phụ thuộc | Sprint 01, Sprint 07 |
| Backlog đầu vào | [sprint-07-backlog.md](../backlog/sprint-07-backlog.md) |
| Implementation plan | [sprint-08-plan.md](../implementation-plan/sprint-08-plan.md) (chưa có) |

## Mục tiêu

Có **backend service** phục vụ UI: CRUD cho mọi thực thể cấu hình, tạo và chạy kịch bản (**tối đa 1 run cùng lúc**),
theo dõi trạng thái/tiến độ, phát **live metric** và lưu metric vào DB.

## Phạm vi

- API cho vehicle type, fleet, trạm sạc, policy plugin, policy group, kịch bản, run, metric.
- Bộ chạy run ở tiến trình nền, giới hạn 1 run chạy cùng lúc.
- Kênh đẩy dữ liệu trực tiếp (tiến độ, metric theo thời gian, vị trí xe dạng snapshot) cho visualizer.
- Truy vấn metric và so sánh giữa các run.

## Ngoài phạm vi

- Giao diện (Sprint 09).
- Xác thực/phân quyền nhiều vai trò (ngoài phạm vi 0.2; chỉ cần chạy nội bộ).
- Hàng đợi nhiều run chạy song song.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S08-1 | API CRUD: vehicle type, fleet (kèm thành phần), trạm sạc, policy plugin (liệt kê built-in, tạo/sửa plugin tuỳ biến qua bước kiểm tra của Sprint 07), policy group, kịch bản. Kiểm tra hợp lệ dùng chung schema Sprint 01 |
| S08-2 | Không cho xoá thực thể đang được kịch bản/run tham chiếu (hoặc xoá mềm); run luôn giữ snapshot |
| S08-3 | API run: tạo run từ kịch bản; bắt đầu; huỷ; xem trạng thái (`queued`/`running`/`succeeded`/`failed`/`cancelled`), tiến độ (thời gian mô phỏng hiện tại / tổng, ước lượng thời gian còn lại), lỗi |
| S08-4 | Bộ chạy nền: chạy engine ở tiến trình riêng để API không bị chặn; **chỉ 1 run `running`**; yêu cầu chạy khi đang bận bị từ chối với thông báo rõ (hoặc xếp hàng nếu plan chọn vậy, nhưng chỉ 1 chạy) |
| S08-5 | Phục hồi: khởi động lại service khi đang có run thì run đó được đánh dấu `failed`/`interrupted`, không treo trạng thái `running` |
| S08-6 | Live stream: đẩy tiến độ, metric theo thời gian (S01-6) và snapshot vị trí/trạng thái xe theo chu kỳ cấu hình được qua WebSocket hoặc SSE; nội dung tương thích định dạng dữ liệu phát lại của Sprint 03 (S03-1) để visualizer dùng chung một bộ đọc |
| S08-7 | Lưu metric: khi run kết thúc ghi metric tổng hợp + chuỗi thời gian + event log (S01-7); metric theo zone, giờ, fleet, loại xe, sản phẩm |
| S08-8 | API metric: lấy metric một run, so sánh nhiều run (bảng chênh lệch theo metric, chiều "tốt hơn" theo `docs/engine/11-metrics.md`); cảnh báo khi hai run không cùng kịch bản/seed (so sánh không ghép cặp) |
| S08-9 | API lấy quỹ đạo xe của run đã xong theo khoảng thời gian theo đúng định dạng S03-1 của Sprint 03 (visualizer phát lại run đã xong thay cho file fixture) |
| S08-10 | Tài liệu: thêm `docs/engine/21-service-api.md` (danh sách endpoint, mô hình trạng thái run, định dạng stream) và cập nhật `15-cli.md` |

## Acceptance criteria

- [ ] AC08-1 Mọi thực thể tạo/đọc/sửa/xoá được qua API; dữ liệu sai bị từ chối với lỗi theo trường.
- [ ] AC08-2 Tạo kịch bản chọn fleet + policy group, chạy qua API, run chuyển `queued → running → succeeded`.
- [ ] AC08-3 Khi đã có 1 run `running`, yêu cầu chạy run thứ hai không làm có 2 run chạy cùng lúc (test đồng thời).
- [ ] AC08-4 Huỷ run đang chạy dừng engine trong ≤ vài giây và đặt trạng thái `cancelled`.
- [ ] AC08-5 Client nhận được tiến độ và metric live trong lúc run chạy; tần suất cấu hình được.
- [ ] AC08-6 Sau khi run xong, metric tổng hợp và chuỗi thời gian đọc lại được từ DB giống số liệu engine tính.
- [ ] AC08-7 Run chạy qua API cho metric giống hệt chạy cùng `RunSpec` qua CLI (NFR-1).
- [ ] AC08-8 Khởi động lại service giữa chừng không để lại run treo `running`.
- [ ] AC08-9 Có test tích hợp cho API (tạo dữ liệu → chạy run nhỏ → đọc metric).

## Rủi ro & câu hỏi mở

- Đẩy snapshot của 8k xe theo thời gian thực có thể nặng: có thể cần giảm tần suất, lọc theo khung nhìn, hoặc nén.
- Chọn framework backend (requirements Q5) trong plan.
