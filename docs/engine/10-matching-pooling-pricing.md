# 10 · Matching, pooling, pricing

## Matching (`kami/matching.py`)

Mỗi `DISPATCH_TICK`, `sim.default_dispatch(open_jobs, idle_drivers, MatchingParams)` làm hai bước:

1. **Sinh ứng viên** (`candidate_pairs`). Với mỗi job:
   - lọc tài xế theo khoảng cách chim bay ≤ `max_pickup_eta × max_speed_mps`, bỏ tài xế trong `job.tabu` và xe
     không đủ chỗ;
   - giữ `candidates_per_job` xe gần nhất;
   - tính ETA thật trên mạng bằng **một** truy vấn many-to-one (`TrafficLayer.many_to_one`, góc nhìn của nền tảng);
   - `cost = eta − wait_weight × thời_gian_khách_đã_chờ`.
2. **Giải bài toán gán** (`solve`):
   - `hungarian`: `scipy.optimize.linear_sum_assignment` (design doc §12). Nếu thiếu scipy thì tự lùi về greedy;
   - `greedy`: sắp xếp theo cost tăng dần, lấy cặp chưa dùng.

| `MatchingParams` | Mặc định | Policy tương ứng (design doc §7.3) |
|---|---|---|
| `max_pickup_eta` | 900 s | Bán kính đón tối đa |
| `candidates_per_job` | 12 | Đánh đổi tốc độ và chất lượng |
| `max_speed_mps` | 16 | Bộ lọc thô |
| `solver` | `hungarian` | Tối ưu toàn cục vs greedy |
| `wait_weight` | 0 | Ưu tiên khách chờ lâu |

Độ dài cửa sổ batch là `Policy.batch_window` hoặc `SimConfig.batch_window`.

Engine gửi từng cặp qua `offer_trip`. Tài xế từ chối thì job quay lại hàng đợi với tài xế đó trong `tabu`.

## Pooling (`kami/pooling.py`)

> **Phạm vi hiện tại (kami 0.2):** sản phẩm chỉ matching **1 tài xế – 1 khách**, chưa có ghép chuyến
> (shared ride). Phần pooling ở đây là của kami 0.1, được giữ để tương thích (NFR-2) nhưng **tạm thời không
> dùng** trong kịch bản, policy group, UI và benchmark của 0.2 — xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại).


Thuật toán là **insertion heuristic** giống FleetPy (`src/fleetctrl/pooling/immediate/insertion.py`), viết lại
trên kiểu `Stop` gọn của kami (lý do ở docs/engine/16).

| Hàm | Ý nghĩa |
|---|---|
| `evaluate(start_loc, start_t, stops, onboard_since, check=True)` | Chạy thử một chuỗi stop bằng ETA của nền tảng, cộng thời gian lên/xuống. Trả `PlanEval(stops, total_time, pickup_t, dropoff_t, detour)`, hoặc `None` nếu vi phạm ràng buộc vòng |
| `best_insertion(start_loc, start_t, stops, rider, onboard_since)` | Thử mọi vị trí (i ≤ j) để chèn pickup/dropoff, giữ phương án khả thi tăng thời gian ít nhất. Có O(n²) phương án, mỗi phương án tốn O(n) truy vấn |
| `plan_pair(a, b)` | Thứ tự stop tốt nhất cho hai khách chưa có xe (đi từ điểm đón của `a`) |
| `driver_plan_with(driver, rider)` | Chèn khách vào plan còn lại của một xe đang chạy (có kiểm tra sức chứa) |
| `find_partner(r, max_o_km, max_d_km, include_matched)` | Lọc theo khoảng cách chim bay giữa hai điểm đón và giữa hai điểm đến, xếp theo tổng khoảng cách, kiểm tra khả thi tối đa `max_candidates` người. Ghi kết quả vào `last_eval` để `pool_accept` biết độ vòng dự kiến |

**Ràng buộc** (`PoolingParams`): thời gian trên xe của mỗi khách không vượt
`direct_tt × (1 + max_detour_ratio) + max_detour_abs` (mặc định 50% + 300 s). Ràng buộc được kiểm tra trên ETA
của nền tảng lúc lập plan; thực tế có thể vượt nếu giao thông xấu đi.

**Ghép trong engine** (`sim.merge_jobs`):
- Hai khách đều WAITING: tạo `Job` mới `pooled=True` với `stops` đã tối ưu và thay hai job cũ trong hàng đợi.
- Một khách WAITING, khách kia MATCHED: chèn khách WAITING vào `driver.plan` của xe kia, khách chuyển sang MATCHED
  ngay, xe tính lại chặng hiện tại. ETA đã hứa với khách cũ **không** cập nhật, nên phần trễ do ghép được tính vào
  sai lệch ETA.
- Phụ phí được cộng vào `rider.surcharge` của cả hai khách (có thể khác nhau qua `partner_surcharge`).

## Pricing (`kami/pricing.py`)

```
fare = round(max(min_fare, (base + per_km·km + per_min·phút) × surge), -2)
driver_payout = fare·(1 − take_rate) + max(surcharge, 0)·surcharge_to_driver
platform_revenue = fare + surcharge − driver_payout          (surcharge âm = nền tảng trợ giá)
```

| `FareModel` | Mặc định |
|---|---|
| `base` | 12.000 đ |
| `per_km` | 9.000 đ |
| `per_min` | 400 đ |
| `min_fare` | 25.000 đ |
| `take_rate` | 25% |
| `surcharge_to_driver` | 0 |

Đổi qua `SimConfig(fare=FareModel(...))`. `fare` tính theo `direct_dist` và `direct_tt` lúc đặt, tức là giá trả
trước (upfront). Policy có thể ghi đè trong `price()`.
