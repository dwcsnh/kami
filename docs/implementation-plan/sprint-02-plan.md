# Implementation plan — Sprint 02: Bản đồ Hà Nội & giao thông giờ cao điểm

| | |
|---|---|
| Sprint | [sprint-02-hanoi-network-traffic.md](../sprint/sprint-02-hanoi-network-traffic.md) |
| Backlog đầu vào | [sprint-01-backlog.md](../backlog/sprint-01-backlog.md) — xử lý trong plan này: **B01-9** (spec kịch bản cho tắc đường zone × giờ, nguồn demand Hà Nội). Các mục khác của backlog 01 thuộc sprint 04/05/07/08. Mốc benchmark: `benchmarks/results/2026-10-07-sprint01.json` |
| Trạng thái | Đã thực hiện (duyệt 2026-10-07) |

## 1. Tóm tắt hướng tiếp cận

Sprint chia làm bốn khối, mỗi khối tắt mặc định để kịch bản 0.1/Sprint 01 cho kết quả **không đổi** (AC02-9):

```
 (A) dữ liệu — chạy một lần, ngoài engine                       (B) engine — đọc dữ liệu đã dựng
 ┌──────────────────────────────────────────────┐            ┌───────────────────────────────────────────┐
 │ python -m kami.osm build hanoi               │            │ RoadNetwork("hanoi")  + edge_attributes   │
 │  PBF Geofabrik (ghim ngày, sha256)           │──CSV──────▶│ FileZoneSystem("hanoi_h3_r8"/"hanoi_wards")│
 │  → cắt theo polygon → lọc loại đường         │            │ TrafficLayer + CongestionModel (zone×giờ) │
 │  → đơn giản hoá → SCC → UTM 48N              │            │   → đặt lại travel time từng cạnh mỗi chu kỳ│
 │  → nodes/edges.csv, edge_attributes.csv,     │            │   → một router / nhóm xe (car, bike)       │
 │    edge_geometry.csv, zones, demand weights  │            │ CONGESTION_UPDATE → tính lại chặng đang chạy│
 │  → manifest.json (phiên bản dữ liệu, số liệu)│            │ TrajectoryRecorder → trajectories.parquet  │
 └──────────────────────────────────────────────┘            └───────────────────────────────────────────┘
 (C) kịch bản Hà Nội: nguồn demand `zonal` (theo zone × giờ) + spec preset `scenarios/hanoi/*.json`
 (D) tài liệu + test (fixture OSM nhỏ commit trong repo để test pipeline mà không cần mạng)
```

- **Tắc đường zone × giờ** thay hệ số giờ chung: hệ số nhân travel time của **từng cạnh** =
  `1 + (P_g(h) − 1) × s_class × s_vehicle`, với `g` = nhóm tắc của zone chứa cạnh, `P_g` profile 24 giờ của nhóm,
  `s_class` theo loại đường, `s_vehicle` theo nhóm xe. Mỗi đầu chu kỳ (mặc định mỗi giờ) engine đặt lại travel time
  cạnh vào router — đúng cơ chế travel time động của FleetPy (`edges_td_att.csv`), chỉ khác là sinh trong bộ nhớ thay
  vì đọc file.
- **Nhóm xe**: mỗi nhóm (`car`, `bike`) có router riêng (travel time riêng, cạnh cấm riêng). Không khai báo fleet
  → mọi xe là `car` như hiện nay.
- **Quỹ đạo**: khi bật `SimConfig.record_trajectories`, mỗi chặng lưu chuỗi node của lộ trình thực đi và thời điểm
  qua từng node; xuất `(lon, lat, t)` cho visualizer Sprint 03.

## 2. Quyết định kỹ thuật

| # | Quyết định | Phương án đã cân nhắc | Lý do chọn |
|---|---|---|---|
| D1 | **Nguồn OSM: file PBF Vietnam của Geofabrik có ghi ngày** (`vietnam-YYMMDD.osm.pbf`, ~330 MB), ghi URL + sha256 vào `data/osm/hanoi.json`; đọc bằng `pyosmium` (phụ thuộc build tuỳ chọn `kami[osm]`). File PBF cache ở `data/osm/cache/` (không commit) | (a) Overpass API với `[date:…]` ghim ngày, không cần thư viện; (b) OSMnx | Đã thử Overpass trong lúc lập plan: truy vấn vùng Hà Nội trả 504/HTML lỗi ở nhiều lần gọi — không đủ tin cậy cho "một lệnh tạo lại". PBF có ngày + sha256 là đầu vào bất biến, chạy offline sau lần tải đầu. OSMnx kéo theo geopandas/networkx và tự đơn giản hoá theo quy tắc riêng, khó kiểm soát định dạng FleetPy. Câu hỏi mở Q-B |
| D2 | **Phạm vi**: polygon trong repo (`data/osm/hanoi_area.geojson`) bao vùng đô thị trung tâm cũ (12 quận nội thành cũ ≈ lon 105,72–105,93, lat 20,93–21,10, ~450 km²). Polygon là tham số của pipeline nên đổi phạm vi không cần sửa code | Toàn thành phố (~3.300 km²) | Đủ cho nhu cầu gọi xe chính; mạng ~10⁵ node, vừa sức router C++ và Sprint 04. Câu hỏi mở Q-A |
| D3 | **Loại đường giữ**: `motorway, trunk, primary, secondary, tertiary` (+ `_link`), `unclassified, residential, living_street`. Bỏ `service` (~40.000 way trong vùng), `track`, `path`, `footway`, `cycleway`, `construction`, đường riêng (`access=private/no`) | Giữ cả `service` (ngõ) | `service` gấp đôi số way, phần lớn là lối vào toà nhà/bãi xe; ngõ dân cư lớn ở Hà Nội đa phần gắn `residential`. Câu hỏi mở Q-E |
| D4 | **Đơn giản hoá đồ thị**: giữ node giao cắt, đầu mút, điểm đổi thuộc tính; gộp chuỗi node bậc 2 thành một cạnh; **hình học đầy đủ** của cạnh lưu riêng ở `base/edge_geometry.csv` (polyline lon/lat) để vẽ quỹ đạo theo đường cong thật. Chiều đi theo `oneway` (kể cả `-1`, `junction=roundabout`); giữ thành phần liên thông mạnh lớn nhất của đồ thị ô tô ∪ xe máy | Không đơn giản hoá (giữ mọi node OSM) | Giảm số node ~3–5 lần → router nhanh hơn; quỹ đạo vẫn nằm trên cạnh (AC02-6) và vẽ đúng hình dạng đường |
| D5 | **Toạ độ**: chiếu sang UTM 48N (`EPSG:32648`) bằng `pyproj` lúc build, ghi `crs.info` | Tự viết công thức UTM | `pyproj` đã là phụ thuộc tuỳ chọn (`geo`); runtime vẫn chỉ cần thư viện chuẩn (`lonlat()` mới cần pyproj, như hiện nay) |
| D6 | **Travel time free-flow** = độ dài / tốc độ; tốc độ lấy `maxspeed` nếu có, nếu không theo bảng mặc định của loại đường (ô tô nội đô: trunk 50, primary 40, secondary 35, tertiary 30, residential 20 km/h…). Ghi bảng vào `manifest.json` và tài liệu như **giả định** | Tốc độ giới hạn pháp lý | Tốc độ giới hạn quá cao so với thực tế nội đô; chưa có GPS để hiệu chỉnh (rủi ro đã nêu trong sprint) |
| D7 | **Thuộc tính theo nhóm xe** trong file riêng `base/edge_attributes.csv` (`from_node,to_node,road_class,allow_car,allow_bike,…`), **không** thêm cột vào `edges.csv` | Thêm cột vào `edges.csv` | Giữ định dạng FleetPy nguyên vẹn; mạng FleetPy cũ và `example_network` không có file này → mặc định mọi cạnh cho mọi nhóm. Cấm xe máy lấy từ `motorcycle=no` (OSM Hà Nội có ~357 way: cao tốc, Vành đai 3 trên cao, một số cầu); cấm ô tô từ `motorcar=no`/`motor_vehicle=no` |
| D8 | **Zone**: pipeline sinh hai hệ zone dạng `node_zone_info.csv` đọc bằng `FileZoneSystem` (runtime không cần `h3`): `hanoi_h3_r8` (H3 độ phân giải 8, cạnh ~460 m, dự kiến ~600 zone) dùng cho surge/tắc đường/sự cố, và `hanoi_wards` (phường **sau sắp xếp 2025** — OSM đã cập nhật, ví dụ "Phường Hoàn Kiếm", "Phường Cửa Nam" ở `admin_level=6`) dùng cho báo cáo. Mỗi node thuộc đúng một zone (node ngoài mọi polygon → zone gần nhất) | Chỉ một hệ zone; zone vuông | H3 đều, ổn định trước thay đổi hành chính; phường cho báo cáo theo đơn vị quen thuộc. Câu hỏi mở Q-D |
| D9 | **Mô hình tắc đường** `CongestionModel` (mới, `kami/congestion.py`): profile 24 giờ theo **nhóm zone** (`core`, `inner`, `outer` — mặc định gán theo khoảng cách tới tâm Hoàn Kiếm 0–3 / 3–8 / > 8 km, hoặc file `zone,group`), hệ số theo loại đường và theo nhóm xe; hoặc đọc thẳng file `zone,hour,factor` (khi có GPS). Profile mặc định Hà Nội: đỉnh 7–9h và 16h30–19h; nhân tối đa ~2,2 ở `core`, xe máy chịu ~50% mức tắc của ô tô. **Giả định**, ghi rõ trong tài liệu | Hệ số theo node qua `node_factor` (như sự cố hiện nay) | `node_factor` chỉ chạy với router Python (chậm 12–15×); đặt lại travel time cạnh chạy được với router C++ và giữ nguyên thuật toán Dijkstra. Với `GridNetwork` (không có cạnh) dùng `node_factor` để test nhanh |
| D10 | **Áp tắc đường vào router**: thêm vào wrapper Cython `setEdgeTravelTimes(from, to, tt)` (vector, không qua file tạm) và `RoadNetwork.set_edge_travel_times(group, times)`; router "live" (sự cố) được đặt lại cùng lúc = tắc × sự cố. Nền tảng (`estimate`) **thấy** tắc đường thường ngày (dữ liệu lịch sử) nhưng mặc định **không thấy** sự cố, giữ "plan vs reality" | Ghi file `edges_td_att.csv` rồi `updateEdgeTravelTimes` | Ghi/đọc CSV ~300k cạnh mỗi giờ × 2 nhóm × 2 router tốn vài giây và đĩa tạm. `updateEdgeTravelTimes(file)` vẫn giữ cho `network_dynamics_file` cũ |
| D11 | Khi bật mô hình tắc, `hour_profile` toàn thành phố của `TrafficLayer` coi như 1 (tránh nhân hai lần); `weather_factor` vẫn nhân chung | Bỏ `hour_profile` | Tương thích: không cấu hình `congestion` thì `hour_profile` chạy như cũ |
| D12 | **Sự kiện mới `CONGESTION_UPDATE`** tại các mốc `k × period_s` (mặc định 3600 s, căn theo giờ đồng hồ), **chỉ đẩy vào hàng đợi khi có `congestion`** → kịch bản cũ không đổi `seq`/tie-break. Xử lý: đặt travel time mới, xoá cache, rồi với mỗi xe đang chạy tính lại thời gian còn lại; nếu lệch > `retime_threshold` (mặc định 10%) thì cắt chặng tại node hiện tại và đi tiếp theo đường mới (dùng lại `_interrupt_leg`/`_start_next_leg`); hazard huỷ của khách được tích phân lại như khi đổi thời tiết | Tính lại mọi chặng; không tính lại | Ngưỡng tránh tính lại hàng nghìn chặng gần như không đổi (S02-5 "thay đổi đáng kể") |
| D13 | **Nhóm xe trong engine**: `Driver.attrs["vehicle_group"]` (từ `VehicleTypeSpec.group` qua fleet, mặc định `car`). `TrafficLayer.travel/estimate/path/many_to_one` nhận thêm `group=` (mặc định `car`); matching chạy `many_to_one` theo từng nhóm. Thời gian chuyến trực tiếp để tính cước của khách dùng nhóm `car` (khách chưa chọn loại dịch vụ — Sprint 05/06) | Một router, cạnh cấm bằng chi phí vô cùng trong hàm cost | Router riêng cho nhóm giữ được tốc độ C++; bộ nhớ ~2 × 2 router chấp nhận được ở ~10⁵ node (đo ở S02-2) |
| D14 | **Quỹ đạo**: `SimConfig.record_trajectories` (mặc định tắt). Khi bật, lộ trình của chặng được tính **lúc xuất phát** (cùng trạng thái router với travel time của chặng); lúc chặng kết thúc (đủ hoặc bị cắt giữa chừng) ghi một bản ghi `(driver_id, leg_seq, purpose, occupied, rider_id, nodes[], times[])`, thời điểm qua node nội suy theo travel time tích luỹ của cạnh, cắt ở vị trí thực tế khi chặng bị ngắt. Xuất `trajectories.parquet` (một dòng mỗi chặng, kèm `lon[]`, `lat[]`); API `sim.trajectories.of(driver_id) → [(lon, lat, t)]`. Run lưu DB thêm artifact `trajectories` | Ghi từng điểm vào event log | Event log sẽ phình gấp hàng chục lần; visualizer (deck.gl `TripsLayer`) cần đúng dạng mảng điểm + thời điểm theo chuyến |
| D15 | **Demand Hà Nội**: nguồn kịch bản mới `zonal` (`ScenarioBuilder.zonal`): điểm đón rút theo trọng số zone × giờ, điểm đến theo mô hình trọng lực (trọng số zone đích × `exp(−khoảng cách/λ)`), node trong zone rút đều; trọng số zone mặc định do pipeline tính từ mật độ POI/toà nhà OSM trong mỗi zone H3 (`zone_weights.csv`, có cột sáng/chiều để phân biệt nhà ở và văn phòng). Rút ngẫu nhiên bằng `random.Random(f"zonal|…")` như các nguồn kịch bản khác | Dùng lại hotspot của `synthetic` | Hotspot ngẫu nhiên không phản ánh không gian Hà Nội; trọng số từ OSM là xấp xỉ hợp lý khi chưa có dữ liệu chuyến thật (requirements Q4) |
| D16 | **Preset Hà Nội** là file ScenarioSpec trong `scenarios/hanoi/` (`weekday.json` cả ngày, `am_peak.json`, `pm_peak_rain.json`, `incident_arterial.json` — sự cố trên một trục chính định vị bằng lon/lat), chạy bằng `run --spec` hoặc tham chiếu từ RunSpec; `python -m kami presets` liệt kê thêm chúng | Thêm vào dict `PRESETS` của 0.1 | `PRESETS` chỉ mô tả tham số synthetic trên mạng bất kỳ; preset Hà Nội gắn với mạng/zone/demand riêng → hợp với spec của Sprint 01 |
| D17 | **Spec (B01-9)**: thêm trường tuỳ chọn, giữ `schema_version = 1` (file cũ vẫn hợp lệ, nghĩa không đổi): `TrafficSpec.congestion`, `TrafficSpec.vehicle_groups`, `SimConfig.record_trajectories`, `retime_threshold`, source `zonal`, `IncidentSpec.at` nhận `{"lon", "lat"}`, `outputs.trajectories` | Tăng `schema_version` lên 2 | Chỉ thêm trường có mặc định; không có tài liệu cũ nào đổi nghĩa |
| D18 | **Dữ liệu sinh ra không commit** (`data/networks/hanoi/`, `data/zones/hanoi_*`, `data/osm/cache/` vào `.gitignore`); commit cấu hình build (`data/osm/hanoi.json`, polygon) và **một fixture OSM nhỏ** (~1 km² quanh Hồ Gươm, < 1 MB, dạng `.osm.pbf`) để test pipeline offline. Test cần mạng Hà Nội đầy đủ tự `skip` khi chưa build | Commit mạng CSV (~30–50 MB); Git LFS | Repo gọn; mạng tái tạo được bằng một lệnh từ PBF có sha256. Câu hỏi mở Q-C |

### Câu hỏi mở cần người dùng chốt

- **Q-A (phạm vi)**: đồng ý vùng đô thị trung tâm cũ (~450 km², 12 quận cũ) cho Sprint 02? Hay cần thêm vùng ven (Gia
  Lâm, Đông Anh, Thanh Trì…) hoặc toàn thành phố? *Đề xuất: vùng trung tâm; polygon là tham số nên mở rộng sau
  được.*
- **Q-B (nguồn OSM)**: đồng ý PBF Geofabrik có ghi ngày + `pyosmium` (phụ thuộc build tuỳ chọn)? *Đề xuất: có.*
  Lưu ý Geofabrik không giữ file theo ngày mãi mãi: tái tạo đúng từng byte cần giữ file PBF đã cache (sha256 ghi
  trong `data/osm/hanoi.json`).
- **Q-C (lưu dữ liệu)**: không commit mạng Hà Nội (tái tạo bằng lệnh) — hay commit CSV (~30–50 MB) / dùng Git LFS?
  *Đề xuất: không commit, kèm fixture nhỏ cho test.*
- **Q-D (zone)**: H3 r8 cho tắc đường/surge + phường mới (sau sắp xếp 2025) cho báo cáo? *Đề xuất: cả hai; mặc định
  kịch bản dùng H3 r8.*
- **Q-E (loại đường)**: bỏ `service` như D3? Ảnh hưởng: xe máy không đi được ngõ gắn `service`. *Đề xuất: bỏ.*
- **Q-F (quy mô preset)**: AC02-8 cần ≥ 10.000 request và ≥ 1.000 xe. *Đề xuất:* `am_peak` (6h–10h, ~15.000 request,
  1.500 xe) là preset nghiệm thu; `weekday` (cả ngày, ~100.000 request, 8.000 xe) có sẵn nhưng chỉ chạy đầy đủ từ
  Sprint 04.

## 3. Thay đổi theo module

| Module | Thay đổi | Interface công khai |
|---|---|---|
| `kami/osm/__init__.py`, `__main__.py` | Mới. `python -m kami.osm build <cấu hình>` (`hanoi` = `data/osm/hanoi.json`), `python -m kami.osm fetch`, `python -m kami.osm check <mạng>` (S02-2). Chỉ import `osmium`/`pyproj`/`h3` bên trong lệnh | Mới (công cụ build) |
| `kami/osm/extract.py` | Đọc PBF trong polygon, lọc loại đường/`access`, gom tag cần thiết | Mới |
| `kami/osm/graph.py` | Dựng đồ thị có hướng, đơn giản hoá (D4), SCC, tốc độ (D6), thuộc tính nhóm xe (D7), chiếu toạ độ | Mới |
| `kami/osm/zones.py` | Gán node → H3 r8, node → phường (point-in-polygon thuần Python), trọng số zone từ POI | Mới |
| `kami/osm/writer.py` | Ghi `base/{nodes,edges,edge_attributes,edge_geometry}.csv`, `crs.info`, `manifest.json`, `data/zones/<tên>/hanoi/node_zone_info.csv`, `data/zones/<tên>/hanoi/zone_weights.csv` | Mới |
| `data/osm/hanoi.json`, `data/osm/hanoi_area.geojson`, `tests/data/osm/hoan_kiem.osm.pbf` | Cấu hình build, polygon, fixture | — |
| `kami/network/road/cpp/_router.pyx` (+ `Network.cpp/.h`) | Thêm `setEdgeTravelTimes(from[], to[], tt[])` | Bổ sung |
| `kami/network/road/graph.py` | Đọc tuỳ chọn `edge_attributes.csv`, `edge_geometry.csv`; `edge_list()`; lưu travel time free-flow gốc | Bổ sung |
| `kami/network/road/network.py` | Router theo nhóm xe (`groups`), `set_edge_travel_times(group, times)`, tham số `group` cho `base_travel`/`many_to_one`/`path`/live; `edge_geometry(a, b)` | Bổ sung, mặc định `car` = hành vi cũ |
| `kami/network/base.py`, `grid.py` | Tham số `group` (bỏ qua với lưới, trừ hệ số tốc độ) | Bổ sung |
| `kami/congestion.py` | Mới. `CongestionModel` (D9), profile mặc định Hà Nội, đọc file `zone,hour,factor` | Mới |
| `kami/traffic.py` | Nhận `congestion`, `vehicle_groups`; `apply_period(t)`; tham số `group` cho mọi truy vấn; D11 | Bổ sung |
| `kami/core/events.py` | `CONGESTION_UPDATE` | Bổ sung |
| `kami/core/engine.py` | Lên lịch/xử lý `CONGESTION_UPDATE` (D12); truyền nhóm xe của tài xế vào truy vấn traffic; ghi quỹ đạo (D14) | Bổ sung, mặc định tắt |
| `kami/matching.py` | `many_to_one` theo nhóm xe | Nội bộ |
| `kami/trajectory.py` | Mới. `TrajectoryRecorder`, `save/load` Parquet, `of(driver_id)` | Mới |
| `kami/scenario.py` | `ScenarioBuilder.zonal(...)` (D15); sự cố định vị bằng lon/lat | Bổ sung |
| `kami/config/specs.py`, `build.py` | Trường mới (D17); fleet ghi `attrs["vehicle_group"]`; dựng `CongestionModel` | Bổ sung |
| `kami/store/runs.py`, `kami/cli.py` | Artifact `trajectories`; `--out` ghi `trajectories.parquet`; `presets` liệt kê `scenarios/hanoi/` | Bổ sung |
| `scenarios/hanoi/*.json` | Mới (D16) | — |
| `benchmarks/specs/hanoi_am_peak_small.json` | Mới, chỉ chạy khi đã build mạng (bị bỏ qua và ghi chú nếu thiếu) | — |
| `docs/engine/08`, `09`, `16`, `02`, `03`, `13`, `18`; `docs/engine/19-osm-pipeline.md` (mới) | Tài liệu S02-9 | — |

## 4. Kế hoạch theo hạng mục

Thứ tự: S02-1 → S02-2 → S02-3 → S02-7 (router theo nhóm) → S02-4 → S02-5 → S02-6 → S02-8 → S02-9. Mỗi bước kết thúc
bằng test pass và kiểm tra AC02-9 (benchmark Sprint 01 cho số sự kiện/metric không đổi).

### S02-1 — Pipeline OSM → mạng FleetPy

1. `data/osm/hanoi.json`: URL PBF có ngày, sha256, polygon, danh sách loại đường, bảng tốc độ, CRS đích, tên mạng/zone.
2. `fetch`: tải PBF vào `data/osm/cache/` nếu chưa có, kiểm sha256 (sai → dừng, báo rõ).
3. `extract`: duyệt PBF bằng `pyosmium` một lượt (way lọc theo tag, node trong polygon + node của way được giữ).
4. `graph`: tách way thành cạnh có hướng; đơn giản hoá (D4); SCC lớn nhất; đánh lại `node_index` 0..N−1 theo thứ
   tự ổn định (theo id OSM) để kết quả tất định.
5. `writer`: ghi file; `manifest.json` gồm phiên bản dữ liệu (ngày PBF, sha256, phiên bản pipeline), số node/cạnh,
   tỷ lệ node trong SCC, bảng tốc độ đã dùng, thời điểm build.
6. Chạy hai lần liên tiếp → file đầu ra giống hệt (sha256) — test trên fixture.

### S02-2 — Router C++ trên mạng Hà Nội

`python -m kami.osm check hanoi`: nạp mạng bằng cả hai backend, 1.000 cặp OD ngẫu nhiên (seed cố định): thời gian
truy vấn trung bình 1→1 và X→1 (bán kính 900 s), tỷ lệ cặp có đường, so lộ trình hai backend (phải trùng). Ghi số
liệu vào `docs/engine/19-osm-pipeline.md` và backlog.

### S02-3 — Zone Hà Nội

1. H3 r8: `h3.latlng_to_cell` cho mỗi node lúc build.
2. Phường: polygon `boundary=administrative` có tên trong vùng (multipolygon ghép từ way); point-in-polygon; node
   rơi ngoài → zone của node gần nhất có zone.
3. `zone_weights.csv` (D15). Test: mỗi node đúng một zone, mọi zone có ≥ 1 node.

### S02-7 — Nhóm xe trên mạng

1. `edge_attributes.csv` + router theo nhóm: cạnh cấm của nhóm được đặt travel time rất lớn (`1e7` s) trong router
   của nhóm và kết quả ≥ `1e6` coi như không có đường (dùng fallback như cặp không liên thông); kiểm tra lộ trình
   không chứa cạnh cấm.
2. `vehicle_groups` trong `TrafficSpec`: `{"bike": {"speed_factor": 0.9, "congestion_scale": 0.5}}` (free-flow xe
   máy chậm hơn, ít chịu tắc hơn — giả định).
3. Fleet → `attrs["vehicle_group"]` = `VehicleTypeSpec.group`.

### S02-4 — Mô hình tắc đường zone × giờ

1. `CongestionModel.multipliers(period, group) → {edge: factor}` theo D9; cache theo (giờ, nhóm).
2. `CongestionSpec`: `kind` (`zone_group` | `file`), `period_s` (3600), `groups` (`{tên: [24 hệ số]}`),
   `zone_group` (`ring` với tâm lon/lat + bán kính | `file`), `road_class_scale`, `file`.
3. Áp lên `GridNetwork` bằng `node_factor` (test nhanh, AC02-4/5 trên lưới) và lên `RoadNetwork` bằng D10.

### S02-5 — Cập nhật travel time theo mốc và tính lại chặng

`CONGESTION_UPDATE` theo D12; `RoadNetwork.update_network` (file dynamics cũ) vẫn chạy qua `TRAFFIC_UPDATE` như cũ.
Ghi log `CONGESTION_UPDATE` (giờ, số chặng được tính lại).

### S02-6 — Lộ trình và quỹ đạo

`TrajectoryRecorder` theo D14; `_leg_position` dùng chung lộ trình đã lưu; xuất Parquet; `of(driver_id)` nối các
chặng thành một chuỗi `(lon, lat, t)`, nội suy theo `edge_geometry` khi có.

### S02-8 — Preset Hà Nội

`ScenarioBuilder.zonal`; bốn file `scenarios/hanoi/*.json` (D16); sự cố `incident_arterial` trên trục Nguyễn Trãi –
Khuất Duy Tiến lúc 17h30–18h30 (vị trí lon/lat, chọn node gần nhất); `pm_peak_rain` dùng thời tiết `rain`.

### S02-9 — Tài liệu

`docs/engine/19-osm-pipeline.md` (pipeline, nguồn dữ liệu, giấy phép ODbL, giả định tốc độ, số liệu mạng/zone); cập
nhật 08 (tắc zone × giờ, nhóm xe, router theo nhóm), 09 (nguồn `zonal`, preset Hà Nội), 16 (phần mở rộng định dạng
FleetPy), 02/03 (`CONGESTION_UPDATE`, `record_trajectories`), 13/18 (artifact quỹ đạo, trường spec mới).

## 5. Kiểm chứng acceptance criteria

| AC | Cách kiểm chứng |
|---|---|
| AC02-1 | `tests/test_osm_pipeline.py`: build fixture Hồ Gươm hai lần → file giống hệt, đọc được bằng `RoadNetwork` và `FleetPyNetwork`; `manifest.json` có sha256 nguồn. Cuối sprint: `python -m kami.osm build hanoi` trên PBF thật, ghi lệnh + sha256 vào backlog |
| AC02-2 | Test fixture: `len(location_nodes()) / num_nodes() ≥ 0,95`; mạng thật: số liệu trong `manifest.json` (test tự skip nếu chưa build) |
| AC02-3 | Test: mọi node có đúng một zone ở cả `hanoi_h3_r8` và `hanoi_wards` (fixture + mạng thật); số zone/phạm vi ghi trong docs/engine/19 |
| AC02-4 | `tests/test_congestion.py`: cùng OD nội thành, `travel(…, 8h)` và `travel(…, 18h)` > `travel(…, 23h)` × (1 + ε) theo profile cấu hình — trên lưới, fixture và (skip nếu thiếu) mạng thật |
| AC02-5 | Test: hai zone khác nhóm cùng giờ có hệ số khác nhau; OD trong `core` chậm hơn tỷ lệ so với OD cùng độ dài ở `outer` |
| AC02-6 | `tests/test_trajectory.py`: với mọi xe, mỗi cặp node liên tiếp là một cạnh của mạng, thời gian không giảm; điểm cuối chặng đón/trả trùng `t` của `PICKUP`/`DROPOFF` trong event log (sai số 1e-6) |
| AC02-7 | Test: cùng OD, `travel(group="bike")` / `travel(group="car")` bằng hệ số cấu hình (trên đường không cấm); lộ trình `bike` không chứa cạnh `allow_bike = false` (fixture có cạnh cấm giả lập + mạng thật nếu có) |
| AC02-8 | Lệnh `python -m kami run --spec scenarios/hanoi/am_peak.json --out out/hanoi` chạy xong; kiểm tra `rider.requests ≥ 10.000`, số xe ≥ 1.000; ghi thời gian chạy vào backlog (chưa có mục tiêu) |
| AC02-9 | Toàn bộ test cũ; `test_config_build`/`test_store` giữ nguyên; `python -m kami bench --compare benchmarks/results/2026-10-07-sprint01.json` cho `events` và metric **giống hệt** mốc (cờ `results changed` không xuất hiện) và thời gian không thoái lui > 10% |

## 6. Mock & phần dự kiến chưa làm

Không dùng mock trong code. Những phần là **giả định** (ghi rõ trong tài liệu, đưa vào backlog):

- Profile tắc đường, bảng tốc độ free-flow, hệ số xe máy, trọng số demand theo zone: giả định hợp lý, chưa hiệu chỉnh
  bằng GPS/dữ liệu chuyến của GreenSM.
- Khách chưa chọn loại dịch vụ (ô tô / xe máy); cước dùng thời gian ô tô — Sprint 05/06.
- Chưa tối ưu thời gian chạy ở 100k request (Sprint 04); preset `weekday` cả ngày có thể rất chậm ở sprint này.
- Chưa có hạn chế rẽ (turn restriction) và thời gian chờ đèn ở nút giao.

## 7. Rủi ro & phương án dự phòng

| Rủi ro | Dự phòng |
|---|---|
| Mạng lớn hơn dự kiến → router/bộ nhớ chậm (4 router C++) | Đo ở S02-2 trước khi làm S02-4; nếu quá lớn: bỏ `living_street`/`unclassified` ngoài vành đai 2, hoặc chỉ tạo router riêng cho nhóm khi có cạnh cấm |
| Đặt lại ~300k travel time mỗi giờ chậm ở Python | Tính hệ số theo (zone group × class) rồi map một lần sang mảng cạnh; truyền vector vào C++; đo trong S02-4 |
| Tính lại hàng nghìn chặng ở mốc tắc đường | Ngưỡng `retime_threshold`; chỉ xét chặng còn > 60 s |
| Preset ≥ 10k request chạy quá lâu trên Python engine | Chưa có mục tiêu thời gian ở sprint này; ghi số liệu cho Sprint 04; nếu > 1 giờ thì rút khung giờ preset nghiệm thu |
| Dữ liệu OSM Hà Nội thiếu `maxspeed`, `oneway` sai | Bảng tốc độ mặc định; thống kê tỷ lệ cạnh có `maxspeed` trong manifest |
| Ranh giới phường trên OSM chưa đầy đủ sau sắp xếp 2025 | H3 là hệ zone mặc định; phường thiếu → báo trong manifest, node gán zone gần nhất |
| `pyosmium` không có wheel cho Python mới | Pipeline chạy trong env `fleetpy` (3.10); runtime không cần `pyosmium` |
| Đổi chữ ký truy vấn traffic (`group=`) làm lệch kết quả cũ | Mặc định `car` đi đúng nhánh cũ; AC02-9 so benchmark từng sự kiện |

## 8. Lịch sử thay đổi

| Ngày | Thay đổi |
|---|---|
| 2026-10-07 | Tạo plan, trạng thái Chờ duyệt. Khảo sát lúc lập plan: Overpass API trả lỗi 504/HTML với truy vấn vùng Hà Nội; Geofabrik có `vietnam-261006.osm.pbf` (~330 MB); OSM đã có phường mới ở `admin_level=6`; ~357 way có `motorcycle=no`; ~40.000 way `service` và ~20.000 way `residential/unclassified/living_street` trong bbox dự kiến |
| 2026-10-07 | Người dùng duyệt plan (đồng ý mọi đề xuất của Q-A…Q-F); trạng thái Đã duyệt, sprint Đang làm |
| 2026-10-07 | Lệch nhỏ khi implement: (1) D6 — `maxspeed` chỉ dùng khi **thấp hơn** bảng tốc độ mặc định (là giới hạn pháp lý; dùng thẳng sẽ làm 18,6% cạnh có tag nhanh hơn đường cùng loại không tag). (2) D16 — preset Hà Nội là file **RunSpec** (kèm fleet ô tô + xe máy) để chạy thẳng bằng `run --spec`; `presets` liệt kê `scenarios/*/*.json`. (3) D14 — lộ trình ghi vào quỹ đạo là `leg.path` mà engine dùng để định vị xe (chưa tính thì tính lúc chặng kết thúc) thay vì luôn tính lúc xuất phát: bật/tắt ghi quỹ đạo cho **cùng kết quả** mô phỏng (có test); `CONGESTION_UPDATE` cố định lộ trình đang chạy trước khi đổi travel time. (4) Thêm `TrafficLayer.activate()` gọi ở đầu `Simulation.run()` và `RoadNetwork.reset_groups()`: network dùng chung giữa các run (cache `build_world`) nay có trạng thái (travel time theo nhóm/tắc đường). (5) `bench` bỏ qua case có mạng đường chưa build (ghi `skipped`). (6) Extra `kami[osm]` = osmium, pyproj, h3. (7) Số thực tế: polygon 353 km² (ước 450), mạng 28.983 node / 70.186 cạnh (ước ~10⁵ node) — nhỏ hơn dự kiến vì gộp chuỗi bậc 2 |
| 2026-10-07 | AC02-2 chỉ đạt một phần: `location_nodes` (node mọi nhóm xe tới được) = 92,6% vì 7% node là ngõ chỉ xe máy đi được (`motorcar=no`); 100% node nằm trong SCC của mạng (ô tô ∪ xe máy), SCC xe máy 99,5%, ô tô 93,1%. Không đổi AC — ghi B02-1, chờ người dùng chốt |
| 2026-10-07 | Kết thúc sprint: plan Đã thực hiện; backlog [sprint-02-backlog.md](../backlog/sprint-02-backlog.md) |
