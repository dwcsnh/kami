# Implementation plan — Sprint 01: Nền tảng cấu hình, lưu trữ & benchmark

| | |
|---|---|
| Sprint | [sprint-01-foundation.md](../sprint/sprint-01-foundation.md) |
| Backlog đầu vào | Không có (sprint đầu tiên) — không có mục backlog nào cần xử lý |
| Trạng thái | Chờ duyệt |

## 1. Tóm tắt hướng tiếp cận

Thêm ba gói mới **bên cạnh** lõi engine, không thay đổi hành vi của engine:

```
kami/config/   spec khai báo (dataclass thuần) + kiểm tra hợp lệ + bộ dựng RunSpec → object engine
kami/store/    SQLite (stdlib sqlite3) + migration SQL + repository + ghi/đọc một lần chạy
kami/bench.py  benchmark harness; mỗi case benchmark chính là một file RunSpec JSON
```

- **Spec là dữ liệu**: mỗi spec là `dataclass` có `to_dict()` / `from_dict()` và `schema_version`, đọc/ghi JSON. Không
  thêm thư viện ngoài vào lõi (giữ `dependencies = []` của `pyproject.toml`).
- **Bộ dựng** chỉ gọi các API 0.1 sẵn có (`GridNetwork`, `ScenarioBuilder.preset/synthetic/...`, `POLICIES`,
  `Composite`, `BehaviorSuite`, `ModelRegistry`, `SimConfig`) — vì vậy một `RunSpec` cho **metric giống hệt** đoạn code
  Python 0.1 tương đương (AC01-1).
- **Engine chỉ đổi hai điểm nhỏ**, đều tắt mặc định: (1) `EventLog` cho phép đăng ký listener; (2) vòng lặp sự kiện
  gọi bộ thu metric theo thời gian tại các mốc chu kỳ. Khi tắt, đường chạy giống 0.1 từng lệnh.
- **Lưu trữ**: spec lưu dạng JSON trong cột `spec_json`, cộng các bảng liên kết cần cho toàn vẹn tham chiếu (fleet ↔
  loại xe, policy group ↔ phiên bản policy). Event log lưu ra **file** (CSV nén gzip, Parquet nếu có `pyarrow`),
  DB chỉ giữ đường dẫn.
- **Benchmark** chạy mỗi case trong một tiến trình con để đo RAM đỉnh riêng từng case, xuất JSON, có chế độ so sánh
  với kết quả mốc để phát hiện thoái lui > 10%.

## 2. Quyết định kỹ thuật

