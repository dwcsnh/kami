# 16 · Phần lấy từ FleetPy

Design doc §12 đề xuất: *tự viết engine mỏng với interface policy/behavior/CRN, tái sử dụng thuật toán từ FleetPy
và ý tưởng decision function từ MaaSSim.* Bảng dưới ghi rõ phần nào của FleetPy đã được đưa vào kami, và phần nào
phải viết lại.

Từ 2026-10, kami **không còn import FleetPy**: phần mạng đường được port vào `kami/network/road/` (giấy phép MIT của
TUM-VT giữ ở [`kami/network/road/LICENSE-FleetPy`](../../kami/network/road/LICENSE-FleetPy)). Không cần checkout
FleetPy, không cần `numpy`/`pandas`.

## Port vào kami

| Thành phần FleetPy gốc | Trong kami | Ghi chú |
|---|---|---|
| `src/routing/road/NetworkBasic.py` (đọc mạng, travel time động) | `kami/network/road/graph.py` — `RoadGraph` | Đọc CSV bằng thư viện chuẩn thay cho pandas |
| `src/routing/road/routing_imports/Router.py` + `PriorityQueue_python3.py` | `kami/network/road/router.py` — `Router` | Chỉ giữ Dijkstra 1→1 hai chiều và 1→X / X→1 có bán kính; thứ tự duyệt, tie-break, điều kiện dừng giữ nguyên; trạng thái tìm kiếm để trong dict thay vì thuộc tính node |
| `src/routing/road/NetworkBasicCpp.py` + `cpp_router/` (C++ + Cython) | `kami/network/road/cpp/` — `_router.pyx`, `Network/Node/Edge.cpp` | Wrapper Cython dùng `std::vector` thay cho numpy; bỏ log `cout`; lỗi mở file thành `RuntimeError`; thêm `setEdgeTravelTimes(from[], to[], tt[])` (Sprint 02) — như `updateEdgeTravelTimes` nhưng đọc từ bộ nhớ thay vì file CSV |
| Lớp ghép các phần trên | `kami/network/road/network.py` — `RoadNetwork` | Thay cho `FleetPyNetwork` cũ (tên cũ vẫn dùng được) |
| Định dạng `data/networks/<name>/base/{nodes,edges}.csv`, `crs.info` | Giữ nguyên định dạng | Mạng tạo bằng công cụ tiền xử lý của FleetPy vẫn dùng được: chép thư mục mạng vào `data/networks/` |
| Thư mục travel time động / file `network_dynamics_file` | `RoadNetwork(network_dynamics_file=…)` + `TRAFFIC_UPDATE` | Hỗ trợ cả thư mục theo mốc thời gian và hệ số `travel_time_factor` |
| `data/zones/<name>/<network>/node_zone_info.csv` | `FileZoneSystem` (tên cũ `FleetPyZoneSystem`) | |
| `data/demand/.../*.csv` (`rq_time,start,end,request_id`) | `ScenarioBuilder.from_fleetpy_demand` | Chỉ là định dạng file |
| Ý tưởng "plan vs. reality" (`VehiclePlan` vs. thực thi) | `TrafficLayer.estimate` vs `travel`, `rider.eta_promised` | Viết lại theo cùng ý tưởng |

**Kiểm chứng khi port:** trên `example_network`, travel time, lộ trình, many-to-one và trạng thái sự cố (router
"live") của bản port trùng khít bản FleetPy khi đọc số cùng cách; metric của các run replay demand và preset `accident`
giống hệt ở cả backend C++ và Python. Khác biệt duy nhất: FleetPy đọc CSV bằng pandas (bộ parse nhanh, không luôn làm
tròn đúng) nên một số travel time lệch ở chữ số cuối (ví dụ `1952.6080000000002` so với `1952.608`); kami dùng
`float()` chuẩn, cùng giá trị mà router C++ đọc bằng `stod`.

## Phần mở rộng định dạng mạng (Sprint 02)

Mạng do pipeline OSM của kami tạo (docs/engine/19) vẫn là một thư mục FleetPy hợp lệ: FleetPy và router C++ đọc
`nodes.csv`/`edges.csv` theo tên cột nên bỏ qua cột và file thêm. kami dùng các phần thêm sau khi có:

