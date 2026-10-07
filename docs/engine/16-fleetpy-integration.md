# 16 · Tái sử dụng FleetPy

Design doc §12 đề xuất: *tự viết engine mỏng với interface policy/behavior/CRN, tái sử dụng thuật toán từ FleetPy
và ý tưởng decision function từ MaaSSim.* Bảng dưới ghi rõ phần nào của FleetPy được dùng lại, dùng như thế nào,
và phần nào phải viết lại.

## Dùng trực tiếp (import FleetPy như thư viện, không copy code)

| Thành phần FleetPy | Dùng trong kami | Cách dùng |
|---|---|---|
| `src/routing/road/NetworkBasic.py` + `routing_imports/Router.py` | `FleetPyNetwork(backend="python")` | Dijkstra hai chiều, X→1, lộ trình; sự cố đi qua `customized_section_cost_function` |
| `src/routing/road/NetworkBasicCpp.py` + `cpp_router/PyNetwork` | `FleetPyNetwork(backend="cpp")` (mặc định khi đã build) | Router C++; sự cố qua `updateEdgeTravelTimes` trên router "live" thứ hai |
| Định dạng `data/networks/<name>/base/{nodes,edges}.csv`, `crs.info` | Mạng đường, chuyển lon/lat | Mọi mạng FleetPy đều dùng được, kể cả mạng tạo bằng `src/preprocessing` của FleetPy |
| Thư mục travel time động của mạng (`network_dynamics_file`) | `FleetPyNetwork(network_dynamics_file=…)` + `TRAFFIC_UPDATE` | Gọi `NetworkBasic.update_network(t)` |
| `data/zones/<name>/<network>/node_zone_info.csv` | `FleetPyZoneSystem` | Zone cho metric, surge, ma trận di chuyển |
| `data/demand/.../*.csv` (`rq_time,start,end,request_id`) | `ScenarioBuilder.from_fleetpy_demand` | Replay demand mẫu, hoặc demand người dùng tạo bằng công cụ của FleetPy |
| Ý tưởng "plan vs. reality" (`VehiclePlan` vs. thực thi) | `TrafficLayer.estimate` vs `travel`, `rider.eta_promised` | Viết lại theo cùng ý tưởng |

`FleetPyNetwork` tìm FleetPy theo thứ tự: tham số `fleetpy_root`, biến môi trường `KAMI_FLEETPY_ROOT`, rồi thư mục
`../FleetPy` cạnh `kami/`.

```bash
conda activate fleetpy                       # môi trường đi kèm FleetPy (numpy, pandas, pyproj…)
cd FleetPy/src/routing/road/cpp_router && python setup.py build_ext --inplace   # nếu chưa build
```

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