| # | Quyết định | Phương án đã cân nhắc | Lý do chọn |
|---|---|---|---|
| D1 | **DB: SQLite qua `sqlite3` của thư viện chuẩn**, SQL viết tay, lớp `Repository` che toàn bộ truy cập | (a) SQLAlchemy Core + Alembic (sẵn sàng PostgreSQL); (b) ORM đầy đủ; (c) chỉ file JSON | Không thêm phụ thuộc; RUN-1 chỉ cho 1 run/lần nên SQLite đủ; mọi truy cập qua `Repository` nên đổi sang PostgreSQL/SQLAlchemy ở Sprint 08 chỉ chạm một gói. Câu hỏi mở Q-A |
| D2 | **Migration**: file `kami/store/migrations/NNNN_<tên>.sql` + bảng `schema_migrations`; áp theo thứ tự, mỗi file trong một transaction; chạy lại bỏ qua file đã áp | Alembic | Đủ cho SQLite, idempotent (AC01-5), không phụ thuộc |
| D3 | **Spec bằng `dataclass` + bộ kiểm tra tự viết**, lỗi gom thành `SpecError` chứa danh sách `(đường dẫn trường, thông báo)`, ví dụ `policy_group.members[0].policy.params.wait_treshold: tham số không tồn tại (có: wait_threshold, surcharge, …)` | pydantic; JSON Schema + `jsonschema` | Lõi không được thêm phụ thuộc; dataclass hợp với code 0.1. JSON Schema cho form UI sinh ở Sprint 07 (`params_schema`) |
| D4 | **Kiểm tra tham số policy bằng introspection** chữ ký `__init__` của lớp trong `POLICIES` (tên tham số, kiểu suy từ giá trị mặc định); `matching` và `batch_window` là tham số chung | Khai báo schema thủ công cho từng policy | Không trùng lặp; manifest/`params_schema` đầy đủ là việc của Sprint 07 |
| D5 | **Policy group → policy**: 0 thành viên bật → `Baseline()`; 1 thành viên → chính policy đó (không bọc `Composite`, để giống hệt 0.1); ≥ 2 → `Composite(*members)` theo thứ tự | Luôn dùng `Composite` | Bọc `Composite` một thành viên đổi `describe()` và có rủi ro lệch thứ tự hook |
| D6 | **Fleet ở Sprint 01**: tổng số xe các fleet thay cho `n_drivers` của kịch bản; xe thứ `i` (theo thứ tự sinh của kịch bản) gán vào slot `L[floor(i·len(L)/n)]` của danh sách mở rộng `(fleet, loại xe)`; `capacity` = `seats` của loại xe; `fleet_id`, `vehicle_type` ghi vào `DriverSpec.attrs` **sau khi** sinh (không đổi rút ngẫu nhiên). `supply_multiplier` của preset vẫn áp như 0.1 | Mỗi fleet sinh xe riêng | Giữ nguyên dòng ngẫu nhiên của `ScenarioBuilder` → spec không có fleet, hoặc 1 fleet 1 loại xe 4 chỗ, cho kết quả giống hệt 0.1. Sprint 05 sẽ thay bằng phân bố ban đầu/ca theo fleet. Câu hỏi mở Q-B |
| D7 | **Bộ thu metric theo thời gian không tạo sự kiện mới**: vòng lặp kiểm tra `ev.time >= next_sample` trước khi xử lý sự kiện và chụp nhanh tại mốc `t_start + k·Δ`. Snapshot = trạng thái sau mọi sự kiện có thời điểm `< mốc` | Thêm sự kiện `METRIC_SAMPLE` vào hàng đợi | Không đổi `events_processed`, không đổi số thứ tự `seq`, không ảnh hưởng điều kiện dừng → metric giống hệt khi bật/tắt |
| D8 | Bộ thu nhận dữ liệu qua **listener của `EventLog`** (gọi cả khi `record_events=False`), đọc thêm trạng thái tài xế trực tiếp lúc chụp | Quét lại toàn bộ rider mỗi mốc | O(sự kiện) thay vì O(rider × số mốc); vẫn chạy được khi Sprint 04 chuyển event log sang ghi dần ra file |
| D9 | **Event log của run lưu ra file** `runs/<run_id>/events.csv.gz` (stdlib); `events.parquet` khi có `pyarrow` và spec yêu cầu; bảng `run_artifact` giữ đường dẫn, định dạng, kích thước, sha256 | Lưu event log trong DB | Event log một ngày GreenSM có thể hàng chục triệu dòng (rủi ro đã nêu trong sprint). Câu hỏi mở Q-C |
| D10 | **Snapshot run = RunSpec đã "giải tham chiếu"**: mọi tham chiếu DB (`{"ref": id}`) được thay bằng nội dung đầy đủ, kèm id + số phiên bản policy đã dùng, rồi lưu vào `run.run_spec_json` | Lưu chỉ id tham chiếu | NFR-4: chạy lại từ snapshot không cần dữ liệu khác còn tồn tại |
| D11 | **Benchmark case = file RunSpec** trong `benchmarks/specs/*.json`; mỗi case chạy trong tiến trình con (`multiprocessing`, `spawn`), đo wall-clock (median của N lần), sự kiện/giây, RAM đỉnh (`resource.getrusage(...).ru_maxrss` của tiến trình con) | `tracemalloc` | `tracemalloc` làm chậm 2–3 lần và chỉ đo heap Python; `ru_maxrss` theo tiến trình con là RAM thật mỗi case |
| D12 | Chỉ hỗ trợ **JSON** cho file spec | YAML | YAML cần thêm phụ thuộc |

