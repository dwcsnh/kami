# 02 · Simulation engine (`kami/core/engine.py`)

## Khởi tạo và chạy

```python
sim = Simulation(scenario, policy=PoolAfterWait(), behavior=BehaviorSuite(), config=SimConfig(), crn_seed=None)
sim.run()            # chỉ chạy được một lần; muốn chạy lại thì tạo Simulation mới
sim.metrics()        # dict metric (docs/engine/11)
sim.log              # EventLog (docs/engine/13)
sim.timeseries       # MetricSampler nếu SimConfig.timeseries_interval_s được đặt, ngược lại None (docs/engine/18)
sim.trajectories     # TrajectoryRecorder nếu SimConfig.record_trajectories, ngược lại None (mục "Quỹ đạo" bên dưới)
sim.riders, sim.drivers, sim.jobs
```

- `crn_seed` mặc định bằng `scenario.seed`. Hai `Simulation` cùng kịch bản và cùng `crn_seed` dùng chung mọi số
  ngẫu nhiên của agent (docs/engine/05).
- `Simulation` tự tạo `TrafficLayer` mới từ `scenario.traffic`. Network được dùng chung giữa các lần chạy. Từ Sprint
  02 network có thể giữ trạng thái (travel time theo nhóm xe / tắc đường, router sự cố), nên `run()` gọi
  `traffic.activate()` trước sự kiện đầu tiên để đưa network về trạng thái của run này.

### `SimConfig`

| Trường | Mặc định | Ý nghĩa |
|---|---|---|
| `batch_window` | 10 s | Chu kỳ `DISPATCH_TICK`. Policy có thể ghi đè bằng `Policy.batch_window` |
| `boarding_s` / `alighting_s` | 30 / 20 s | Thời gian lên / xuống xe (cộng vào chặng kế tiếp) |
| `idle_decision_s` | 120 s | Xe rảnh bao lâu thì hỏi `IdleMoveModel` |
| `idle_recheck_s` | 300 s | Model chọn "đứng yên" thì bao lâu sau hỏi lại |
| `drain_s` | 3600 s | Sau `t_end` vẫn chạy tiếp để các chuyến dở dang kết thúc (không còn request mới) |
| `cancel_step_s` | 20 s | Bước tích phân hazard hủy chuyến |
| `cancel_lookahead_s` | 1800 s | Tầm nhìn khi gài sự kiện hủy; quá tầm thì gài sự kiện kiểm tra lại |
| `default_quote_eta` | 900 s | ETA hiển thị khi không thấy xe rảnh nào |
| `traffic_update_s` | 3600 s | Chu kỳ `TRAFFIC_UPDATE` (nạp travel time động của `RoadNetwork` nếu có) |
| `record_events` | True | Tắt để chạy nhanh hơn khi chỉ cần metric |
| `timeseries_interval_s` | None | Bật `MetricSampler` với chu kỳ này (s thời gian mô phỏng); kết quả ở `sim.timeseries` (docs/engine/18). Không đổi kết quả mô phỏng |
| `record_trajectories` | False | Ghi lộ trình + thời điểm qua node của mọi chặng (`sim.trajectories`). Không đổi kết quả mô phỏng (Sprint 02) |
| `retime_threshold` | 0,1 | `CONGESTION_UPDATE` tính lại chặng khi thời gian còn lại lệch quá tỷ lệ này (Sprint 02) |
| `retime_min_s` | 60 s | … trừ khi chặng còn ít hơn số giây này |
| `fare` | `FareModel()` | Docs/10 |
| `pooling` | `PoolingParams()` | Docs/10 |

## Cơ chế thời gian (design doc §4.1)

Engine dùng mô hình lai: mỗi hành động của agent là một sự kiện riêng, còn matching gom theo batch ở
`DISPATCH_TICK`. Vòng lặp lõi chỉ vài dòng:

```python
while q:
    ev = heapq.heappop(q)              # Event(time, priority, seq, kind, payload)
    if ev.time > t_stop: break         # t_stop = t_end + drain_s
    self.t = ev.time
    getattr(self, "_on_" + ev.kind.value.lower())(**ev.payload)
```

