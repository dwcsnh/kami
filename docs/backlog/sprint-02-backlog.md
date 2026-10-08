# Backlog sau Sprint 02 — Bản đồ Hà Nội & giao thông giờ cao điểm

| | |
|---|---|
| Sprint | [sprint-02-hanoi-network-traffic.md](../sprint/sprint-02-hanoi-network-traffic.md) |
| Plan | [sprint-02-plan.md](../implementation-plan/sprint-02-plan.md) |
| Ngày kết thúc | 2026-10-07 |

Mục backlog đầu vào đã xử lý: **B01-9** (spec cho tắc đường zone × giờ, nguồn demand Hà Nội — `traffic.congestion`,
`traffic.vehicle_groups`, source `zonal`, sự cố theo lon/lat, `outputs.trajectories`; docs/engine/18).

## Trạng thái acceptance criteria

| AC | Kết quả | Bằng chứng / ghi chú |
|---|---|---|
| AC02-1 | Đạt | `python -m kami.osm build hanoi` từ `vietnam-261006.osm.pbf` (sha256 `121ba51a…795b`, ghi trong `data/osm/hanoi.json` và `manifest.json`; sai sha256 → từ chối build). `tests/test_osm_pipeline.py::test_ac02_1_rebuild_is_identical_and_readable`: build fixture hai lần → mọi file mạng + zone giống hệt từng byte, đọc được bằng `RoadNetwork` và `FleetPyNetwork` |
| AC02-2 | **Một phần** | 100% node của mạng nằm trong thành phần liên thông mạnh của đồ thị ô tô ∪ xe máy (pipeline giữ SCC lớn nhất). Nhưng `location_nodes()` — node **mọi** nhóm xe tới được — là 26.845/28.983 = **92,6%** (< 95%): 7% node là ngõ chỉ xe máy đi được (`motorcar=no` + `motorcycle=yes`, dữ liệu OSM đúng). SCC riêng: xe máy 99,5%, ô tô 93,1%. Xem B02-1 |
| AC02-3 | Đạt | `test_ac02_3_every_node_one_zone` (fixture) và `TestHanoiNetwork` (mạng thật): mọi node đúng một zone, mọi zone ≥ 1 node. `hanoi_h3_r8`: 452 ô H3 r8; `hanoi_wards`: 60 phường/xã sau sắp xếp 2025. Số zone và phạm vi ghi ở docs/engine/19 và 08 |
| AC02-4 | Đạt | `tests/test_congestion.py`: `test_ac02_4_peaks_slower_than_night` (lưới: 8h và 18h > 1,5 × 23h, tỷ lệ đúng profile), `test_ac02_4_and_5_on_fixture` (fixture, backend Python + C++), `TestCongestionHanoi::test_ac02_4_inner_city_od` (Văn Miếu → Hồ Gươm trên mạng thật) |
| AC02-5 | Đạt | `test_ac02_5_zones_differ_in_the_same_hour`: ba nhóm `core`/`inner`/`outer` cùng giờ có hệ số khác nhau; OD 2 km trong `core` chậm hơn tỷ lệ > 1,2 lần so với OD cùng độ dài ở `outer`. Thêm hệ số theo file `zone,hour,factor` (`test_zone_hour_file`) |
| AC02-6 | Đạt | `tests/test_trajectory.py`: với mọi xe, mọi cặp node liên tiếp là một cạnh (lưới và fixture có tắc đường, sự cố, nhóm xe), thời gian không giảm trong và giữa các chặng, chặng kế tiếp bắt đầu ở node chặng trước kết thúc; điểm cuối chặng đón/trả trùng `t_pickup`/`t_dropoff` (sai số 1e-6) và sự kiện `PICKUP`/`DROPOFF` của log (log làm tròn 3 chữ số). Bật/tắt ghi quỹ đạo cho cùng metric và cùng event log (`test_recording_does_not_change_results`, `test_neutral_on_roads`) |
| AC02-7 | Đạt | `tests/test_vehicle_groups.py`: travel time xe máy / ô tô = 1 / `speed_factor` trên cùng lộ trình không cấm (lưới + fixture, cả hai backend); lộ trình của mỗi nhóm không chứa cạnh cấm của nhóm đó (cạnh `motorcycle=no` giả lập + ngõ `motorcar=no` thật của fixture), trong khi nhóm kia có dùng các cạnh này |
| AC02-8 | Đạt | `python -m kami run --spec scenarios/hanoi/am_peak.json --out out/hanoi`: **15.180 request, 1.500 xe** (1.000 ô tô + 500 xe máy), 105.834 sự kiện, `wall_s` 125 s (tổng 135 s), RAM đỉnh 966 MB; ghi `metrics.json`, `events.parquet`, `trajectories.parquet` (32.963 chặng, 55 MB). `test_ac02_8_am_peak_size` kiểm tra quy mô khi mạng đã build |
| AC02-9 | Đạt | `python -m kami bench --repeat 5 --compare benchmarks/results/2026-10-07-sprint01.json`: 5 case cũ có `events` và metric **giống hệt** mốc (không có cờ `results changed`), thời gian −5,8%…+2,9%. Toàn bộ test cũ pass (`test_config_build`, `test_store`, `test_road_network`… không sửa) |

