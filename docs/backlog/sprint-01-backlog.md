# Backlog sau Sprint 01 — Nền tảng cấu hình, lưu trữ & benchmark

| | |
|---|---|
| Sprint | [sprint-01-foundation.md](../sprint/sprint-01-foundation.md) |
| Plan | [sprint-01-plan.md](../implementation-plan/sprint-01-plan.md) |
| Ngày kết thúc | 2026-10-07 |

## Trạng thái acceptance criteria

| AC | Kết quả | Bằng chứng / ghi chú |
|---|---|---|
| AC01-1 | Đạt | `tests/test_config_build.py::TestSameAsPythonApi` — `test_spec_equals_python_api` (metric, `events_processed` và toàn bộ event log giống hệt API 0.1), `test_cli_spec_equals_cli_flags` (`kami spec` + `run --spec` cho `metrics.json` giống hệt `run` với cờ 0.1), `test_composite_equals_python_api` |
| AC01-2 | Đạt | `test_all_presets_and_policies`: 8 preset × 4 policy qua JSON → metric giống hệt API 0.1. `examples/specs/preset_<tên>.json` cho đủ 8 preset (`test_example_spec_for_every_preset`) |
| AC01-3 | Đạt | `tests/test_config_specs.py::TestValidation` (14 test): thiếu trường, sai kiểu, ngoài khoảng, enum, trường lạ có gợi ý, preset/plugin không tồn tại, tham số policy sai tên (`policy_group.members[0].policy.params.wait_treshold` → gợi ý `wait_threshold`), loại xe không khai báo, model behavior sai slot; mọi lỗi báo một lần |
| AC01-4 | Đạt | `tests/test_store.py::test_round_trip_every_entity` (loại xe, fleet, trạm sạc, kịch bản, policy + phiên bản, policy group); `test_config_specs.py::TestRoundTrip` cho `to_dict`/`from_dict` của mọi spec và mọi file ví dụ |
| AC01-5 | Đạt | `test_migrate_empty_and_idempotent`: DB rỗng → đủ 14 bảng; migrate lại (cùng kết nối và sau khi mở lại) không lỗi, `schema_migrations` không đổi; `python -m kami db init` |
| AC01-6 | Đạt | `test_execute_records_run`: run `succeeded`, snapshot đã giải tham chiếu chạy lại không cần DB cho metric bằng metric đã lưu, chuỗi thời gian khớp `sim.timeseries`, file `events.parquet` đọc lại đủ số dòng, `size_bytes`/`sha256`. Nhánh `failed` và "tham chiếu sai không tạo run" có test riêng |
| AC01-7 | Đạt | `tests/test_isolation.py`: `import kami`, `examples/01_quickstart.py` và `run --spec` (không `--db`) trong tiến trình con không nạp `sqlite3`/`kami.store`; kiểm tra tĩnh không file nào ngoài `kami/store`, `cli.py`, `bench.py` import thư viện DB |
| AC01-8 | Đạt | `python -m kami bench --repeat 5 --out benchmarks/results/2026-10-07-sprint01.json`; số liệu ở mục "Số liệu mốc". `tests/test_bench.py` kiểm tra cấu trúc JSON và phát hiện thoái lui |
| AC01-9 | Đạt | `python -m unittest discover -s tests -t .`: 114 test pass trên Python 3.14 hệ thống (3 skip có sẵn: thiếu router C++/`pyproj`) và trên env `fleetpy` Python 3.10 (0 skip). Test mới: `test_config_specs`, `test_config_build`, `test_timeseries`, `test_store`, `test_cli_spec`, `test_bench`, `test_isolation`. Ví dụ 01–05 đều chạy |

## Mục còn mở