`run()` lên lịch sẵn các sự kiện sau:
- `DRIVER_ONLINE`/`DRIVER_OFFLINE` theo ca của từng tài xế;
- `REQUEST_CREATED` cho từng request;
- `WEATHER_CHANGE`, `INCIDENT_START`/`INCIDENT_END`;
- `TRAFFIC_UPDATE` mỗi giờ;
- `CONGESTION_UPDATE` đầu tiên lúc `t_start`, **chỉ khi** kịch bản có `traffic.congestion` (kịch bản cũ không đổi thứ
  tự sự kiện); mỗi lần xử lý tự hẹn lần kế tiếp ở bội số `period_s` sau đó, tới hết `drain_s`;
- `DISPATCH_TICK` đầu tiên;
- các tick khai báo trong `policy.tick_intervals`.

Sau đó `run()` gọi `policy.on_start()`. Khi kết thúc, engine đóng sổ tài xế còn online (`_finalise`) và gọi
`policy.on_end()`.

## Ba kỹ thuật bắt buộc (design doc §4.2)

### 1. Tie-break tất định
Heap so sánh theo `(time, priority, seq)`. `priority` cố định theo loại sự kiện (bảng ở docs/engine/03): môi trường đổi
trước, rồi xe tới điểm, rồi khách hủy, request mới, ra quyết định nền tảng, cuối cùng là timer của policy.
`seq` tăng dần theo thứ tự lên lịch. Nhờ vậy, cùng kịch bản và cùng seed thì log giống nhau từng dòng
(có test `test_reproducible`).

### 2. Lazy invalidation
Engine không xoá sự kiện khỏi heap. Mỗi sự kiện mang một "vé", và handler bỏ qua sự kiện nếu vé đã cũ:

| Vé | Thuộc | Tăng khi | Dùng cho |
|---|---|---|---|
| `driver.plan_version` | Driver | bắt đầu chặng mới, đổi plan, ngắt chặng, chuyển trạng thái rảnh | `ARRIVE_STOP`, `IDLE_MOVE`, `IDLE_ARRIVE` |
| `rider.cancel_token` | Rider | mỗi lần gài lại thời điểm hủy | `RIDER_CANCEL` |
| `rider.state` | Rider | — | mọi handler kiểm tra trạng thái trước khi hành động |

### 3. Tách kế hoạch và thực tế (cách của FleetPy)
- **Kế hoạch:** ETA hứa với khách (`rider.eta_promised`) và `leg.promised_arrive` dùng
  `TrafficLayer.estimate()`. Mặc định hàm này **không biết sự cố** (`platform_sees_incidents=False`).
- **Thực tế:** chặng xe chạy dùng `TrafficLayer.travel()`, có tính sự cố. Khi môi trường đổi giữa chặng, engine
  tính lại thời gian chặng nhưng không sửa lời hứa.
- Chênh lệch giữa hai bên đo bằng metric `rider.eta_error_abs`.

## Hủy chuyến như một quá trình sống sót (survival)

Mỗi khách có một "ngân sách hazard" `E ~ Exp(1)`, rút từ CRN với khoá `("cancel_<pha>", rider)`. Khách hủy tại
thời điểm τ đầu tiên mà hazard tích luỹ `∫ h(s) ds` đạt `E`. Đây là phương pháp inverse-transform cho mô hình
survival có hazard thay đổi theo thời gian.

- Pha `waiting` (chưa có xe) dùng `cancel_wait`. Pha `matched` (đã có xe) dùng `cancel_matched`; khi đổi pha thì
  dùng ngân sách mới.
- `_arm_cancel` tích phân hazard với bước `cancel_step_s` để tìm τ, rồi đặt `RIDER_CANCEL` tại τ. Nếu τ vượt
  `cancel_lookahead_s`, nó đặt một sự kiện `recheck` để tính tiếp từ đó.
