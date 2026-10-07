# Sprint 05 — Loại xe, fleet & sạc xe điện

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | EV-1, EV-2, EV-3, EV-4, EV-5, FLEET-1, FLEET-2, FLEET-4 |
| Phụ thuộc | Sprint 01, Sprint 02, Sprint 03 (visualizer) |
| Backlog đầu vào | [sprint-04-backlog.md](../backlog/sprint-04-backlog.md); từ [sprint-01-backlog.md](../backlog/sprint-01-backlog.md): B01-1, B01-2 |
| Implementation plan | [sprint-05-plan.md](../implementation-plan/sprint-05-plan.md) (chưa có) |

## Mục tiêu

Engine mô phỏng được **nhiều fleet xe điện** với nhiều loại xe, mỗi xe có **mức pin** giảm theo quãng đường, phải
**đi sạc** tại trạm sạc có số cổng giới hạn, và quyết định sạc là **hành vi của tài xế** (behavior model + CRN).
Request của khách gắn với **sản phẩm** và chỉ được phục vụ bởi loại xe phù hợp.

## Phạm vi

- Danh mục loại xe: 1 loại bike và 4–5 loại car (seed data, chỉnh được).
- Fleet: nhiều fleet trong một lần chạy, mỗi fleet = danh sách (loại xe × số lượng) + sản phẩm phục vụ.
- Trạng thái pin, ràng buộc quãng đường, hạ tầng trạm sạc, hàng đợi sạc.
- Behavior model quyết định sạc.
- Hook/API cho policy can thiệp việc sạc (đóng gói thành plugin chuẩn ở Sprint 07).
- Sản phẩm của request (bike, car 4 chỗ, car 7 chỗ…).

## Ngoài phạm vi

- UI quản lý fleet (Sprint 09); sprint này chỉ cần cấu hình qua `RunSpec`/DB.
- Giá theo sản phẩm (Sprint 06).
- Mô hình suy giảm pin theo tuổi, nhiệt độ, sạc theo đường cong phi tuyến chi tiết (có thể đưa vào backlog).

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S05-1 | `VehicleType` đầy đủ: tên, nhóm (bike/car), số chỗ, sản phẩm phục vụ, dung lượng pin, quãng đường tối đa khi đầy pin, mức tiêu thụ (suy ra hoặc khai báo), công suất sạc tối đa, thời gian sạc từ x% đến y%. Seed data cho 1 bike + 4–5 car |
| S05-2 | `Fleet`: tên, thành phần (loại xe × số lượng), zone xuất phát/phân bố ban đầu, ca làm việc. Một kịch bản có nhiều fleet; xe mang `fleet_id` và `vehicle_type` |
| S05-3 | Sản phẩm của request: kịch bản gán sản phẩm cho từng request (tỷ lệ theo zone/giờ cấu hình được); matching chỉ ghép request với xe phục vụ sản phẩm đó và đủ chỗ |
| S05-4 | Trạng thái pin (SOC) của từng xe: khởi tạo theo phân phối, giảm theo quãng đường thật đã đi (bao gồm chạy rỗng, đi sạc); ghi vào event log |
| S05-5 | Ràng buộc quãng đường: không gửi cuốc nếu quãng đường (đón + chở + tới trạm sạc gần nhất) vượt quá quãng đường còn lại trừ mức dự phòng |
| S05-6 | Hạ tầng sạc: `ChargingStation` (vị trí node, số cổng, công suất, loại xe dùng được); seed data cho Hà Nội; xe xếp hàng khi đầy cổng; thời gian sạc phụ thuộc công suất trạm và xe |
| S05-7 | Hiện thực các sự kiện `CHARGING`, `CHARGE_START`, `CHARGE_END` (đã dành sẵn) và trạng thái tài xế tương ứng; xe đang sạc không nhận cuốc |
| S05-8 | Behavior model quyết định sạc (slot mới trong `BehaviorSuite`): xác suất đi sạc theo SOC, giờ trong ngày, thu nhập đã đạt, khoảng cách và hàng đợi của trạm; chọn trạm; sạc đến mức nào. Quyết định đi qua CRN |
| S05-9 | Hook policy cho sạc: ví dụ `on_charge_decision` / API `send_to_charge(driver, station)` để policy điều xe đi sạc; policy mẫu "sạc ngoài giờ cao điểm" |
| S05-10 | Metric mới: số lần sạc, thời gian chờ sạc, thời gian sạc, tỷ lệ thời gian xe không phục vụ do sạc, số lần hết pin giữa chừng (phải bằng 0 nếu ràng buộc đúng), tỷ lệ sử dụng cổng sạc; metric theo fleet và theo loại xe |
| S05-11 | Lưu vehicle type, fleet, trạm sạc vào DB theo schema Sprint 01 (mở rộng schema) |
| S05-13 | Visualizer: thêm trạng thái xe đi sạc/đang sạc vào định dạng dữ liệu phát lại (S03-1) và màu vệt tương ứng; lớp trạm sạc (độ đầy cổng, hàng đợi); chi tiết xe hiển thị fleet, loại xe, SOC; metric sạc trong bảng metric |
| S05-12 | Tài liệu: cập nhật `04-agents.md`, `03-events.md`, `06-behavior.md`, `11-metrics.md`; thêm `20-fleet-ev-charging.md` |

## Acceptance criteria

- [ ] AC05-1 Seed data có 1 loại bike và 4–5 loại car với đầy đủ trường; load được từ DB.
- [ ] AC05-2 Một kịch bản chạy được với ≥ 2 fleet, mỗi fleet ≥ 2 loại xe; metric tách được theo fleet và loại xe.
- [ ] AC05-3 Request sản phẩm bike không bao giờ được ghép với car và ngược lại; có test.
- [ ] AC05-4 SOC của mọi xe không âm trong suốt lần chạy; số lần hết pin giữa chuyến = 0.
- [ ] AC05-5 Tổng năng lượng tiêu thụ của mỗi xe khớp quãng đường đi × mức tiêu thụ (sai số làm tròn).
- [ ] AC05-6 Trạm sạc không bao giờ phục vụ quá số cổng cùng lúc; có hàng đợi và metric thời gian chờ sạc.
- [ ] AC05-7 Thay đổi tham số behavior model sạc (ví dụ ngưỡng SOC) làm thay đổi metric sạc theo đúng chiều kỳ vọng;
      có test.
- [ ] AC05-8 Cùng seed, cùng cấu hình cho kết quả giống hệt; đổi policy không làm lệch các rút ngẫu nhiên ngoại sinh (CRN).
- [ ] AC05-9 Policy mẫu "sạc ngoài giờ cao điểm" chạy được và so sánh được với baseline bằng `Experiment`.
- [ ] AC05-10 Kịch bản 0.1 không khai báo fleet vẫn chạy (fleet mặc định một loại xe, không giới hạn pin).
- [ ] AC05-12 Fixture demo có sạc phát lại được trên visualizer: thấy xe đi sạc/đang sạc với màu riêng, trạm sạc hiển
      thị số cổng đang dùng khớp event log.
- [ ] AC05-11 Benchmark `hanoi_greensm_day` có bật sạc được đo và ghi vào backlog.

## Rủi ro & câu hỏi mở

- Thông số thật của xe và vị trí trạm sạc của GreenSM (requirements Q2, Q3).
- Tài xế GreenSM là nhân viên hay đối tác ảnh hưởng tới mức "tự quyết" khi sạc: cần cả model tự quyết và model tuân
  lệnh điều phối.