| File / cột | Nội dung | Dùng cho |
|---|---|---|
| `base/nodes.csv`: cột `lon`, `lat`, `osm_id` | Toạ độ WGS84 (7 chữ số), id node OSM | `lonlat()` không cần `pyproj`; `node_at_lonlat` |
| `base/edge_attributes.csv` | `from_node,to_node,road_class,allow_car,allow_bike,speed_kmh,maxspeed_tag` | Hệ số tắc theo loại đường; cạnh cấm theo nhóm xe; cột `allow_<nhóm>` bất kỳ được đọc |
| `base/edge_geometry.csv` | `from_node,to_node,lons,lats` (polyline gồm cả hai node đầu mút, phân cách `;`) | Quỹ đạo vẽ theo đường cong thật |
| `manifest.json` (thư mục mạng) | Phiên bản dữ liệu: file PBF nguồn, ngày, sha256, phiên bản pipeline, số liệu mạng/zone | Truy vết dữ liệu (AC02-1) |

Travel time động theo zone × giờ không ghi ra `edges_td_att.csv`: kami sinh trong bộ nhớ và đặt thẳng vào router
(`RoadNetwork.set_edge_factors`, docs/engine/08) — cùng cơ chế "đặt lại travel time cạnh theo mốc" của FleetPy, tránh
ghi/đọc ~70k cạnh × 2 nhóm xe mỗi giờ.

## Dữ liệu và build

- Dữ liệu mặc định ở `data/` của repo (`networks/`, `zones/`, `demand/`); đổi bằng biến môi trường `KAMI_DATA_ROOT`
  hoặc tham số `data_root=`. `RoadNetwork` nhận cả đường dẫn thư mục mạng. Tham số `fleetpy_root=` của 0.1 vẫn chạy
  (nghĩa là `data_root=<fleetpy_root>/data`).
- Router C++ là extension tuỳ chọn, build một lần cho mỗi môi trường Python:

```bash
pip install cython                      # hoặc: pip install -e ".[cpp]"
python -m kami.network.road.cpp.build   # cần trình biên dịch C++17
```

Chưa build thì `RoadNetwork(backend="auto")` dùng router Python (chậm hơn khoảng 12–15 lần, cùng lộ trình). Travel
time của hai backend có thể lệch khoảng 1e-9 s (cộng dồn theo thứ tự khác — FleetPy gốc cũng vậy), đủ để một run
phân nhánh nhẹ: **mốc benchmark và các arm của một thí nghiệm phải dùng cùng backend** (`sim.network.backend`).
`lonlat()` cần `pyproj` (`pip install -e ".[geo]"`).

## Viết lại theo ý tưởng của FleetPy (không import được)

| Thành phần FleetPy | Vì sao không import | Thay thế trong kami |
|---|---|---|
| `fleetctrl/pooling/immediate/insertion.py` (insertion heuristic) | Gắn chặt với `FleetControlBase`, `VehiclePlan`, `PlanRequest`, `SimulationVehicle`; dùng nó đồng nghĩa với kéo theo toàn bộ fleet control của FleetPy | `kami.pooling.Pooling.best_insertion`: cùng thuật toán trên `Stop` gọn hơn |
| `fleetctrl/pooling/batch/AlonsoMora` | Như trên, và cần Gurobi | Chưa có. Ghép theo batch tối ưu là việc tiếp theo (docs/engine/17) |
| `fleetctrl/repositioning/*` | Phụ thuộc `RepositioningBase`, forecast zone system của FleetPy | `HeatmapReposition`: policy cân bằng cung cầu theo zone đơn giản |
| `fleetctrl/pricing/*` (TimeBased/UtilizationBased DP) | Phụ thuộc fleet control | `SurgePricing` |
| `fleetctrl/charging/*` | Phụ thuộc fleet control và hạ tầng sạc của FleetPy | Chưa có (`CHARGING`, `CHARGE_START/END` để sẵn) |
| `demand/TravelerModels.py` | Mô hình chọn offer gắn với vòng lặp theo bước thời gian của FleetPy; không có CRN | `BehaviorSuite` (docs/engine/06) |
| Vòng lặp mô phỏng `FleetSimulationBase` | Chạy theo bước thời gian; xe làm theo lệnh của nhà vận hành, tài xế không tự quyết | `kami.core.engine` (discrete-event) |

## Khi nào nên dùng FleetPy trực tiếp thay vì kami

- Cần ghép batch tối ưu (Alonso-Mora), sạc xe điện, nhiều nhà vận hành, broker hay MaaS liên phương thức: đó là các
  module trưởng thành của FleetPy.
- Cần đồng mô phỏng vi mô với SUMO: dùng `FleetPy/studies/fleetpy_sumo_coupling`.

Kami tập trung vào thứ FleetPy không có: **tài xế và khách tự ra quyết định, policy dạng plugin, CRN và đánh giá
nhân quả**.