### Câu hỏi mở cần người dùng chốt

- **Q-A (DB)**: đồng ý SQLite stdlib cho 0.2 (đổi sang PostgreSQL sau nếu cần, qua `Repository`)? Hay muốn
  SQLAlchemy + Alembic ngay từ đầu (thêm phụ thuộc tuỳ chọn `kami[store]`)? *Đề xuất: SQLite stdlib.*
- **Q-B (fleet)**: đồng ý quy tắc D6 (fleet quyết định số xe; `supply_multiplier` của preset vẫn nhân lên số xe)?
- **Q-C (event log)**: mặc định `csv.gz` (không phụ thuộc) hay Parquet (cần `pyarrow`)? *Đề xuất: `csv.gz`, Parquet
  tuỳ chọn.*
- **Q-D (môi trường benchmark mốc)**: FleetPy không còn là phụ thuộc (mạng đường đã port vào `kami/network/road/`),
  nên case `example_network` chạy được ở mọi môi trường; chỉ router C++ cần build riêng cho từng interpreter. Hai
  interpreter cho số liệu khác nhau nên mốc phải cố định **một** môi trường (phiên bản Python + router C++ đã build hay
  chưa). *Đề xuất: env `conda` hiện có (Python 3.10, đã build router C++); ghi rõ trong file kết quả.*

## 3. Thay đổi theo module

| Module | Thay đổi | Interface công khai |
|---|---|---|
| `kami/config/__init__.py` | Mới. Xuất các spec, `load_run_spec`, `build_run`, `SpecError` | Mới |
| `kami/config/specs.py` | Mới. Dataclass: `ScenarioSpec` (+ `NetworkSpec`, `ZoneSpec`, `TrafficSpec`, `SourceSpec` các loại `preset`/`synthetic`/`fleetpy_demand`/`csv`, `IncidentSpec`, thời tiết), `RunSpec`, `FleetSpec` (+ `FleetComposition`), `VehicleTypeSpec`, `ChargingStationSpec`, `PolicySpec`, `PolicyGroupSpec` (+ `PolicyGroupMember`), `BehaviorSpec`, `SimConfigSpec`, `OutputSpec`; `Ref` (tham chiếu DB) | Mới |
| `kami/config/validate.py` | Mới. Tiện ích kiểm tra kiểu/khoảng/enum, gom lỗi theo đường dẫn trường | Mới |
| `kami/config/build.py` | Mới. `build_world`, `build_scenario`, `build_policy`, `build_behavior`, `build_sim_config`, `build_run(spec) → BuiltRun(scenario, policy, behavior, config, crn_seed)`, `run_spec(spec) → Simulation` | Mới |
| `kami/config/legacy.py` | Mới. `spec_from_cli(preset, policy, args, network…)` → `RunSpec` tương đương tham số CLI 0.1; dùng cho lệnh `kami spec` và test AC01-2 | Mới |
| `kami/timeseries.py` | Mới. `MetricSampler` (S01-6) | Mới |
| `kami/eventlog.py` | Thêm `EventLog.subscribe(fn)`; `add()` gọi listener kể cả khi `enabled=False`. Thêm `to_csv(..., compress=True)` cho `.csv.gz` | Bổ sung, tương thích ngược |
| `kami/core/engine.py` | `SimConfig.timeseries_interval_s: Optional[float] = None`; nếu khác `None`, `Simulation` tạo `self.timeseries = MetricSampler(...)` và vòng lặp chụp tại mốc; chụp mốc cuối sau `_finalise` | Bổ sung, mặc định tắt |
| `kami/store/__init__.py` | Mới. **Không** được import từ `kami/__init__.py` hay lõi | Mới |
| `kami/store/db.py` | Mới. `connect(path)` (bật `foreign_keys`, WAL), `migrate(conn)`, `current_version(conn)` | Mới |
| `kami/store/migrations/0001_initial.sql` | Mới. Bảng ở S01-4 | — |
| `kami/store/repository.py` | Mới. `Repository`: `save_/get_/list_/delete_` cho `vehicle_type`, `fleet`, `charging_station`, `policy` (+ `add_policy_version`), `policy_group`, `scenario`; `resolve(run_spec)` (giải `Ref`); `create_run`, `finish_run`, `get_run`, `run_metrics`, `run_timeseries`, `run_artifacts` | Mới |
| `kami/store/runs.py` | Mới. `execute(run_spec, repo, artifacts_dir) → run_id`: giải tham chiếu → snapshot → tạo run `running` → chạy → ghi metric, chuỗi thời gian, event log → `succeeded`/`failed` | Mới |
| `kami/bench.py` | Mới. Chạy suite, xuất JSON, so sánh với mốc | Mới |
| `kami/cli.py` | `run --spec FILE [--db PATH] [--artifacts DIR] [--out DIR]`; lệnh mới `spec` (xuất RunSpec từ tham số CLI 0.1), `db init` (tạo/migrate), `bench [--suite DIR] [--repeat N] [--out FILE] [--compare FILE]`. Lệnh và cờ cũ giữ nguyên; `--spec` dùng cùng cờ cũ thì báo lỗi rõ ràng | Bổ sung |
| `benchmarks/specs/*.json` | Mới. Các case benchmark (mục S01-8) | — |
| `examples/specs/*.json`, `examples/05_run_from_spec.py` | Mới. Spec mẫu (preset, fleet, policy group nhiều thành viên) và ví dụ dùng thư viện + DB | — |
| `docs/engine/18-config-persistence.md` | Mới (S01-9); cập nhật `02-engine.md` (`timeseries_interval_s`), `13-eventlog.md` (listener, csv.gz), `15-cli.md`, `README.md` của `docs/engine` | — |

