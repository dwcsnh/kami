# 18 · Cấu hình khai báo, lưu trữ & benchmark (`kami/config`, `kami/store`, `kami/timeseries.py`, `kami/bench.py`)

Từ kami 0.2 (Sprint 01), mọi thứ người dùng cấu hình — kịch bản, loại xe, fleet, trạm sạc, policy, policy group,
lần chạy — biểu diễn được bằng **dữ liệu JSON** (spec), lưu được vào DB và dựng lại thành object của engine. Engine
không đổi hành vi: một spec cho **metric giống hệt** đoạn code Python 0.1 tương đương.

```
 file JSON / bản ghi DB ──▶ kami.config (spec + kiểm tra) ──▶ build_run ──▶ Simulation (engine 0.1)
                                     ▲                                         │
                    kami.store.Repository (SQLite) ◀── runs.execute ◀──────────┘ metric, chuỗi thời gian, event log
```

| Gói | Vai trò | Phụ thuộc |
|---|---|---|
| `kami.config` | Spec (dataclass), kiểm tra hợp lệ, bộ dựng spec → engine, chuyển cờ CLI 0.1 → spec | Chỉ engine |
| `kami.timeseries` | `MetricSampler`: chụp metric chính theo chu kỳ thời gian mô phỏng | Chỉ engine |
| `kami.store` | SQLite (`sqlite3` của thư viện chuẩn), migration, `Repository`, ghi một lần chạy | `kami.config`; `pyarrow` cho event log Parquet |
| `kami.bench` | Benchmark harness | `kami.config` |

**NFR-5:** `import kami` không nạp `kami.store` hay `sqlite3`; chỉ `kami.store`, `kami/cli.py` (lệnh `run --db`,
`db`) và `kami/bench.py` được import chúng. Có test kiểm tra tĩnh và trong tiến trình con (`tests/test_isolation.py`).

## 1. Spec

```python
from kami.config import load_run_spec, run_spec, RunSpec
spec = load_run_spec("examples/specs/fleets_policy_group.json")   # đọc + kiểm tra
sim = run_spec(spec)                                              # dựng + chạy, trả Simulation đã chạy
spec.to_dict(); RunSpec.from_dict(d)                              # round-trip JSON
```

Mọi spec có `from_dict` / `to_dict` / `to_json`. Thời gian là giây kể từ 0h ngày kịch bản, khoảng cách mét, tiền VND.
Mọi trường có giá trị mặc định trừ các trường ghi **bắt buộc**. Ví dụ đầy đủ ở
[`examples/specs/`](../../examples/specs/) (mỗi preset một file `preset_<tên>.json`, cộng `fleets_policy_group.json`).

### `RunSpec` — một lần chạy

| Trường | Mặc định | Ý nghĩa |
|---|---|---|
| `schema_version` | 1 | Phiên bản schema; file mới hơn bản kami hỗ trợ bị từ chối |
| `name` | `"run"` | Nhãn |
| `scenario` | **bắt buộc** | `ScenarioSpec` hoặc tham chiếu DB `{"ref": …}` |
| `vehicle_types` | `[]` | Danh sách `VehicleTypeSpec` hoặc ref |
| `fleets` | `[]` | Danh sách `FleetSpec` hoặc ref. Rỗng → dùng `scenario.n_drivers` |
| `charging_stations` | `[]` | Danh sách `ChargingStationSpec` hoặc ref (engine dùng từ Sprint 05) |
| `policy_group` | nhóm rỗng (= baseline) | `PolicyGroupSpec` hoặc ref |
| `behavior` | mặc định | `BehaviorSpec` |
| `sim_config` | `{}` | Ghi đè `SimConfig` (thưa) |
| `seed` | `null` | Ghi đè `scenario.seed` |
| `crn_seed` | `null` | Seed CRN; `null` = seed kịch bản (docs/engine/05) |
| `outputs.event_log` | `"parquet"` | `parquet` (cần `pyarrow`), `csv.gz` hoặc `none` |
| `outputs.trajectories` | `"none"` | `parquet`: bật `SimConfig.record_trajectories` và ghi `trajectories.parquet` (Sprint 02, docs/engine/02) |
| `outputs.replay` | không có (= `"none"`) | `json`: bật ghi quỹ đạo và ghi thư mục phát lại `replay/` (`kami.replay` v1, Sprint 03, docs/engine/20). Không khai báo thì `to_dict` không có trường này |