| Mã | Loại | Mức độ | Mô tả | Lý do chưa làm | Sprint dự kiến xử lý | Trạng thái |
|---|---|---|---|---|---|---|
| B01-1 | Chờ phụ thuộc | Cao | `VehicleTypeSpec.range_km`, `group` và `ChargingStationSpec` được lưu và kiểm tra nhưng engine chưa dùng | Mô hình pin/sạc thuộc Sprint 05 | 05 | Mở |
| B01-2 | Chờ phụ thuộc | Cao | Fleet chưa có phân bố ban đầu / ca làm việc riêng; xe được gán vào fleet theo quy tắc D6 sau khi kịch bản sinh | FLEET-1/2 thuộc Sprint 05 | 05 | Mở |
| B01-4 | Nợ kỹ thuật | Thấp | Chỉ hỗ trợ SQLite; chưa có PostgreSQL | Q-A chốt SQLite; mọi truy cập qua `Repository` nên đổi chỉ chạm `kami/store` | 08 (xem lại khi có backend nhiều người dùng) | Mở |
| B01-5 | Chờ phụ thuộc | Cao | Benchmark chưa có case quy mô GreenSM (`hanoi_greensm_day`, ~100k request, ~8k xe) | Cần mạng Hà Nội (Sprint 02) và tối ưu quy mô (Sprint 04) | 04 | Mở |
| B01-6 | Nợ kỹ thuật | Cao | Kết quả phụ thuộc môi trường: có `scipy` thì matching Hungarian, không có thì greedy (cùng spec + seed cho số sự kiện khác nhau giữa Python hệ thống và env `fleetpy`). Snapshot run chưa ghi solver thực dùng / môi trường | Hành vi có từ 0.1, ngoài phạm vi sprint | 04 (ghi môi trường vào run, hoặc báo lỗi khi `solver="hungarian"` mà thiếu `scipy`) | Mở |
| B01-7 | Nợ kỹ thuật | Cao | Event log vẫn giữ toàn bộ trong RAM rồi mới ghi file; chưa ghi dần ra Parquet qua listener | Cơ chế listener đã có (`EventLog.subscribe`); ghi dần cần cho quy mô thành phố | 04 | Mở |
| B01-8 | Nợ kỹ thuật | Thấp | Các case lưới ngắn (~0,6 s) nhạy nhiễu: dao động min–max ~8%, sát ngưỡng thoái lui 10% | Giữ đúng các case trong plan | 04 (thêm case dài hơn hoặc tăng `--repeat`) | Mở |
| B01-9 | Ý tưởng | Cao | Spec kịch bản chưa có trường cho tắc đường theo khu vực × giờ, lịch travel time động của mạng Hà Nội và nguồn demand Hà Nội | Thuộc MAP-3/MAP-4; spec đã có `schema_version` để mở rộng | 02 | Đã xử lý ở Sprint 02 (`traffic.congestion`, `traffic.vehicle_groups`, source `zonal` — docs/engine/18) |
| B01-10 | Nợ kỹ thuật | Thấp | Benchmark mốc đo trên working tree chưa commit (`git_dirty: true`, commit gốc `be389e0`) | Sprint chưa được commit tại thời điểm đo | 02 (đo lại sau commit nếu cần mốc gắn commit) | Đã xử lý 2026-10-07: đo lại trên commit `c013913`, số liệu mốc bên dưới đã cập nhật |

## Mock đang dùng

Không có mock.

## Số liệu mốc

Môi trường mốc (Q-D): env conda `fleetpy` — CPython 3.10.21, router C++ đã build, có `scipy`; AMD Ryzen 9 6900HS
(16 luồng), Linux 7.0, commit `c013913` (working tree sạch). Lệnh: `python -m kami bench --repeat 5`. File:
[`benchmarks/results/2026-10-07-sprint01.json`](../../benchmarks/results/2026-10-07-sprint01.json).

| Case | wall_s median (min–max) | build_s | Sự kiện | Sự kiện/s | RAM đỉnh (MB) | Backend |
|---|---|---|---|---|---|---|
| `grid_am_peak_baseline` | 0,656 (0,637–0,706) | 0,01 | 8.375 | 12.765 | 77 | grid |
| `grid_am_peak_baseline_nots` | 0,614 (0,607–0,654) | 0,01 | 8.375 | 13.649 | 77 | grid |
| `grid_am_peak_surge` | 0,651 (0,639–0,709) | 0,01 | 8.456 | 12.996 | 77 | grid |
| `grid_pm_peak_x5` | 2,641 (2,597–2,770) | 0,06 | 26.170 | 9.911 | 97 | grid |
| `road_example_400` | 0,737 (0,723–0,774) | 0,24 | 3.901 | 5.293 | 85 | cpp |

Metric vận hành chính (giống nhau ở mọi lần lặp — cờ `deterministic`):

| Case | Chuyến | Tỷ lệ hoàn thành | Chờ TB (phút) | Utilization | GMV (VND) |
|---|---|---|---|---|---|
| `grid_am_peak_baseline` | 859 | 0,946 | 4,55 | 0,588 | 55.032.300 |
| `grid_am_peak_surge` | 839 | 0,951 | 4,31 | 0,579 | 60.075.000 |
| `grid_pm_peak_x5` | 3.042 | 0,932 | 5,81 | 0,736 | 360.655.000 |
| `road_example_400` | 380 | 0,995 | 0,81 | 0,287 | 11.468.600 |

Chi phí bộ thu chuỗi thời gian (300 s): `grid_am_peak_baseline` so với `grid_am_peak_baseline_nots` chênh −1,9% ở
lần đo đầu và +6,8% ở lần đo lại — nằm trong nhiễu đo của case ngắn (giữa hai lần đo cùng code, các case dao động
±5%; xem B01-8). Sprint sau so sánh bằng
`python -m kami bench --compare benchmarks/results/2026-10-07-sprint01.json` trong cùng môi trường.