## 4. Kế hoạch theo hạng mục

Thứ tự thực hiện: S01-1 → S01-2 → S01-3 → S01-6 → S01-4/S01-5 → S01-7 → S01-8 → S01-9. Mỗi bước kết thúc bằng test pass.

### S01-1 — Schema cấu hình khai báo

1. `validate.py`: `SpecError(errors: list[(path, msg)])`; hàm `req`, `opt`, `typed`, `in_range`, `one_of`, `list_of`
   ghi lỗi theo đường dẫn, gom hết lỗi rồi mới ném (người dùng thấy mọi trường sai một lần).
2. `specs.py`: mỗi spec là `@dataclass` với `from_dict(d, path="")`, `to_dict()`; trường lạ bị từ chối
   ("trường không tồn tại"). `schema_version: int = 1` ở `RunSpec`, `ScenarioSpec`; đọc phiên bản lớn hơn bản hỗ trợ
   → lỗi rõ ràng.
3. Nội dung tối thiểu:
   - `ScenarioSpec`: `name`, `network` (`grid`: `width_m`, `height_m`, `spacing_m`, `speed_kmh` | `road`: `name`
     hoặc đường dẫn, `dynamics_file`, `backend`), `zones` (`square`: `cell_m` | `h3`: `resolution` | `file`: `name`), `traffic`
     (tham số `TrafficLayer`), `source` (`preset`: `preset`, `demand_per_hour`, `overrides` | `synthetic`: đúng các
     tham số của `ScenarioBuilder.synthetic` gồm khung giờ, profile, thời tiết, sự cố | `fleetpy_demand` | `csv`),
     `n_drivers` (dùng khi run không khai báo fleet), `seed` (mặc định, `RunSpec.seed` ghi đè).
   - `VehicleTypeSpec`: `name`, `group` (`bike`/`car`), `seats`, `range_km`. `ChargingStationSpec`: `name`, vị trí
     (`lon`/`lat` hoặc `node`), `ports`, `power_kw`. (Sprint 05 mở rộng.)
   - `FleetSpec`: `name`, `composition: [{vehicle_type: <tên>, count}]`.
   - `PolicySpec`: `plugin` (khoá trong `POLICIES`), `params`, `version` (tuỳ chọn). `PolicyGroupSpec`: `name`,
     `members: [{policy: PolicySpec | Ref, enabled}]`.
   - `BehaviorSpec`: `preset` (`default`/`employed_drivers`), `registry` + `slots` (như cờ `--registry`), `models`
     (`{slot: {class, params}}`, chỉ class trong `kami.behavior.models`).
   - `SimConfigSpec`: các trường của `SimConfig` + `fare` (`FareModel`) + `pooling` (`PoolingParams`); thêm
     `timeseries_interval_s` (mặc định 300).
   - `RunSpec`: `name`, `scenario` (spec hoặc `Ref`), `vehicle_types`, `fleets`, `charging_stations`, `policy_group`,
     `behavior`, `sim_config`, `seed`, `crn_seed`, `outputs` (`event_log`: `csv.gz`/`parquet`/`none`).
