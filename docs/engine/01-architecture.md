# 01 · Kiến trúc tổng thể

## Các lớp

```
 ┌───────────────┐   ┌──────────────────────────┐
 │ Network/Zones │──▶│ ScenarioBuilder          │  demand + supply + thời tiết + sự cố + thuộc tính agent
 │ (grid|FleetPy)│   │  synthetic / preset /    │  (phần NGOẠI SINH, replay y hệt cho mọi arm)
 └───────────────┘   │  replay FleetPy / CSV    │
                     └────────────┬─────────────┘
                                  ▼ Scenario
 ┌──────────────┐   ┌───────────────────────────────┐   ┌───────────────────┐
 │ Policy       │◀─▶│ Simulation (kami.core.engine) │◀─▶│ BehaviorSuite     │
 │ (hooks)      │   │  heap (t, priority, seq)      │   │  (model registry) │
 └──────────────┘   │  Rider / Driver / Job         │   └─────────┬─────────┘
                    │  matching · pooling · pricing │             │ xác suất
                    └──────┬─────────────────┬──────┘             ▼
                           │                 │              CRN(seed).u(key)  → quyết định = u < p
                    ┌──────▼──────┐   ┌──────▼──────┐
                    │TrafficLayer │   │  EventLog   │──▶ metrics.compute ──▶ evaluation (CRN, CI, rule)
                    └─────────────┘   └─────────────┘
```

| Thành phần (design doc §3) | Module kami | Docs |
|---|---|---|
| Data layer | `kami.network` (FleetPy `data/networks`, `data/zones`, `data/demand`) | 08, 09, 16 |
| Scenario builder | `kami.scenario` | 09 |
| Simulation engine | `kami.core.engine`, `kami.core.events`, `kami.core.agents` | 02–04 |
| Policy plugins | `kami.policy` | 07 |
| Behavior models | `kami.behavior`, `kami.training` | 06, 14 |
| Traffic layer | `kami.traffic`, `kami.network` | 08 |
| Event log | `kami.eventlog` | 13 |
| Evaluator (CRN) | `kami.core.crn`, `kami.metrics`, `kami.evaluation` | 05, 11, 12 |

## Luồng một chuyến đi

```
REQUEST_CREATED ─ engine báo giá (FareModel × surge, ETA xe gần nhất) ─ policy.price()
   │  BookingModel.p_book  vs  CRN("book", rider)
   ├─ không đặt ─▶ OFFER_REJECTED, rider DECLINED
   └─ đặt ─▶ OFFER_ACCEPTED, rider WAITING, tạo Job, gài RIDER_CANCEL (survival), policy.on_request()
            │
DISPATCH_TICK (mỗi batch_window giây) ─ policy.on_dispatch(open_jobs, idle_drivers) ─▶ cặp (job, driver)
            │  DriverAcceptModel.p_accept  vs  CRN("driver_accept", driver, job, n_reject)
            ├─ từ chối ─▶ TRIP_REJECTED, driver vào tabu của job
            └─ nhận ─▶ TRIP_ACCEPTED, rider MATCHED (ETA hứa = ước lượng của nền tảng), gài lại RIDER_CANCEL pha "matched"
                     │
ARRIVE_STOP (pickup) ─▶ PICKUP, rider ONBOARD, driver ON_TRIP
ARRIVE_STOP (dropoff) ─▶ DROPOFF, rider DONE, cộng thu nhập tài xế, policy.on_dropoff()
                     │
driver hết plan ─▶ DriverShiftModel (nghỉ?) ─▶ policy.on_driver_idle() (điều xe?) ─▶ IDLE_MOVE (IdleMoveModel)
```

`POLICY_TIMER`, `REPOSITION_TICK`, `PRICE_UPDATE` cho policy chen vào bất kỳ lúc nào.
`WEATHER_CHANGE` và `INCIDENT_START/END` đổi trạng thái giao thông, tính lại thời gian các chặng đang chạy và
gài lại thời điểm hủy của khách đang chờ.

## 8 nguyên tắc của design doc được hiện thực thế nào

| # | Nguyên tắc | Cách làm trong kami |
|---|---|---|
| 1 | Agent-based, discrete-event | Mỗi `Rider`/`Driver` là object riêng; heap sự kiện `(time, priority, seq)`; lai event-driven + `DISPATCH_TICK` |
| 2 | Policy là plugin | `Policy` có hook với default = baseline; policy chỉ gọi API của `Simulation` |
| 3 | Hành vi = model tại điểm quyết định | 7 slot trong `BehaviorSuite`; model trả xác suất/hazard, engine quyết định |
| 4 | Luật chung, rút ngẫu nhiên riêng | Thuộc tính cá nhân rút từ phân phối trong `ScenarioBuilder.rider_attrs/driver_attrs` |
| 5 | Replay ngoại sinh, mô hình hoá hậu can thiệp | `Scenario` chỉ chứa phần ngoại sinh; mọi phản ứng sau quyết định đều do model sinh ra |
| 6 | CRN | `CRN(seed).u(stream, *keys)` theo khoá agent × quyết định; `Experiment` ghép cặp theo (kịch bản, seed) |
| 7 | Tách training | `kami.training` fit → `ModelRegistry` (JSON) → `BehaviorSuite` |
| 8 | Đúng chiều > đúng tuyệt đối | Báo cáo có chiều/verdict từng metric, kiểm tra ổn định dấu khi đổi giả định (`sign_stable`) |

## Phụ thuộc

- Lõi chỉ dùng thư viện chuẩn: chạy được trên Python 3.9 trở lên mà không cần cài thêm.
- `scipy` (tuỳ chọn): Hungarian matching và t-quantile chính xác. Nếu thiếu, engine tự chuyển sang greedy và
  khai triển Cornish–Fisher.
- FleetPy (tuỳ chọn): mạng OSM thật, router C++, zone, demand. Cần `numpy`, `pandas`, `pyproj`.
- `h3`, `pandas`, `pyarrow` (tuỳ chọn): zone H3, DataFrame, Parquet.
