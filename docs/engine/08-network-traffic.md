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

### `GridNetwork` (`network/grid.py`)
Thành phố lưới synthetic: `width_m × height_m`, bước `spacing_m`, vận tốc `speed_kmh`. Quãng đường là khoảng cách
Manhattan. Khi có sự cố, engine thử hai lộ trình chữ L và chọn cái nhanh hơn. Không cần dữ liệu, routing gần như
tức thời, dùng cho prototype và test.

### `FleetPyNetwork` (`network/fleetpy_network.py`)
Dùng lại `NetworkBasic` / `NetworkBasicCpp` của FleetPy (chi tiết ở docs/engine/16).

```python
net = FleetPyNetwork("example_network", backend="auto")   # "auto" | "cpp" | "python"
```

- Đọc `FleetPy/data/networks/<name>/base/{nodes,edges}.csv` và `crs.info`.
- `location_nodes()` là thành phần liên thông mạnh lớn nhất, bỏ các node stop-only. Mạng ví dụ không liên thông
  mạnh hoàn toàn: có 7.140/7.617 node dùng được.
- Cặp điểm không có đường đi: dùng fallback `khoảng cách chim bay × 1,4` ở 8 m/s.
- Cache kết quả free-flow `(o, d)` (mặc định 200k cặp).
- `update_network(t)`: nạp file travel time động của FleetPy (`network_dynamics_file`) khi tới mốc. Engine gọi qua
  `TRAFFIC_UPDATE`.
- **Backend C++** (khi FleetPy đã build `cpp_router`): nhanh hơn khoảng 20 lần. Sự cố được áp vào một **router C++
  thứ hai** (trạng thái "live") qua `updateEdgeTravelTimes`, chính là cơ chế mạng động của FleetPy. Nhờ vậy góc
  nhìn free-flow của nền tảng và trạng thái thật có sự cố cùng tồn tại mà vẫn nhanh.
- **Backend Python:** sự cố đi qua `customized_section_cost_function` của router FleetPy. Đúng nhưng chậm.

## Zone (`network/zones.py`)

Zone là đơn vị không gian cho metric theo khu, surge, ma trận di chuyển và vùng sự cố. Thay cho lưới H3 trong
design doc, vì `h3` là phụ thuộc tuỳ chọn.

| Lớp | Zone id | Khi nào dùng |
|---|---|---|
| `SquareZoneSystem(net, cell_m=1000)` | `"i_j"` | Mặc định, chạy được ở mọi nơi |
| `H3ZoneSystem(net, resolution=8)` | H3 cell | Cần `pip install h3` và mạng có lon/lat (FleetPy) |
| `FleetPyZoneSystem(net, "example_zones")` | int | Dùng lại `FleetPy/data/zones/<name>/<network>/node_zone_info.csv` |

API: `zone_of(node)`, `zones()`, `nodes_in(z)`, `location_nodes_in(z)`, `centroid_node(z)`, `neighbors(z)`
(theo khoảng cách tâm), `zones_within(node, radius_m)`.

## Traffic layer (`kami/traffic.py`)

```
thời_gian = base_network_time(tránh sự cố) × hour_profile[giờ] × weather_factor[thời_tiết]
```

| Mức (design doc §8) | Trong kami |
|---|---|
| 1. ETA theo thời gian | `hour_profile` (24 hệ số, mặc định có đỉnh 7–9h và 17–19h) × `weather_factor` (`clear` 1,0; `rain` 1,25; `heavy_rain` 1,5) |
| 2. Sự cố là sự kiện ngoại sinh | `Incident(id, zones, factor, cancel_multiplier)`: chậm `factor` lần trên mọi node của zone bị ảnh hưởng; xe đang chạy được tính lại đường; khách chờ trong vùng có hazard hủy × `cancel_multiplier` |
| 3. Đồng mô phỏng vi mô | Không có trong engine. FleetPy có coupling SUMO (`FleetPy/studies/fleetpy_sumo_coupling`) — xem docs/engine/17 |

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

**Giới hạn đã biết:**
- Hệ số giờ và thời tiết là hệ số toàn thành phố.
- Chặng đã xuất phát giữ thời gian tính lúc xuất phát khi chỉ có hệ số giờ thay đổi. Engine chỉ tính lại khi thời
  tiết hoặc sự cố đổi.

Muốn dùng ma trận ETA học từ GPS theo zone × giờ × thời tiết: viết một `Network` trả `base_travel` từ ma trận
(docs/engine/17).

## Nguồn dữ liệu giao thông

Xem design doc §8. Thứ tự ưu tiên là GPS của chính hãng: tốc độ theo zone × giờ × thời tiết, sự cố cũ hiện ra dưới
dạng tốc độ sụt cục bộ. Google Routes, Waze, TomTom hay HERE chỉ nên dùng để lấy mẫu kiểm chứng.