4. Kiểm tra chéo: loại xe được fleet tham chiếu phải tồn tại; `count > 0`; tên plugin tồn tại; tham số policy theo D4;
   khung giờ `t_start < t_end`; preset tồn tại.

### S01-2 — Bộ dựng từ cấu hình

1. `build_world(scenario_spec)` → `(network, zones)` giống `cli._world`; cache theo spec mạng trong tiến trình
   (mạng đường thật nạp lâu).
2. `build_scenario`: gọi đúng hàm `ScenarioBuilder` tương ứng `source`; áp fleet theo D6.
3. `build_policy` theo D4, D5; `MatchingParams` dựng từ `params.matching`.
4. `build_behavior`, `build_sim_config`; `build_run` trả `BuiltRun`; `run_spec(spec)` chạy và trả `Simulation`.
5. `legacy.spec_from_cli(...)` sinh RunSpec cho mọi tổ hợp preset × policy của CLI 0.1.

### S01-3 — CLI chạy từ file cấu hình

1. `python -m kami run --spec run.json`: in giống lệnh `run` hiện tại (scenario summary, policy, metric); `--out`
   ghi `metrics.json`, `events.csv`, thêm `timeseries.json` và `run_spec.resolved.json`.
2. `--db kami.db` (+ `--artifacts runs/`): ghi run vào DB qua `kami.store.runs.execute` và in `run_id`.
3. `python -m kami spec --preset rain --policy surge --arg every=60 > run.json` để chuyển cách gọi cũ sang spec.
4. `python -m kami db init --db kami.db`.

### S01-4 / S01-5 — Lưu trữ & repository

1. `0001_initial.sql`: `vehicle_type`, `fleet`, `fleet_vehicle(fleet_id, vehicle_type_id, count)`,
   `charging_station`, `policy(id, name, plugin, source_kind)`, `policy_version(policy_id, version, params_json,
   params_schema_json NULL, source_code NULL)` — bất biến, `policy_group`, `policy_group_member(group_id, position,
   policy_version_id, params_json, enabled)`, `scenario`, `run`, `run_metric_summary(run_id, name, value)`,
   `run_metric_timeseries(run_id, t, name, value)`, `run_artifact(run_id, kind, path, format, size_bytes, sha256)`.
   Bảng thực thể có `id`, `name` (unique), `spec_json`, `created_at`, `updated_at`, `deleted_at` (xoá mềm, phục vụ
   S08-2).
2. `Repository` chỉ nhận/trả **spec** (không nhận object engine); `save_*` kiểm tra hợp lệ trước khi ghi.
3. Kiểm tra NFR-5: test chạy `python -c "import kami; ..."` trong tiến trình con rồi khẳng định `kami.store` và
   `sqlite3` không có trong `sys.modules`; thêm test tĩnh rằng không file nào dưới `kami/` (trừ `kami/store/`,
   `kami/cli.py`, `kami/bench.py`) import `kami.store`/`sqlite3`.

### S01-6 — Bộ thu metric theo thời gian