### `ScenarioSpec` — thế giới ngoại sinh

| Trường | Mặc định | Ý nghĩa |
|---|---|---|
| `name` | `"scenario"` | Với nguồn `synthetic`, tên là một phần của dòng ngẫu nhiên (cùng tên + seed = cùng kịch bản) |
| `network` | lưới 8 km | `{"kind": "grid", "width_m", "height_m", "spacing_m": 250, "speed_kmh": 25}` hoặc `{"kind": "road", "name": "example_network", "data_root", "dynamics_file", "scenario_time", "backend": "auto"}` |
| `zones` | vuông 1 km | `{"kind": "square", "cell_m"}`, `{"kind": "h3", "resolution"}` hoặc `{"kind": "file", "name": "example_zones", "neighbor_radius_m": 1500}` |
| `traffic` | mặc định engine | `hour_profile` (24 hệ số), `weather_factor` (`{trạng thái: hệ số}`), `platform_sees_incidents`; Sprint 02: `congestion`, `vehicle_groups` (bảng dưới) |
| `source` | **bắt buộc** | Nguồn demand/supply, xem bảng dưới |
| `n_drivers` | 150 | Số xe khi run không khai báo fleet |
| `seed` | 0 | Seed kịch bản |

| `source.kind` | Hàm 0.1 tương ứng | Trường |
|---|---|---|
| `preset` | `ScenarioBuilder.preset` | `preset` (**bắt buộc**), `demand_per_hour` (200), `overrides` (tham số synthetic bất kỳ, ví dụ `{"t_end": 30600}`) |
| `synthetic` | `ScenarioBuilder.synthetic` | `t_start`, `t_end`, `demand_per_hour`, `profile` (`weekday`/`weekend`/24 số), `n_hotspots`, `hotspot_sigma_m`, `min_trip_m`, `weather` (`[[t, "rain"], …]`), `demand_weather_multiplier`, `incidents` (`[{"t_offset", "duration", "at": "hotspot0" \| node, "radius_m", "factor", "cancel_multiplier"}]`), `supply_multiplier`, `warmup_s` |
| `fleetpy_demand` | `from_fleetpy_demand` | `file` (**bắt buộc**), `t_start`, `t_end`, `time_offset`, `capacity`. Cần `network.kind = "road"` |
| `csv` | `from_csv` | `file` (**bắt buộc**), `time_col`, `origin`, `dest`, `coords` (`xy`/`node`/`lonlat`), `t_start`, `t_end` |
| `zonal` (Sprint 02) | `ScenarioBuilder.zonal` | `area` (Sprint 03, tuỳ chọn: `{"bbox": [lon0, lat0, lon1, lat1], "name"}` — chỉ zone trong khung sinh request và vị trí đầu ca, docs/engine/09), `t_start`, `t_end`, `demand_per_hour` (1000), `profile`, `weights` (file `zone_weights.csv`; bỏ trống = file cạnh file zone của `FileZoneSpec`, không có thì theo số node), `am_hours` ([6, 10]), `pm_hours` ([16, 20]), `gravity_lambda_m` (3000), `smoothing` (0,1), `min_trip_m`, `weather`, `demand_weather_multiplier`, `incidents` (`at`: node hoặc `{"lon", "lat"}` — không có hotspot), `supply_multiplier`, `warmup_s` |

`incidents[].at` của `synthetic`/`preset` cũng nhận `{"lon": …, "lat": …}` (Sprint 02).

**Trường traffic của Sprint 02 (B01-9, quyết định D17).** Chỉ thêm trường tuỳ chọn, `schema_version` vẫn là 1: tài
liệu cũ hợp lệ và không đổi nghĩa (`to_dict` của spec không khai báo các trường này không đổi).

