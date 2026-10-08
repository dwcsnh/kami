# 08 · Network, zone & traffic layer

## Network (`kami/network/base.py`)

Vị trí trong kami luôn là **id node** của một `Network`. Interface:

| Hàm | Ý nghĩa |
|---|---|
| `num_nodes()`, `nodes()` | Tất cả node; zone được định nghĩa trên toàn bộ node |
| `location_nodes()` | Node dùng được làm vị trí ngẫu nhiên hoặc đích điều xe (liên thông, không phải node stop-only) |
| `coords(n)` | Toạ độ phẳng (m) |
| `lonlat(n)` | (lon, lat) nếu mạng có hệ toạ độ địa lý, ngược lại `None` |
| `base_travel(o, d, node_factor=None)` | `(giây, mét)` của đường nhanh nhất ở **free-flow**. `node_factor(n)` nhân thời gian các cạnh đi vào `n`; routing phải tránh vùng chậm |
| `many_to_one(origins, d, node_factor, max_tt)` | Nhiều điểm về một đích (dùng cho matching) |
| `path(o, d, node_factor)` | `[(node, giây_tích_luỹ)]` dọc lộ trình |
| `nearest_node(x, y)`, `bounds()`, `crow_dist(o, d)` | |

Mạng có router theo nhóm xe (`RoadNetwork`, thuộc tính `supports_groups`) nhận thêm `group=` ở `base_travel`,
`many_to_one`, `path` và các hàm "live". `GridNetwork` và mạng tự viết của 0.1 không cần tham số này: traffic layer chỉ
truyền `group` khi mạng hỗ trợ.

### `GridNetwork` (`network/grid.py`)
Thành phố lưới synthetic: `width_m × height_m`, bước `spacing_m`, vận tốc `speed_kmh`. Quãng đường là khoảng cách
Manhattan. Khi có sự cố, engine thử hai lộ trình chữ L và chọn cái nhanh hơn. Không cần dữ liệu, routing gần như
tức thời, dùng cho prototype và test.

### `RoadNetwork` (`network/road/`)
Mạng đường thật từ OSM, port từ FleetPy (nguồn gốc và kiểm chứng ở docs/engine/16). Tên cũ `FleetPyNetwork` vẫn dùng
được.

```python
net = RoadNetwork("example_network", backend="auto")   # "auto" | "cpp" | "python"
net = RoadNetwork("/path/to/networks/hanoi")            # hoặc đường dẫn thư mục mạng
```

- Đọc `<data_root>/networks/<name>/base/{nodes,edges}.csv` và `crs.info` (`data_root` mặc định là `data/` của repo
  hoặc `$KAMI_DATA_ROOT`). Chỉ cần thư viện chuẩn; `lonlat()` cần `pyproj`, trừ khi `nodes.csv` có cột `lon,lat`
  (mạng do pipeline OSM của kami tạo — docs/engine/19).
- File mở rộng tuỳ chọn (Sprint 02, định dạng ở docs/engine/16): `edge_attributes.csv` (loại đường, cạnh cấm theo nhóm
  xe), `edge_geometry.csv` (polyline của cạnh, cho quỹ đạo). Không có file thì mọi cạnh mở cho mọi nhóm xe.
- `location_nodes()` là thành phần liên thông mạnh lớn nhất, bỏ các node stop-only. Mạng ví dụ không liên thông
  mạnh hoàn toàn: có 7.140/7.617 node dùng được. Khi có cạnh cấm theo nhóm xe, `location_nodes()` là giao các thành
  phần liên thông mạnh của **từng** nhóm: mọi nhóm xe đi tới được mọi điểm đón/trả. Trên mạng Hà Nội: 26.845/28.983
  node (92,6%); phần còn lại là ngõ chỉ xe máy đi được (`motorcar=no`).
- `node_at_lonlat(lon, lat)`: location node gần một điểm WGS84 nhất. `edge_geometry(a, b)`: polyline của cạnh.
- Cặp điểm không có đường đi: dùng fallback `khoảng cách chim bay × 1,4` ở 8 m/s.
- Cache kết quả free-flow `(o, d)` (mặc định 200k cặp).
- `update_network(t)`: nạp travel time động (thư mục `<network>/<t>/edges_td_att.csv` hoặc `network_dynamics_file`)
  khi tới mốc. Engine gọi qua `TRAFFIC_UPDATE`.
