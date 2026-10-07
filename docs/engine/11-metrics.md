# 11 · Metrics (`kami/metrics.py`)

`sim.metrics()` (tương đương `kami.metrics.compute(sim)`) trả về dict phẳng `{tên: số}`.

- **Đơn vị:** thời gian theo phút, tiền theo VND, quãng đường theo km, tỷ lệ trong [0, 1].
- **Cửa sổ đo:** chỉ tính khách *gửi request* trong `[tags.measure_from, t_end)`. Metric tài xế và vận hành tính
  trên toàn bộ thời gian online.
- Metric không xác định (ví dụ độ vòng khi không có chuyến ghép) có giá trị `nan` và bị bỏ qua khi so sánh cặp.
- `DIRECTION[tên]` cho biết chiều "tốt hơn": +1 là cao hơn tốt hơn, −1 là thấp hơn tốt hơn, 0 là chẩn đoán.
  Report dùng nó để ghi verdict.

## Khách (`rider.*`)

| Metric | Định nghĩa | Chiều |
|---|---|---|
| `requests`, `booked` | Số request trong cửa sổ; số đã đặt | |
| `conversion` | đặt / request | + |
| `completion_rate` | DONE / đặt | + |
| `cancel_rate` | CANCELLED / đặt (`cancel_rate_waiting`, `cancel_rate_matched` tách theo pha) | − |
| `no_driver_rate` | Hủy khi chưa từng có xe / đặt ("không tìm được xe") | − |
| `unfinished_rate` | Chưa kết thúc khi dừng mô phỏng / đặt (≈0 nhờ `drain_s`) | |
| `wait_mean`, `wait_p50`, `wait_p90`, `wait_p95` | Từ lúc đặt tới lúc đón | − |
| `eta_error_abs`, `eta_error_signed` | Giờ đón thực − giờ đón đã hứa (dương = trễ) | − |
| `travel_time_p90` | p90 từ lúc đặt tới lúc tới nơi (khách DONE) | − |
| `fare_mean` | Giá thực trả trung bình (fare + surcharge) | 0 |
| `pool_rate` | Tỷ lệ khách DONE đi ghép | 0 |
| `pool_offer_accept_rate`, `pool_offers` | Tỷ lệ nhận đề nghị ghép; số đề nghị | |
| `detour_ratio` | Trung bình thời gian trên xe / thời gian đi thẳng, cho khách ghép | − |
| `pooled_travel_time_p90` | p90 từ lúc đặt tới lúc tới nơi của khách ghép | |
| `pooled_cancel_rate` | Tỷ lệ hủy trong số khách đã được ghép | |

## Tài xế (`driver.*`)

| Metric | Định nghĩa | Chiều |
|---|---|---|
| `online_hours` | Tổng giờ online | |
| `utilization` | Thời gian chở khách / thời gian online | + |
| `busy_share` | (đi đón + chở khách) / online | |
| `earnings_per_hour` | Tổng thu nhập / giờ online | + |
| `idle_gap_mean` | Thời gian rảnh trung bình giữa hai cuốc | − |
| `empty_km_share` | km chạy rỗng / tổng km | − |
| `rejection_rate` | Số lần từ chối / số cuốc được gửi | 0 |
| `earnings_gini` | Gini của thu nhập theo giờ giữa các tài xế | − |

## Nền tảng & vận hành

| Metric | Định nghĩa | Chiều |
|---|---|---|
| `platform.trips` | Số chuyến hoàn thành (khách trong cửa sổ đo) | + |
| `platform.gmv` | Σ(fare + surcharge) | + |
| `platform.revenue` | Σ(fare + surcharge − payout tài xế) | + |
| `platform.contribution_margin` | Hiện bằng `revenue` vì chưa mô hình hoá chi phí khuyến khích (docs/engine/17) | + |
| `platform.surcharge_total` | Tổng phụ phí ghép (âm nếu là giảm giá) | |
| `platform.pooled_jobs` | Số job ghép, tương đương số "xe được giải phóng" | |
| `ops.vehicle_km`, `ops.empty_km` | Tổng km xe chạy; km chạy rỗng | − |
| `ops.trips_per_vehicle_hour` | Chuyến / giờ online | + |
| `ops.pax_km_per_vehicle_km` | km khách (đi thẳng) / km xe | + |

## Công bằng (`fair.*`)

| Metric | Định nghĩa |
|---|---|
| `fair.zone_wait_p90_max` | p90 thời gian chờ ở zone tệ nhất (chỉ zone có ≥ 10 khách đặt) |
| `fair.zone_wait_p90_spread` | Chênh lệch p90 giữa zone tệ nhất và tốt nhất |
| `fair.zone_completion_min` | Tỷ lệ hoàn thành thấp nhất giữa các zone |

## Phân rã

- `kami.metrics.by_zone(sim)` → `{zone: {requests, booked, completion_rate, cancel_rate, wait_p90, wait_mean}}`.
  `Experiment` lưu kết quả này cho mỗi lần chạy để kiểm tra guardrail "không khu nào xấu đi quá X%".
- `kami.metrics.by_hour(sim)` → `{giờ: {requests, trips, cancel_rate, wait_mean}}`, dùng hiệu chỉnh baseline theo
  lịch sử.

## Bộ metric theo policy (design doc §10.3)

| Policy | Metric chính | Guardrail | Chẩn đoán |
|---|---|---|---|
| Cửa sổ batch | `rider.wait_mean` | `rider.wait_p95`, `rider.cancel_rate` | `rider.eta_error_abs`, `driver.empty_km_share` |
| Surge | `platform.contribution_margin`, `platform.trips` | `rider.no_driver_rate`, `rider.fare_mean`, `fair.*` | `rider.conversion` |
| Repositioning | `fair.zone_completion_min` | `ops.empty_km`, `driver.earnings_per_hour` | `by_zone` |
| Ghép sau 5' +20k | `rider.cancel_rate`, `rider.completion_rate` | `rider.detour_ratio`, `rider.pooled_travel_time_p90`, `rider.pooled_cancel_rate`, `rider.fare_mean` | `rider.pool_offer_accept_rate`, `platform.pooled_jobs` |

## Thêm metric

Thêm khoá mới vào dict trong `compute()` (nếu có chiều tốt/xấu thì khai báo trong `DIRECTION`). Không cần sửa
phần evaluation: `compare()` tự lấy mọi metric có trong kết quả.