| Trường | Nội dung |
|---|---|
| `traffic.congestion` | `{}` = mặc định Hà Nội. `kind` (`zone_group` \| `file`), `period_s` (3600), `profiles` (`{nhóm: [24 hệ số]}`, ghép với mặc định `core`/`inner`/`outer`), `zone_groups` (`"ring"` hoặc `{zone: nhóm}`), `zone_groups_file` (CSV `zone,group`), `center` (`{"lon", "lat"}`), `ring_radii_m`, `ring_groups`, `road_class_scale`, `file` (CSV `zone,hour,factor` cho `kind="file"`). Đường dẫn file: như `source.file` |
| `traffic.vehicle_groups` | `{"car": {}, "bike": {"speed_factor": 0.9, "congestion_scale": 0.5}}` — khoá chỉ nhận `car`/`bike`; trường bỏ trống lấy mặc định của nhóm. Không khai báo = mọi xe đi như ô tô |
| `sim_config.record_trajectories`, `retime_threshold`, `retime_min_s` | Các trường mới của `SimConfig` (docs/engine/02) |
Đường dẫn `file` được thử theo thứ tự: tuyệt đối hoặc tương đối với thư mục hiện tại, rồi tương đối với data root
của mạng (ví dụ `demand/example_demand/matched/example_network/example_400.csv`).

### Loại xe, fleet, trạm sạc

| Spec | Trường |
|---|---|
| `VehicleTypeSpec` | `name` (**bắt buộc**), `group` (`car`/`bike`), `seats` (4), `range_km` (tuỳ chọn) |
| `FleetSpec` | `name` (**bắt buộc**), `composition`: `[{"vehicle_type": <tên>, "count": n}]` (**bắt buộc**, ≥ 1 phần tử) |
| `ChargingStationSpec` | `name` (**bắt buộc**), đúng một vị trí: `lon` + `lat` hoặc `node`; `ports` (1), `power_kw` (60) |

**Quy tắc fleet → xe (Sprint 01, quyết định D6).** Tổng số xe của các fleet thay cho `n_drivers`; hệ số
`supply_multiplier` của preset vẫn nhân lên (preset `undersupply` với fleet 50 xe → 30 xe). Kịch bản được sinh như
0.1, rồi xe thứ `i` (theo thứ tự sinh) nhận slot `L[floor(i·len(L)/n)]` của danh sách mở rộng `L` các cặp
`(fleet, loại xe)` — mỗi xe khai báo một phần tử, theo thứ tự fleet rồi thành phần. Chỉ `capacity` (= `seats`) và
`attrs["fleet_id"]`, `attrs["vehicle_type"]`, `attrs["vehicle_group"]` (= `group`, Sprint 02) thay đổi; mọi rút ngẫu
nhiên giữ nguyên, nên một fleet một loại xe 4 chỗ cho kết quả giống hệt không khai báo fleet. `group` có tác dụng
trên mạng khi kịch bản khai báo `traffic.vehicle_groups` (Sprint 02, docs/engine/08). `range_km` và trạm sạc được lưu
và kiểm tra nhưng engine chưa dùng (Sprint 05).

### Policy và policy group

```json
{"name": "surge+reposition", "members": [
  {"policy": {"plugin": "surge", "params": {"every": 60}}},
  {"policy": {"ref": "surge_fast", "version": 2}, "params": {"max_surge": 1.5}},
  {"policy": {"plugin": "baseline"}, "enabled": false}
]}
```

- `PolicySpec`: `plugin` (khoá trong `POLICIES`, **bắt buộc**), `params` (tham số khởi tạo), `name`/`version` (do
  `Repository` điền khi giải tham chiếu).
- Tham số hợp lệ đọc từ chữ ký `__init__` của lớp policy và các lớp cha nó chuyển `**kw` tới (quyết định D4); kiểu
  suy từ giá trị mặc định (tham số mặc định là số nguyên nhận mọi số; mặc định `None` nhận số, chuỗi, bool hoặc
  `null`). `matching` (các trường của `MatchingParams`) và `batch_window` dùng chung cho mọi policy.
- `PolicyGroupMember.params` ghi đè tham số của policy chỉ trong nhóm này.
- **Nhóm → policy (D5):** 0 thành viên bật → `Baseline()`; 1 → chính policy đó (không bọc `Composite`, để giống
  hệt 0.1); ≥ 2 → `Composite(*members)` theo thứ tự khai báo (docs/engine/07).

### Behavior