- **Backend C++** (sau khi build `python -m kami.network.road.cpp.build`): nhanh hơn khoảng 12–15 lần. Sự cố được áp
  vào một **router C++ thứ hai** (trạng thái "live") qua `updateEdgeTravelTimes`. Nhờ vậy góc nhìn free-flow của nền
  tảng và trạng thái thật có sự cố cùng tồn tại mà vẫn nhanh.
- **Backend Python:** sự cố đi qua hàm chi phí của router (`travel_time × hệ số node`). Cùng kết quả, chậm hơn.

#### Router theo nhóm xe (Sprint 02, quyết định D10, D13)

Mỗi nhóm xe (`"car"`, `"bike"`) có trạng thái router riêng: bản sao travel time của đồ thị Python, router C++, cache,
router "live" cho sự cố. Nhóm `"car"` **chính là** trạng thái mặc định của 0.1 (`net.graph`, `net._cpp`); nhóm khác
được tạo khi dùng lần đầu. Cạnh nhóm không được đi có travel time `FORBIDDEN_TT = 1e7` s trong router của nhóm; kết
quả ≥ `1e6` s coi như không có đường (dùng fallback chim bay), nên lộ trình của một nhóm không bao giờ chứa cạnh cấm.

| Hàm | Ý nghĩa |
|---|---|
| `edge_list()` | Cạnh `(from, to)` theo thứ tự `edges.csv` — thứ tự của các vector bên dưới |
| `edge_road_class()`, `edge_allowed(group)` | Loại đường OSM, quyền đi của nhóm theo từng cạnh |
| `set_edge_factors(group, factors)` | Travel time cạnh của nhóm = free-flow (`edges.csv`) × `factors[i]`; `None` = free-flow. Giữ nguyên cạnh cấm và hệ số sự cố đang áp |
| `reset_groups()` | Mọi nhóm về free-flow, không sự cố (traffic layer gọi lúc bắt đầu run) |

Travel time mới được đẩy vào router C++ bằng `setEdgeTravelTimes(from[], to[], tt[])` (hàm thêm vào wrapper, không
qua file tạm); chỉ các cạnh đổi giá trị được gửi. Trên Hà Nội, đặt lại 70k cạnh cho hai nhóm mất khoảng 0,1 s.
`network_dynamics_file` cũ vẫn chạy nhưng chỉ tác động lên nhóm mặc định (file hệ số `travel_time_factor`: mọi nhóm).

## Zone (`network/zones.py`)

Zone là đơn vị không gian cho metric theo khu, surge, ma trận di chuyển và vùng sự cố. Thay cho lưới H3 trong
design doc, vì `h3` là phụ thuộc tuỳ chọn.

| Lớp | Zone id | Khi nào dùng |
|---|---|---|
| `SquareZoneSystem(net, cell_m=1000)` | `"i_j"` | Mặc định, chạy được ở mọi nơi |
| `H3ZoneSystem(net, resolution=8)` | H3 cell | Cần `pip install h3 pyproj` và mạng có lon/lat (`RoadNetwork`) |
| `FileZoneSystem(net, "example_zones")` | int | Đọc `<data_root>/zones/<name>/<network>/node_zone_info.csv` (tên cũ `FleetPyZoneSystem`) |

Zone của Hà Nội do pipeline OSM tạo sẵn dưới dạng file (runtime không cần `h3`), đọc bằng `FileZoneSystem`
(docs/engine/19):

| Hệ zone | Số zone | Dùng cho |
|---|---|---|
| `hanoi_h3_r8` | 452 ô H3 độ phân giải 8 (cạnh ≈ 460 m), 1–221 node/ô | Mặc định của kịch bản: tắc đường, surge, sự cố, demand |
| `hanoi_wards` | 60 phường/xã sau sắp xếp 2025 (OSM `admin_level=6`) | Báo cáo theo đơn vị hành chính |