- Khi covariate đổi (thời tiết, sự cố), `_environment_change` làm theo thứ tự:
  1. `_accrue` hazard đến hiện tại với điều kiện **cũ**;
  2. đổi môi trường;
  3. gài lại thời điểm hủy với điều kiện mới.
- **Chu kỳ tắc đường mới** (`_on_congestion_update`, quyết định D12):
  1. lấy vị trí hiện tại của mọi xe đang chạy theo lộ trình **cũ** (`_leg_position` — cố định lộ trình đã đi);
  2. `_accrue` hazard của khách đang chờ;
  3. `traffic.apply_period(t)` đặt travel time mới (không đổi thì dừng);
  4. với mỗi chặng còn ≥ `retime_min_s`: thời gian còn lại mới = `travel(node hiện tại, đích)`. Lệch quá
     `retime_threshold` thì cắt chặng tại node hiện tại và chạy tiếp theo đường mới (chặng chưa xuất phát — đang
     cho khách lên xe — giữ giờ xuất phát);
  5. gài lại thời điểm hủy; ghi `CONGESTION_UPDATE` (`hour`, `moving`, `retimed`).
- Khách hủy khi tài xế đang tới đón: các stop của khách bị xoá khỏi plan. Nếu tài xế đang chạy tới đúng khách đó,
  chặng hiện tại bị ngắt và tài xế chuyển sang stop kế tiếp (hoặc về trạng thái rảnh).

## Vị trí của xe đang chạy

`current_loc(driver)` nội suy dọc lộ trình thật: `TrafficLayer.path(…, group=leg.group)` được tính một lần cho mỗi
chặng rồi cache trong `leg.path`, và vị trí là node đã qua cuối cùng theo tỷ lệ thời gian. Khi ngắt chặng (`_interrupt_leg`),
tài xế đứng tại node đó và quãng đường cộng theo đúng tỷ lệ đã chạy.

Mỗi tài xế có `Driver.group` (nhóm xe trên mạng, docs/engine/08): mọi truy vấn traffic cho chặng của tài xế (ETA
báo giá, ETA nhận cuốc, matching, `travel` của chặng, `path`) dùng nhóm này; `Leg.group` lưu nhóm của chặng.

## Quỹ đạo (Sprint 02, S02-6, `kami/trajectory.py`)

Khi `SimConfig.record_trajectories` bật, mỗi chặng kết thúc (tới nơi, hoặc bị cắt do đổi plan / sự cố / tắc đường /
hết ca) được ghi thành một `LegTrace(driver_id, leg_seq, purpose, occupied, rider_id, group, t_depart, t_end, cut,
nodes, times)`:

- `nodes` là lộ trình engine dùng để định vị xe (`leg.path`, chưa tính thì tính lúc chặng kết thúc), cắt theo đúng
  quy tắc của `_leg_position` khi chặng bị ngắt — node cuối là nơi xe chạy tiếp;
- `times` nội suy theo travel time tích luỹ của lộ trình giữa giờ xuất phát và giờ tới; chặng đủ kết thúc **đúng** lúc
  `ARRIVE_STOP` (= `PICKUP`/`DROPOFF`);
- ghi quỹ đạo chỉ **đọc** trạng thái engine: cùng kịch bản cho cùng kết quả khi bật hay tắt (có test).

API: `sim.trajectories.of(driver_id) → [(lon, lat, t)]` (nội suy theo `edge_geometry` khi mạng có; lưới trả `(x, y,
t)`), `legs_of(driver_id)`, `save(path)` → `trajectories.parquet` (một dòng mỗi chặng: `nodes`, `times`, `lon`, `lat`
và polyline mở rộng `path_lon`, `path_lat`, `path_t` cho deck.gl `TripsLayer`; metadata `kami.coords`), `kami.trajectory.load(path)`.

Sprint 03: `kami.replay` dựng từ các chặng này **dòng thời gian trạng thái** của từng xe (chặng = đoạn chạy, khoảng hở
giữa hai chặng = đoạn đứng yên) và ghi thư mục phát lại cho web — xem [20-visualizer.md](20-visualizer.md). Chặng
độ dài 0 (xe đã ở điểm đón) hoặc bị cắt trước giờ xuất phát không có chuyển động, chỉ kết thúc khoảng hở trước nó.