`BehaviorSpec`: `preset` (`default` | `employed_drivers`) → `registry` (thư mục model registry; `slots`
`{slot: phiên bản}`, bỏ trống = bản mới nhất của mọi slot có thư mục) → `models` (`{slot: {"class": …, "params":
{…}}}`, lớp trong `kami.behavior.models`). Bước sau ghi đè bước trước. Wrapper: `{"class": "HazardScaler", "params":
{"inner": {"class": "WeibullCancel"}, "factor": 1.2}}`. Model phải trả lời đúng câu hỏi của slot (ví dụ slot
`booking` cần `p_book`).

### `sim_config`

Dict thưa ghi đè các trường của `SimConfig` (docs/engine/02); `fare` ghi đè `FareModel`, `pooling` ghi đè
`PoolingParams` (chỉ để biểu diễn cấu hình 0.1). Riêng `timeseries_interval_s` mặc định **300 s** khi chạy từ spec
(`null` tắt bộ thu chuỗi thời gian).

### Thông báo lỗi

Mọi lỗi của một tài liệu được gom vào một `SpecError`, mỗi lỗi kèm đường dẫn trường:

```
cấu hình không hợp lệ (2 lỗi):
  - scenario.source.preset: preset 'rainy' không tồn tại; ý bạn là 'rain'? (có: accident, oversupply, rain, …)
  - policy_group.members[0].policy.params.wait_treshold: trường không tồn tại; ý bạn là 'wait_threshold'? (có: …)
```

Kiểm tra gồm: thiếu trường bắt buộc, sai kiểu (bool không được coi là số), ngoài khoảng, giá trị enum, trường lạ (có
gợi ý tên gần đúng), preset/plugin/model không tồn tại, tham số policy và model, khung giờ rỗng
(`t_start ≥ t_end`), loại xe fleet dùng mà run không khai báo, tên trùng.

### CLI 0.1 → spec

`spec_from_cli(...)` (và `python -m kami spec <cờ của run>`) cho RunSpec mà `python -m kami run` với cùng cờ chạy.
Lưu ý: như 0.1, `--registry` thay cả suite nên bỏ qua `--employed-drivers`.

## 2. Chuỗi thời gian metric (`kami/timeseries.py`)

`SimConfig(timeseries_interval_s=Δ)` bật `MetricSampler`; kết quả ở `sim.timeseries.rows` (list dict),
`to_json` (NaN → `null`), `to_csv`, `series(tên)`. Mỗi dòng là một mốc `t_start + k·Δ`, cộng một dòng cuối tại thời
điểm kết thúc. Snapshot tại mốc `m` là trạng thái **sau mọi sự kiện có thời điểm < m**.

| Nhóm | Cột |
|---|---|
| Cửa sổ `[m − Δ, m)` | `rider.requests`, `rider.booked`, `rider.completed`, `rider.cancelled`, `rider.wait_mean`, `rider.wait_p90` (phút, các lượt đón trong cửa sổ), `rider.pickup_mean` (Sprint 03: phút từ lúc tài xế nhận chuyến `TRIP_ACCEPTED` tới lúc đón, các lượt đón trong cửa sổ), `platform.gmv`, `platform.surge_mean` (trung bình surge của báo giá trong cửa sổ) |
| Tích luỹ | `rider.requests_cum`, `rider.booked_cum`, `rider.completed_cum`, `rider.cancelled_cum`, `platform.gmv_cum` |
| Trạng thái tại `m` | `rider.waiting_now`, `driver.online`, `driver.idle` (đỗ), `driver.repositioning` (rảnh và đang chạy: tự đi hoặc platform điều), `driver.en_route`, `driver.on_trip`, `driver.utilization_now` (= on_trip / online) |

Cách hoạt động (D7, D8): bộ thu đăng ký listener của `EventLog` (được gọi cả khi `record_events=False`), đọc trạng
thái tài xế trực tiếp lúc chụp. Vòng lặp sự kiện chỉ thêm một phép so sánh `ev.time >= mốc` — không thêm sự kiện vào
hàng đợi, không rút số ngẫu nhiên, nên metric, `events_processed` và event log **giống hệt** khi bật/tắt. Trên benchmark mốc,
chi phí bật bộ thu nằm trong sai số đo (`grid_am_peak_baseline` so với `grid_am_peak_baseline_nots`).