Mỗi node thuộc đúng một zone ở cả hai hệ. Thư mục zone có thêm `zone_definitions.csv` (`zone_id,key,name,lon,lat`:
ô H3 / tên phường) và `zone_weights.csv` (số toà nhà ở, nơi làm việc, POI theo zone — đầu vào của nguồn demand
`zonal`).

API: `zone_of(node)`, `zones()`, `nodes_in(z)`, `location_nodes_in(z)`, `centroid_node(z)`, `neighbors(z)`
(theo khoảng cách tâm), `zones_within(node, radius_m)`.

## Traffic layer (`kami/traffic.py`)

```
thời_gian = base_network_time(tránh sự cố) × hour_profile[giờ] × weather_factor[thời_tiết]          (0.1, mặc định)
thời_gian = base_network_time(nhóm xe, tắc zone × giờ của chu kỳ hiện tại, tránh sự cố) × weather_factor  (congestion)
```

| Mức (design doc §8) | Trong kami |
|---|---|
| 1. ETA theo thời gian | `hour_profile` (24 hệ số, mặc định có đỉnh 7–9h và 17–19h) × `weather_factor` (`clear` 1,0; `rain` 1,25; `heavy_rain` 1,5) |
| 2. Sự cố là sự kiện ngoại sinh | `Incident(id, zones, factor, cancel_multiplier)`: chậm `factor` lần trên mọi node của zone bị ảnh hưởng; xe đang chạy được tính lại đường; khách chờ trong vùng có hazard hủy × `cancel_multiplier` |
| 3. Đồng mô phỏng vi mô | Không có trong engine (FleetPy có coupling SUMO riêng) — xem docs/engine/17 |

Cấu hình qua `Scenario.traffic` (truyền thẳng vào `TrafficLayer`):

```python
ScenarioBuilder(net, zones, traffic={"hour_profile": [...24 số...],
                                     "weather_factor": {"rain": 1.4},
                                     "platform_sees_incidents": False})
```

| Hàm | Dùng bởi |
|---|---|
| `travel(o, d, t)` | Chặng xe thật sự chạy (có tính sự cố) |
| `estimate(o, d, t)` | ETA của nền tảng: báo giá, ETA hứa, matching, pooling. Mặc định **không** biết sự cố, nên sinh ra sai lệch ETA |
| `many_to_one(origins, d, t, max_tt, aware)` | Matching |
| `path(o, d)` | Nội suy vị trí xe đang chạy |
| `incident_at(node)`, `multiplier(t)` | `Context` cho behavior model |

Các hàm truy vấn nhận thêm `group=` (mặc định `"car"`); engine truyền nhóm xe của tài xế (`Driver.group`).

### Tắc đường theo zone × giờ (Sprint 02, `kami/congestion.py`, quyết định D9)

Bật bằng `traffic={"congestion": {...}}` (hoặc `TrafficSpec.congestion`). Hệ số nhân travel time của một cạnh:

```
hệ_số = 1 + (P_g(h) − 1) × s_class × s_vehicle
```

- `g`: nhóm tắc của zone chứa **node cuối** của cạnh. Mặc định (`zone_groups="ring"`) theo khoảng cách từ tâm zone tới
  tâm vòng: `core` < 3 km ≤ `inner` < 8 km ≤ `outer`. Tâm mặc định là Hồ Hoàn Kiếm (105,8522; 21,0287) khi mạng có
  lon/lat bao điểm đó, ngược lại là tâm của mạng. Có thể gán tay `{zone: nhóm}` hoặc file `zone,group`.
- `P_g(h)`: 24 hệ số theo giờ của nhóm. Hoặc `kind="file"`: file `zone,hour,factor` cho từng zone (khi có GPS).
- `s_class`: theo loại đường (`edge_attributes.csv`; lưới và mạng không có file: 1).
- `s_vehicle`: `congestion_scale` của nhóm xe.

**Giả định** (chưa hiệu chỉnh bằng GPS — xem backlog Sprint 02):