Test: `python -m unittest discover -s tests -t .` — **162 test pass** trên env `fleetpy` (Python 3.10, 0 skip) và
trên Python 3.14 hệ thống (20 skip: thiếu pyosmium/h3/router C++). Test mới: `test_osm_pipeline`, `test_congestion`,
`test_vehicle_groups`, `test_trajectory`, `test_zonal`.

## Mục còn mở

| Mã | Loại | Mức độ | Mô tả | Lý do chưa làm | Sprint dự kiến xử lý | Trạng thái |
|---|---|---|---|---|---|---|
| B02-1 | AC một phần | Cao | AC02-2: `location_nodes` = 92,6% (< 95%) vì ngõ chỉ xe máy đi được bị loại khỏi điểm đón/trả chung. Hướng xử lý cần người dùng chốt: (a) chấp nhận định nghĩa "≥ 95% node trong SCC của mạng" (đang 100%) và giữ location chung 92,6%; (b) location theo nhóm xe — khách trong ngõ chỉ xe máy đón được (matching đã loại cặp không có đường), xe ô tô không xuất phát/đi rảnh vào ngõ; (c) bỏ ngõ chỉ xe máy khỏi mạng (mất dữ liệu thật) | Đổi AC hoặc mở rộng phạm vi cần người dùng đồng ý | 05 (loại dịch vụ / nhóm xe) hoặc theo quyết định | Mở |
| B02-2 | Ý tưởng | Cao | Profile tắc đường, bảng tốc độ free-flow, `speed_factor`/`congestion_scale` xe máy và trọng số demand theo zone là **giả định**, chưa hiệu chỉnh. Cần GPS / dữ liệu chuyến của GreenSM: tốc độ theo zone × giờ → file `zone,hour,factor` (`congestion.kind = "file"` đã hỗ trợ) | Chưa có dữ liệu (requirements Q4) | Khi có dữ liệu | Mở |
| B02-3 | Nợ kỹ thuật | Cao | Thông lượng trên mạng Hà Nội ≈ 850 sự kiện/s (bị chặn bởi Dijkstra: 1→1 ≈ 1,9 ms, X→1 ≈ 1,8 ms; `_quote_eta` gọi 3 truy vấn 1→1 mỗi request). `am_peak` (15k request) 125 s; `weekday` (≈100k request, 8.000 xe) chưa chạy đầy đủ | Ngoài phạm vi (Sprint 04) | 04 | Mở |
| B02-4 | Nợ kỹ thuật | Cao | Kết quả của nguồn `fleetpy_demand`/`csv` phụ thuộc **đường dẫn tuyệt đối** của file: RNG seed bằng `f"fleetpy|{demand_csv}|{seed}"`. Cùng spec chạy ở thư mục repo khác cho kết quả khác (`road_example_400`: 3.895 so với 3.901 sự kiện) — vi phạm NFR-1. Sửa (seed theo tên file hoặc sha256) sẽ đổi kết quả mốc | Có từ 0.1; sửa cần đặt lại mốc benchmark | 04 | Mở |
| B02-5 | Nợ kỹ thuật | Thấp | `_environment_change` (thời tiết, sự cố — code 0.1) khởi động lại ngay cả chặng **chưa xuất phát** (đang cho khách lên xe), làm mất thời gian `boarding_s`. `CONGESTION_UPDATE` đã xử lý đúng (giữ giờ xuất phát) | Sửa sẽ đổi kết quả preset `accident`/`rain` của 0.1 (AC02-9) | 04 (cùng lúc đặt lại mốc) | Mở |
| B02-6 | Chờ phụ thuộc | Cao | Khách chưa chọn loại dịch vụ (ô tô / xe máy): thời gian chuyến trực tiếp và cước tính theo ô tô; matching cho mọi nhóm xe phục vụ mọi khách (xe máy 1 chỗ chở được khách đặt ô tô) | Loại dịch vụ thuộc Sprint 05/06 | 05 | Mở |
| B02-7 | Nợ kỹ thuật | Thấp | Travel time của một chặng tính theo trạng thái lúc xuất phát (không tích phân qua các chu kỳ tắc đường); chỉ tính lại ở `CONGESTION_UPDATE` khi lệch > `retime_threshold`. Chưa có hạn chế rẽ, thời gian chờ đèn | Đủ cho mô hình theo giờ; FleetPy cũng vậy | Chưa xếp | Mở |
| B02-8 | Nợ kỹ thuật | Thấp | `network_dynamics_file` (travel time động theo thư mục của FleetPy) chỉ áp cho nhóm xe mặc định và không kết hợp với `congestion` (tắc đường nhân trên travel time của `edges.csv`) | Hà Nội dùng tắc đường sinh trong bộ nhớ; chưa có dữ liệu dynamics | Chưa xếp | Mở |
| B02-9 | Nợ kỹ thuật | Cao | `trajectories.parquet` của `am_peak` 55 MB (32.963 chặng, polyline mở rộng theo hình học cạnh); cả ngày ước ~400 MB. Visualizer có thể cần lọc theo vùng/xe, giảm điểm, hoặc ghi dần | Sprint 03 quyết định định dạng fixture cho visualizer | 03 (fixture), 04 (ghi dần) | **Một phần (Sprint 03)**: fixture visualizer dùng `kami.replay` v1 theo khu vực + giản lược điểm (1,14 MB); ghi dần / quy mô cả ngày chuyển B03-2 (Sprint 04) |
| B02-10 | Nợ kỹ thuật | Thấp | Hệ zone phường bị cắt ở biên polygon: 60 zone gồm cả phần nhỏ của xã ngoài vùng (ví dụ "Xã Đông Anh", "Xã Bát Tràng") | Polygon xấp xỉ 12 quận cũ, không theo ranh giới phường mới | Khi mở rộng phạm vi (Q-A) | Mở |
| B02-11 | Nợ kỹ thuật | Thấp | Mốc benchmark Sprint 02 đo trên working tree chưa commit (`git_dirty: true`, commit gốc `d100a3f`) | Sprint chưa được commit tại thời điểm đo | 03 (đo lại sau commit) | **Xong (Sprint 03)**: đo lại trên `0e4e0d0` sạch → [`2026-10-08-sprint02-clean.json`](../../benchmarks/results/2026-10-08-sprint02-clean.json), xem "Số liệu mốc" |
| B02-12 | Nợ kỹ thuật | Thấp | Pipeline cần `pyosmium` (đã cài vào env `fleetpy`, Python 3.10); chưa kiểm tra wheel cho Python 3.14. Runtime không cần | Chỉ là công cụ build | Chưa xếp | Mở |