Metric tổng hợp đếm khách theo cửa sổ đo (`measure_from`, warm-up bị loại, docs/engine/11) còn chuỗi thời gian đếm
mọi sự kiện, nên tổng theo cửa sổ chỉ bằng metric tổng hợp khi kịch bản không có warm-up.

## 3. Lưu trữ (`kami/store`)

```python
from kami.store import Repository, execute
repo = Repository.open("kami.db")                    # tạo / migrate schema
repo.save_vehicle_type(VehicleTypeSpec("vf_e34", seats=4, range_km=285))
repo.save_fleet(FleetSpec("taxi", [FleetComposition("vf_e34", 90)]))
repo.save_policy(PolicySpec("surge", {"every": 60}), name="surge_fast")   # → (policy_id, version)
result = execute(RunSpec.from_dict({"scenario": {"ref": "rain"}, "fleets": [{"ref": "taxi"}],
                                    "policy_group": {"members": [{"policy": {"ref": "surge_fast"}}]}}),
                 repo, artifacts_dir="runs")
repo.get_run(result.run_id); repo.run_metrics(result.run_id); repo.run_timeseries(result.run_id)
```

- **DB:** SQLite qua `sqlite3` của thư viện chuẩn (D1). Mọi truy cập đi qua `Repository`, nên đổi sang PostgreSQL
  (Sprint 08 nếu cần) chỉ chạm gói này.
- **Migration:** `kami/store/migrations/NNNN_<tên>.sql`, áp theo thứ tự, mỗi file một transaction, ghi vào
  `schema_migrations`; chạy lại bỏ qua file đã áp (D2). `python -m kami db init --db kami.db`.
- `Repository` chỉ nhận/trả spec. `save_*` kiểm tra hợp lệ rồi **upsert theo tên**; `get_*` nhận id (`int`, đọc được
  cả bản đã xoá mềm) hoặc tên (`str`, chỉ bản đang dùng); `delete_*` là xoá mềm (`deleted_at`); tên dùng lại được
  sau khi xoá. Không xoá được loại xe đang được fleet dùng.
- **Policy có phiên bản:** `save_policy` tạo policy + phiên bản 1, hoặc thêm phiên bản mới nếu tham số đổi (không
  đổi thì trả phiên bản hiện có); `add_policy_version`; phiên bản là bất biến. Tham chiếu policy trong group không
  ghi `version` được **ghim** vào phiên bản mới nhất lúc lưu group.

### Bảng

| Bảng | Nội dung |
|---|---|
| `vehicle_type`, `fleet`, `charging_station`, `policy_group`, `scenario` | `id`, `name` (duy nhất trong các bản chưa xoá), `spec_json`, `created_at`, `updated_at`, `deleted_at` |
| `fleet_vehicle` | `(fleet_id, position)` → `vehicle_type_id`, `count` — toàn vẹn tham chiếu fleet ↔ loại xe |
| `policy` / `policy_version` | `name`, `plugin`, `source_kind` / `version`, `params_json`, `params_schema_json` và `source_code` (để trống; policy tuỳ biến ngoài phạm vi — requirements §5) |
| `policy_group_member` | `(group_id, position)` → `policy_version_id` (NULL nếu policy khai báo trực tiếp), `plugin`, `params_json` (tham số hiệu lực), `enabled` |
| `run` | `status` (`queued`/`running`/`succeeded`/`failed`/`cancelled`), `run_spec_json` (snapshot đã giải tham chiếu), `source_spec_json` (bản gửi lên), `provenance_json`, `kami_version`, `schema_version`, `seed`, thời điểm, `wall_s`, `events`, `error` |
| `run_metric_summary` | `(run_id, name)` → `value` (NaN lưu `NULL`) |
| `run_metric_timeseries` | `(run_id, name, t)` → `value` (dạng dài) |
| `run_artifact` | `kind` (`event_log`, `trajectories` — Sprint 02, `replay` — Sprint 03: `path` là `manifest.json` của thư mục, `format` `kami.replay`), `path`, `format`, `size_bytes`, `sha256`, `rows` |

### Vòng đời một lần chạy (`kami.store.runs.execute`)