| Giờ | 0–4 | 5 | 6 | 7 | 8 | 9 | 10–11 | 12 | 13–14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `core` | 1,0 | 1,05 | 1,3 | 1,9 | **2,2** | 1,7 | 1,4 | 1,45 | 1,35 | 1,45 | 1,7 | 2,1 | **2,2** | 1,7 | 1,4 | 1,25 | 1,1 | 1,0 |

`inner` = `1 + (core − 1) × 0,7`, `outer` = `1 + (core − 1) × 0,4`. `s_class`: motorway 0,6; trunk 0,9; primary,
secondary 1,0; tertiary 0,9; unclassified 0,7; residential 0,6; living_street 0,4 (`_link` theo loại gốc).

Tắc đường là **trạng thái theo chu kỳ** (giống thư mục travel time theo mốc của FleetPy): `apply_period(t)` đặt
travel time cạnh của mọi nhóm xe cho chu kỳ chứa `t` (mặc định `period_s = 3600`, căn theo giờ đồng hồ). Engine gọi ở
mỗi `CONGESTION_UPDATE` (docs/engine/02). `travel(o, d, t)` dùng trạng thái hiện tại, không đổi theo `t`. Trên
`GridNetwork` hệ số đi vào routing dưới dạng `node_factor` (cạnh đi vào node). Khi bật tắc đường, `hour_profile`
toàn thành phố không còn tác dụng (quyết định D11), `weather_factor` vẫn nhân chung.

Nền tảng (`estimate`) **thấy** tắc đường thường ngày (dữ liệu lịch sử), vẫn **không** thấy sự cố. Sự cố nhân thêm trên
travel time đã có tắc (router "live" được đồng bộ lại mỗi khi travel time nền đổi).

### Nhóm xe (Sprint 02, S02-7)

`traffic={"vehicle_groups": {"car": {}, "bike": {"speed_factor": 0.9, "congestion_scale": 0.5}}}`:

| Tham số | Ý nghĩa | Mặc định `car` / `bike` (giả định) |
|---|---|---|
| `speed_factor` | Tốc độ free-flow so với ô tô (travel time ÷ hệ số) | 1,0 / 0,9 |
| `congestion_scale` | Phần mức tắc của ô tô mà nhóm chịu (`s_vehicle`) | 1,0 / 0,5 |

Cạnh cấm lấy từ dữ liệu (`allow_car`, `allow_bike`). Nhóm của tài xế: `Driver.group`, lấy từ
`attrs["vehicle_group"]` (= `VehicleTypeSpec.group` của fleet). **Không khai báo `vehicle_groups` thì mọi xe đi như
ô tô** (kết quả của spec 0.1/Sprint 01 có loại xe `bike` không đổi); nhóm không có trong `vehicle_groups` cũng đi như
ô tô. Matching tính ETA theo từng nhóm (`many_to_one` một lần cho mỗi nhóm có trong ứng viên). Thời gian chuyến trực
tiếp để tính cước dùng nhóm `car` (khách chưa chọn loại dịch vụ — Sprint 05/06).

**Giới hạn đã biết:**
- Không bật tắc đường thì hệ số giờ và thời tiết là hệ số toàn thành phố.
- Chặng đã xuất phát giữ thời gian tính lúc xuất phát khi chỉ có hệ số giờ thay đổi. Engine tính lại khi thời tiết
  hoặc sự cố đổi, và khi chu kỳ tắc đường đổi làm thời gian còn lại lệch quá `retime_threshold`.
- Travel time của một chặng tính theo trạng thái lúc xuất phát, không tích phân theo thời gian (chặng 7h50–8h10 dùng
  hệ số 7h cho tới lần tính lại ở 8h).
- Chưa có hạn chế rẽ và thời gian chờ đèn ở nút giao.

Muốn dùng ma trận ETA học từ GPS theo zone × giờ × thời tiết: viết một `Network` trả `base_travel` từ ma trận
(docs/engine/17).

## Nguồn dữ liệu giao thông

Xem design doc §8. Thứ tự ưu tiên là GPS của chính hãng: tốc độ theo zone × giờ × thời tiết, sự cố cũ hiện ra dưới
dạng tốc độ sụt cục bộ. Google Routes, Waze, TomTom hay HERE chỉ nên dùng để lấy mẫu kiểm chứng.