1. `MetricSampler(sim, interval_s)`: đăng ký listener `EventLog`; giữ bộ đếm tích luỹ và theo cửa sổ.
2. Mỗi mốc ghi một dòng: `t`; `rider.requests`, `rider.booked`, `rider.completed`, `rider.cancelled` (cửa sổ và tích
   luỹ); `rider.waiting_now`; `rider.wait_mean`, `rider.wait_p90` (phút, của các lượt đón trong cửa sổ);
   `driver.online`, `driver.idle`, `driver.repositioning` (IDLE đang có leg), `driver.en_route`, `driver.on_trip`;
   `driver.utilization_now`; `platform.gmv` tích luỹ; `platform.surge_mean`.
3. `sim.timeseries.rows` (list dict) và `to_json/to_csv`.
4. Engine: hai thay đổi nêu ở mục 3, mặc định tắt (`SimConfig`), bộ dựng spec mặc định bật 300 s.

### S01-7 — Lưu một lần chạy

`runs.execute`: `repo.resolve(spec)` → snapshot (D10) kèm `kami.__version__`, `schema_version` → `create_run`
(`running`, `started_at`) → `run_spec` → ghi `run_metric_summary` (từ `sim.metrics()`, NaN lưu `NULL`),
`run_metric_timeseries`, file event log + `run_artifact` → `finish_run(succeeded, wall_s, events)`. Ngoại lệ →
`failed` + thông báo lỗi, không để treo `running`.

### S01-8 — Benchmark harness

1. Suite mặc định `benchmarks/specs/`:
   - `grid_am_peak_baseline` — lưới 8 km, preset `weekday_am_peak`, 200 req/h, 150 xe, `baseline`;
   - `grid_am_peak_pool` — như trên với `pool_after_wait`;
   - `grid_pm_peak_x5` — lưới 12 km, 1.000 req/h, 600 xe, policy group `surge` + `heatmap_reposition` (đo matching/
     tick ở quy mô lớn hơn);
   - `road_example_400` — `example_network`, replay `example_400.csv`, 25 xe; ghi rõ backend router (C++/Python)
     trong kết quả.
2. `python -m kami bench --repeat 3 --out benchmarks/results/<ngày>.json`: mỗi case một tiến trình con; ghi
   `wall_s` (median, min, max), `events`, `events_per_s`, `peak_rss_mb`, metric chính (để phát hiện thay đổi kết quả),
   môi trường (Python, OS, CPU, commit git, phiên bản kami).
3. `--compare <mốc.json>`: in bảng % thay đổi, đánh dấu case chậm hơn > 10% hoặc RAM tăng > 10%, mã thoát ≠ 0 nếu có.
4. Thư mục `benchmarks/results/` được commit để làm mốc lịch sử.

### S01-9 — Tài liệu

`docs/engine/18-config-persistence.md`: định dạng từng spec (bảng trường, đơn vị, mặc định), quy tắc fleet → xe, policy
group → policy, sơ đồ bảng DB, vòng đời run, định dạng event log, cách chạy benchmark và đọc kết quả. Cập nhật các file
nêu ở mục 3.

## 5. Kiểm chứng acceptance criteria