1. `repo.resolve(spec)`: thay mọi `{"ref": …}` bằng nội dung (fleet tham chiếu kéo theo loại xe của nó), trả thêm
   *provenance* (id, tên, phiên bản policy đã dùng). Tham chiếu sai → `SpecError`, **không** tạo bản ghi run.
2. Snapshot = RunSpec đã giải tham chiếu (D10): chạy lại được mà không cần dữ liệu nào khác trong DB
   (`repo.run_spec(run_id)`, NFR-4).
3. Tạo bản ghi `running` → dựng và chạy → ghi metric tổng hợp, chuỗi thời gian, file event log
   `<artifacts>/<run_id>/events.parquet` (hoặc `.csv.gz`) + `run_artifact`, và `trajectories.parquet` (artifact
   `trajectories`, số dòng = số chặng) khi `outputs.trajectories = "parquet"` → `succeeded`.
4. Ngoại lệ trong lúc dựng/chạy → `failed` kèm traceback; không bao giờ để treo `running`. Trả `RunResult(run_id,
   status, sim, error)`.

### Event log của run

Lưu ra **file** (D9), DB chỉ giữ đường dẫn: event log một ngày quy mô GreenSM có thể hàng chục triệu dòng. Mặc định
**Parquet** (nén zstd, cần `pyarrow`: `pip install 'kami[store]'`), thay thế bằng `csv.gz` (thư viện chuẩn). Cột:
`t` (float), `event`, `rider_id`, `driver_id` (int, có thể null), `info` (chuỗi JSON). Ghi bằng
`EventLog.save(path, fmt)`, đọc bằng `kami.eventlog.load(path)` (docs/engine/13).

## 4. Benchmark (`kami/bench.py`, PERF-3)

```bash
python -m kami bench --repeat 5 --out benchmarks/results/<ngày>.json      # chạy suite, xuất JSON
python -m kami bench --compare benchmarks/results/2026-10-07-sprint01.json  # so với mốc, exit 1 nếu thoái lui
python -m kami bench --cases grid_pm_peak_x5,road_example_400 --repeat 3
```

- Mỗi case là một file RunSpec trong [`benchmarks/specs/`](../../benchmarks/specs/) (D11):

  | Case | Nội dung |
  |---|---|
  | `grid_am_peak_baseline` | Lưới 8 km, `weekday_am_peak`, 200 req/h, 150 xe, baseline |
  | `grid_am_peak_baseline_nots` | Như trên, tắt bộ thu chuỗi thời gian (đo chi phí của nó) |
  | `grid_am_peak_surge` | Như trên với `surge` |
  | `grid_pm_peak_x5` | Lưới 12 km, `weekday_pm_peak`, 1.000 req/h, 600 xe, group `surge` + `heatmap_reposition` |
  | `road_example_400` | `example_network`, replay `example_400.csv`, 25 xe |
  | `hanoi_am_peak_small` (Sprint 02) | Mạng `hanoi`, zone H3 r8, tắc đường zone × giờ, nguồn `zonal` 7h–8h 600 req/h, 200 ô tô + 100 xe máy. **Bỏ qua** (ghi `skipped` trong JSON) khi mạng chưa build |

- Mỗi lần lặp chạy trong một tiến trình Python riêng. Ghi `wall_s` của `Simulation.run` (median/min/max),
  `build_s` (nạp mạng + sinh kịch bản), `events`, `events_per_s`, `peak_rss_mb` (`ru_maxrss` của tiến trình con,
  chuẩn hoá đơn vị Linux/macOS), backend mạng, vài metric chính và cờ `deterministic` (mọi lần lặp cho cùng kết
  quả), cùng môi trường (Python, OS, CPU, commit git, router C++ đã build hay chưa).
- `--compare`: bảng % thay đổi; case chậm hơn hoặc tốn RAM hơn quá `--threshold` (mặc định 10%) bị đánh dấu và
  lệnh trả mã 1; ghi chú `results changed` nếu số sự kiện/metric đổi; cảnh báo khi Python/CPU khác mốc.
- **Môi trường mốc:** env conda `fleetpy` (Python 3.10, router C++ đã build, có `scipy`). Số liệu của interpreter
  khác (ví dụ Python hệ thống không có `scipy` → matching greedy) không so sánh được với mốc. Kết quả mốc được commit
  trong `benchmarks/results/` và chép vào backlog sprint.
