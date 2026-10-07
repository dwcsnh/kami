# 03 · Sự kiện (`kami/core/events.py`)

`EventType` hiện thực danh mục sự kiện ở design doc §4.3. Mỗi sự kiện trên heap là
`Event(time, priority, seq, kind, payload)`. Chỉ ba trường đầu được dùng để so sánh thứ tự.

## Danh mục

| Nhóm | Sự kiện | Payload | Handler làm gì | Ưu tiên |
|---|---|---|---|---|
| Môi trường | `WEATHER_CHANGE` | `weather` | Đổi hệ số thời tiết, tính lại các chặng đang chạy, gài lại thời điểm hủy | 0 |
| | `INCIDENT_START` | `incident_id` | Bật sự cố trên các zone trong bán kính, tính lại chặng, gài lại hủy | 0 |
| | `INCIDENT_END` | `incident_id` | Tắt sự cố | 0 |
| | `TRAFFIC_UPDATE` | — | Ghi hệ số giờ vào log; nạp travel time động của `RoadNetwork` nếu tới mốc | 0 |
| Tài xế | `DRIVER_ONLINE` | `driver_id` | Bắt đầu ca, chuyển IDLE | 1 |
| | `DRIVER_OFFLINE` | `driver_id` | Hết ca: nghỉ ngay nếu đang rảnh, xong cuốc rồi nghỉ nếu đang bận | 1 |
| | `ARRIVE_STOP` | `driver_id`, `version` | Tới stop kế tiếp trong plan, xử lý đón hoặc trả khách | 2 |
| | `IDLE_ARRIVE` | `driver_id`, `version` | Kết thúc chặng chạy rỗng hoặc reposition | 2 |
| | `IDLE_MOVE` | `driver_id`, `version` | Hỏi `IdleMoveModel`: đứng yên hay di chuyển tới zone nào | 5 |
| | `CHARGE_START/END` | — | Dành sẵn cho xe điện (chưa hiện thực) | — |
| Khách | `RIDER_CANCEL` | `rider_id`, `token`, `recheck` | Khách hủy, hoặc tính tiếp hazard nếu `recheck` | 3 |
| | `REQUEST_CREATED` | `request_id` | Tạo khách, báo giá, mô hình đặt xe, mở Job | 4 |
| Nền tảng | `PRICE_UPDATE` | `every` | `policy.on_tick(sim, "PRICE_UPDATE")` | 6 |
| | `DISPATCH_TICK` | — | `policy.on_dispatch`, rồi `offer_trip` cho từng cặp | 7 |
| | `REPOSITION_TICK` | `every` | `policy.on_tick(sim, "REPOSITION_TICK")` | 8 |
| Policy | `POLICY_TIMER` | `rider_id?`, payload tuỳ ý | `policy.on_timer(sim, rider, **payload)` | 9 |

**Lý do của thứ tự ưu tiên:** mọi quyết định tại thời điểm t phải thấy thế giới tại t. Vì vậy môi trường đổi
trước. Sau đó các sự kiện giải phóng năng lực (trả khách, xe tới điểm) chạy trước dispatch cùng thời điểm, để xe
vừa rảnh kịp được ghép ngay. Timer của policy chạy sau cùng, khi trạng thái đã ổn định.

## Sự kiện chỉ ghi log

Một số hành động của engine được ghi vào `EventLog` nhưng không phải sự kiện trên heap:

| Nhãn log | Khi nào | Thông tin |
|---|---|---|
| `OFFER_SHOWN` | Báo giá cho khách | `fare`, `eta`, `surge`, `p` |
| `OFFER_ACCEPTED` / `OFFER_REJECTED` | Khách đặt / không đặt | `job` |
| `TRIP_OFFERED` / `TRIP_ACCEPTED` / `TRIP_REJECTED` | Gửi cuốc, tài xế nhận, tài xế từ chối | `job`, `eta`, `p`, `pooled` |
| `PICKUP` / `DROPOFF` | Đón / trả khách | `eta_error`, `wait` / `fare`, `surcharge`, `ivt`, `pooled` |
| `POOL_OFFER` *(pooling — ngoài phạm vi 0.2, giữ cho tương thích, xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại))* | `sim.behavior.pool_accept` | `surcharge`, `detour`, `p`, `accepted`, `partner` |
| `POOL_MERGE` *(pooling, như trên)* | `sim.merge_jobs` thành công | `partner`, `job`, `surcharge` |
| `IDLE_MOVE` | Xe rảnh bắt đầu chạy | `origin`, `dest`, `purpose` (`idle` hoặc `reposition`), `tt` |

## Thêm sự kiện mới

1. Thêm thành viên vào `EventType` và mức ưu tiên vào `EVENT_PRIORITY` (không khai báo thì mặc định là 5).
2. Viết handler `Simulation._on_<tên_viết_thường>(**payload)`.
3. Lên lịch bằng `self._push(t, EventType.X, **payload)` bên trong engine. Policy không được tự đẩy sự kiện; nếu
   cần, hãy dùng `POLICY_TIMER`.