## Mock đang dùng

Không có mock trong code. Phần **giả định** (không phải mock): xem B02-2; đánh dấu "giả định" trong docs/engine/08,
09, 19.

## Số liệu mốc

Môi trường mốc như Sprint 01: env conda `fleetpy` — CPython 3.10.21, router C++ đã build (thêm
`setEdgeTravelTimes`), có `scipy`; AMD Ryzen 9 6900HS (16 luồng), Linux 7.0, commit `d100a3f` + working tree Sprint
02 (B02-11). Lệnh: `python -m kami bench --repeat 5`. File:
[`benchmarks/results/2026-10-07-sprint02.json`](../../benchmarks/results/2026-10-07-sprint02.json).

| Case | wall_s median (min–max) | build_s | Sự kiện | Sự kiện/s | RAM đỉnh (MB) | Backend | So với mốc 01 |
|---|---|---|---|---|---|---|---|
| `grid_am_peak_baseline` | 0,618 (0,601–0,644) | 0,01 | 8.375 | 13.555 | 77 | grid | −5,8% |
| `grid_am_peak_baseline_nots` | 0,621 (0,609–0,705) | 0,01 | 8.375 | 13.482 | 77 | grid | +1,2% |
| `grid_am_peak_surge` | 0,669 (0,658–0,741) | 0,01 | 8.456 | 12.632 | 77 | grid | +2,9% |
| `grid_pm_peak_x5` | 2,621 (2,579–2,661) | 0,06 | 26.170 | 9.986 | 97 | grid | −0,7% |
| `road_example_400` | 0,736 (0,709–0,858) | 0,25 | 3.901 | 5.299 | 87 | cpp | −0,1% |
| `hanoi_am_peak_small` (mới) | 9,192 (9,160–9,447) | 0,95 | 7.578 | 824 | 211 | cpp | — |

