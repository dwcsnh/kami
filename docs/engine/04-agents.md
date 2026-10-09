# 04 · Agents (`kami/core/agents.py`)

Agent chỉ **giữ trạng thái**. Mọi chuyển trạng thái đều do engine thực hiện. Policy đọc được agent nhưng không
được sửa trực tiếp (design doc §7.1).

## Rider

```
REQUESTED ──(không đặt)──▶ DECLINED
    │ đặt
    ▼
 WAITING ──(merge với khách MATCHED)──┐
    │ tài xế nhận                      │
    ▼                                  ▼
 MATCHED ──▶ ONBOARD ──▶ DONE
    │  │
    └──┴──(hazard đạt ngân sách)──▶ CANCELLED
```

| Nhóm | Trường | Ý nghĩa |
|---|---|---|
| Định danh | `id`, `t_request`, `origin`, `dest`, `zone`, `dest_zone` | Lấy từ `RequestSpec` của kịch bản |
| Thuộc tính cá nhân | `attrs["patience_min"]`, `["vot"]`, `["price_sens"]`, `["pool_willingness"]` | Rút từ phân phối khi dựng kịch bản (docs/engine/09) |
| Chuyến thẳng | `direct_tt`, `direct_dist` | Thời gian / quãng đường đi thẳng tại lúc đặt, dùng làm mốc tính độ vòng |
| Giá | `quote` (`Quote`), `fare`, `surcharge` | Cước gốc và phụ phí (hoặc giảm giá) ghép chuyến |
| Ghép | `pooled`, `pool_offers`, `pool_accepts`, `job_id`, `driver_id` | Trường `pool*`: *(pooling — ngoài phạm vi 0.2, giữ cho tương thích, xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại))* |
| Mốc thời gian | `t_booked`, `t_matched`, `eta_promised`, `t_pickup`, `t_dropoff`, `t_cancel`, `cancel_phase` | `eta_promised` là thời điểm tuyệt đối nền tảng hứa đón |
| Survival | `hazard_phase`, `hazard_budget`, `hazard_acc`, `hazard_t`, `cancel_token` | Docs/02 |
| Lazy invalidation | `version` | Tăng mỗi lần đổi trạng thái |

`rider.fare_paid` = `fare + surcharge` nếu DONE, ngược lại bằng 0.

## Driver

```
OFFLINE ──online──▶ IDLE ──nhận cuốc──▶ EN_ROUTE ──đón──▶ ON_TRIP ──trả hết, plan rỗng──▶ IDLE
   ▲                  │  (đang cruising / reposition vẫn là IDLE)          │
   └──hết ca / ShiftModel──┘                                CHARGING (dành sẵn)
```

| Nhóm | Trường | Ý nghĩa |
|---|---|---|
| Ca làm | `shift_start`, `shift_end`, `going_offline` | Hết ca khi đang bận thì `going_offline=True`, nghỉ sau khi xong plan |
| Thuộc tính | `attrs["accept_bias"]`, `attrs["income_target"]`, `home_zone`, `capacity` | |
| Vị trí & kế hoạch | `loc`, `leg` (`Leg`), `plan` (list `Stop`), `onboard`, `job_ids`, `plan_version` | `loc` là node cuối cùng đã tới; vị trí lúc đang chạy lấy qua `sim.current_loc(d)` |
| Kế toán | `online_time`, `busy_time`, `occupied_time`, `dist_total`, `dist_empty`, `earnings`, `trips`, `offers`, `rejections`, `idle_gaps` | Docs/02 |

`driver.available` = `state == IDLE and not going_offline`.

## Đối tượng phụ

| Lớp | Trường | Dùng ở đâu |
|---|---|---|
| `Job` | `id`, `rider_ids`, `created_t`, `tabu`, `driver_id`, `pooled`, `stops` | Đơn vị dispatch: 1 khách (phạm vi 0.2), hoặc nhiều khách sau khi policy ghép (pooling của 0.1). `tabu` là các tài xế đã từ chối |
| `Stop` | `kind` (`pickup`/`dropoff`), `rider_id`, `loc` | Phần tử của `driver.plan` và `job.stops` |
| `Leg` | `origin`, `dest`, `t_depart`, `t_arrive`, `dist`, `occupied`, `purpose`, `promised_arrive`, `path` | Một chặng chạy liên tục. `purpose` ∈ {`stop`, `idle`, `reposition`} |
| `Quote` | `fare`, `eta`, `surge`, `surcharge` | Báo giá; `policy.price()` có thể sửa |
| `PoolOffer` | `surcharge`, `waited`, `detour`, `partner_id` | Đầu vào của `PoolAcceptModel` *(pooling — ngoài phạm vi 0.2, giữ cho tương thích, xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại))* |

## Mức cá nhân hoá (design doc §5)

| Mức | Trong kami |
|---|---|
| 1. Object riêng, hành vi giống nhau | Bỏ thuộc tính khỏi `attrs`; model dùng giá trị mặc định |
| 2. **Thuộc tính rút từ phân phối** (mặc định) | `ScenarioBuilder.rider_attrs` / `driver_attrs` |
| 3. Tham số theo lịch sử từng người (ẩn danh) | Đưa vào `RequestSpec.attrs` / `DriverSpec.attrs` khi replay; model đọc `attrs` |
| 4. Trí nhớ, học qua nhiều ngày | Chưa có (docs/engine/17). Có thể làm bằng cách chạy chuỗi kịch bản và cập nhật `attrs` giữa các ngày |

## Trường bổ sung của Shared V1

Rider có service_preference, effective_mode, pair_id/pair_history,
pickup_deadline, cancellation_reason, exclusive_reference_fare,
shared_direct_baseline_s/shared_predicted_extra_s và hazard_history theo phase.
Job có pair_id, cặp vẫn dùng driver.plan gồm bốn Stop. Quote thêm metadata cước
tham chiếu, preference và fare_factor; TripOffer thêm shared/rider_ids có default.
Các field mới nằm sau field cũ, constructor của 0.1 tiếp tục chạy. Hai khách một
người mỗi booking, tối đa hai trong một cặp. Xem [Shared V1](23-shared-rides-v1.md).