## API dành cho policy

Policy **chỉ** tác động vào thế giới qua các hàm sau (design doc §7.1):

| Hàm | Tác dụng |
|---|---|
| `sim.schedule(t, "POLICY_TIMER", r=rider, **payload)` | Hẹn giờ; tới hạn gọi `policy.on_timer(sim, rider, **payload)`. Loại sự kiện khác sẽ bị từ chối |
| `sim.default_dispatch(jobs, drivers, matching_params)` | Matching mặc định (docs/engine/10) |
| `sim.offer_trip(driver, job) -> bool` | Gửi cuốc. `DriverAcceptModel` quyết định; nếu nhận thì gọi `assign` |
| `sim.assign(driver, job)` | Gán cứng, bỏ qua bước nhận cuốc (tài xế là nhân viên, hoặc ép dispatch) |
| `sim.merge_jobs(r, partner, surcharge, partner_surcharge=None) -> bool` | *(pooling — ngoài phạm vi 0.2, giữ cho tương thích, xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại))* Ghép hai khách: cả hai đang WAITING, hoặc một WAITING và một MATCHED (chèn vào plan của tài xế) |
| `sim.reposition(driver, node) -> bool` | Điều một xe đang rảnh tới `node` |
| `sim.set_surge(zone, multiplier)` | Hệ số surge cho các báo giá sau đó trong zone |
| `sim.behavior.pool_accept(rider, offer_or_surcharge) -> bool` | *(pooling — ngoài phạm vi 0.2, giữ cho tương thích, xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại))* Hỏi khách có nhận ghép không (dùng CRN) |
| `sim.pooling.find_partner(r, max_o_km, max_d_km, include_matched)` | *(pooling — ngoài phạm vi 0.2, giữ cho tương thích, xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại))* Tìm người ghép khả thi (docs/engine/10) |

Hàm đọc (không đổi trạng thái): `sim.t`, `sim.riders`, `sim.drivers`, `sim.jobs`, `sim.open_jobs`,
`sim.idle_drivers()`, `sim.current_loc(d)`, `sim.zone_stats(window_s)`, `sim.context(node)`, `sim.traffic`,
`sim.zones`, `sim.network`.

## Kế toán tài xế

`_set_driver_state` cộng dồn thời gian ở trạng thái cũ mỗi khi trạng thái đổi:
- `online_time`: mọi trạng thái khác `OFFLINE`;
- `busy_time`: `EN_ROUTE` và `ON_TRIP`;
- `occupied_time`: `ON_TRIP`;
- `idle_gaps`: các khoảng rảnh trước mỗi lần nhận cuốc.

Quãng đường tính theo chặng: `dist_total`, và `dist_empty` cho các chặng không có khách. Thu nhập tài xế bằng
`FareModel.driver_payout(fare, surcharge)` cộng tại lúc trả khách.

## Mở rộng engine

- **Sự kiện mới:** thêm vào `EventType` và `EVENT_PRIORITY`, viết `_on_<tên>` trong `Simulation`.
- **Thay matching hoặc giá:** viết policy (docs/engine/07), không cần sửa engine.
- **Thay hành vi:** thay một slot trong `BehaviorSuite` (docs/engine/06), không cần sửa engine.

## Shared ride V1 trong engine

`SimConfig.shared_ride` mặc định tắt; bật bằng `SharedRideConfig(enabled=True, ...)`.
Dispatch V1 xét cặp WAITING trước, sau đó gán Exclusive trên xe còn lại. State và
kế toán do `Simulation`/`SharedLifecycle` cập nhật; evaluator chỉ trả phương án.
Cặp chỉ commit sau khi tài xế nhận offer. Hủy/timeout dùng plan_version để loại
arrival cũ; cleanup bảo toàn vị trí thật, km đã chạy và dwell chưa kết thúc.
Nhánh tắt giữ assign/pooling/price của 0.1. Xem [Shared V1](23-shared-rides-v1.md).