| AC | Cách kiểm chứng |
|---|---|
| AC01-1 | `tests/test_config_build.py::test_spec_equals_python_api`: dựng cùng kịch bản/policy/seed bằng API 0.1 và bằng `RunSpec` JSON, so `metrics()` từng khoá (NaN = NaN) và số sự kiện. Thêm test qua CLI (`main(["run", "--spec", f, "--out", d])`) so `metrics.json` với API |
| AC01-2 | `test_all_presets_and_policies`: với mọi preset trong `PRESETS` × mọi policy trong `POLICIES`, `spec_from_cli` → JSON → `run_spec` (kịch bản thu nhỏ để test nhanh) cho metric giống hệt API 0.1. `examples/specs/` có ít nhất một file cho mỗi preset |
| AC01-3 | `tests/test_config_specs.py`: thiếu trường, sai kiểu, ngoài khoảng, trường lạ, plugin không tồn tại, tham số policy sai tên (có gợi ý tên đúng), loại xe không tồn tại; khẳng định đường dẫn trường trong `SpecError` |
| AC01-4 | `tests/test_store.py::test_round_trip_*`: với mỗi loại thực thể `save` → `get` → `==` spec gốc; thêm round-trip `to_dict`/`from_dict` cho mọi spec |
| AC01-5 | `test_migrate_empty_and_idempotent`: DB rỗng → `migrate` → đủ bảng; `migrate` lần hai không lỗi, `schema_migrations` không đổi |
| AC01-6 | `test_execute_records_run`: chạy một RunSpec nhỏ qua `runs.execute` → bản ghi `run` `succeeded` có snapshot giải tham chiếu, metric tổng hợp bằng `sim.metrics()`, chuỗi thời gian có số mốc đúng, file event log tồn tại và đọc lại được đúng số dòng. Test riêng cho nhánh `failed` |
| AC01-7 | Test tiến trình con nêu ở S01-4/S01-5; chạy `python examples/01_quickstart.py` trong test hoặc lệnh kiểm chứng cuối sprint |
| AC01-8 | `tests/test_bench.py` chạy suite một case nhỏ, kiểm tra cấu trúc JSON. Cuối sprint chạy suite đầy đủ trong môi trường chốt ở Q-D, ghi kết quả vào `docs/backlog/sprint-01-backlog.md` |
| AC01-9 | `python -m unittest discover -s tests -t .` (cả Python hệ thống và env có router C++); test mới: `test_config_specs.py`, `test_config_build.py`, `test_timeseries.py`, `test_store.py`, `test_cli_spec.py`, `test_bench.py`, `test_isolation.py` |

Bổ sung (không phải AC nhưng bảo vệ NFR-1): `test_timeseries.py::test_sampler_does_not_change_results` — metric và
`events_processed` khi bật bộ thu bằng khi tắt; tổng `rider.completed` theo cửa sổ bằng `platform.trips` cuối cùng
trên kịch bản không có warm-up.

## 6. Mock & phần dự kiến chưa làm

Không dùng mock. Những phần **có schema/lưu được nhưng engine chưa dùng** (sẽ ghi vào backlog):

- `VehicleTypeSpec.range_km`, `group` và `ChargingStationSpec`: lưu và kiểm tra hợp lệ, engine bỏ qua đến Sprint 05.
- Fleet chưa có phân bố ban đầu/ca riêng (D6) — Sprint 05.
- `policy_version.params_schema_json` và `source_code` để trống (plugin built-in) — Sprint 07.
- Chưa hỗ trợ PostgreSQL (nếu Q-A chọn SQLite) — xem lại ở Sprint 08.
- Benchmark chưa có case quy mô GreenSM (`hanoi_greensm_day` thuộc Sprint 04).

## 7. Rủi ro & phương án dự phòng

| Rủi ro | Dự phòng |
|---|---|
| Kết quả qua spec lệch API 0.1 vì khác thứ tự dựng object (ví dụ `Composite` một thành viên, thứ tự tham số) | D5; test AC01-1/AC01-2 phủ mọi preset × policy; so cả `events_processed` |
| Bộ thu metric làm chậm engine | Mặc định tắt trong `SimConfig`; benchmark chạy với cấu hình như spec (bật 300 s) và ghi riêng chi phí bật/tắt trên một case |
| Đo RAM bằng `ru_maxrss` khác đơn vị giữa Linux (KB) và macOS (byte) | Chuẩn hoá theo `sys.platform` |
| Spec ràng buộc quá chặt với tham số `ScenarioBuilder` hiện tại, Sprint 02 đổi kịch bản Hà Nội | `schema_version` + hàm nâng cấp spec cũ; source mới (ví dụ `hanoi`) thêm vào được mà không phá source cũ |
| Mạng FleetPy nạp chậm khi chạy nhiều spec | Cache world theo spec mạng trong tiến trình |

## 8. Lịch sử thay đổi

| Ngày | Thay đổi |
|---|---|
| 2026-10-07 | Tạo plan, trạng thái Chờ duyệt |
| 2026-10-07 | Cập nhật sau khi port mạng đường FleetPy vào `kami/network/road/` (việc ngoài sprint): Q-D, spec mạng `road`/zone `file`, case benchmark `road_example_400` |