`hanoi_am_peak_small`: mạng `hanoi`, H3 r8, tắc đường zone × giờ, `zonal` 7h–8h (1.141 request), 200 ô tô + 100 xe
máy: 793 chuyến, hoàn thành 0,875, chờ TB 6,47 phút, utilization 0,616, GMV 61.818.000 VND. Case tự bỏ qua khi mạng
chưa build.

Metric vận hành của 5 case cũ giống hệt mốc Sprint 01 (cờ `deterministic`).

**Đo lại trên commit sạch (B02-11, 2026-10-08):** commit `0e4e0d0`, `git_dirty: false`, cùng môi trường, `--repeat 5`
→ [`2026-10-08-sprint02-clean.json`](../../benchmarks/results/2026-10-08-sprint02-clean.json) — **mốc so sánh cho
Sprint 03**. Sự kiện và metric giống hệt bảng trên; wall_s median: `grid_am_peak_baseline` 0,62 · `_nots` 0,60 ·
`_surge` 0,60 · `grid_pm_peak_x5` 2,57 · `road_example_400` 0,70 · `hanoi_am_peak_small` 9,18 (−10,4%…+0,8% so với
bảng trên). Ghi chú: chạy bench từ một bản checkout ở **thư mục khác** cho `road_example_400` 3.905 sự kiện (thay vì
3.901) — tái hiện B02-4; mốc phải đo trong thư mục repo.

**Preset nghiệm thu `scenarios/hanoi/am_peak.json`** (seed 0, chạy một lần qua CLI):

| Request | Xe | Sự kiện | wall_s | RAM đỉnh | Chuyến | Hoàn thành | Chờ TB / p90 (phút) | Utilization | Chuyến/xe-giờ | GMV (VND) |
|---|---|---|---|---|---|---|---|---|---|---|
| 15.180 | 1.500 | 105.834 | 125,2 | 966 MB | 10.980 | 0,899 | 4,90 / 11,29 | 0,531 | 1,93 | 864.312.900 |

**Mạng Hà Nội** (`python -m kami.osm check hanoi`): 28.983 node, 70.186 cạnh; nạp C++ 0,95 s; 1→1 C++ 1,90 ms
(p95 4,51 ms), X→1 (900 s) 1,84 ms, Python 1→1 27,2 ms; 100% cặp có đường; lộ trình C++ = Python 200/200. Build
mạng: 95 s, 1,6 GB RAM.
