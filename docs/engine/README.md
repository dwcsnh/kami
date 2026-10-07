# Tài liệu engine kami (0.1)

> Tài liệu từng module của engine. Mục lục chung, yêu cầu 0.2 và lộ trình sprint ở [../README.md](../README.md).
> Design doc gốc: [../design/policy_simulator_design_v0.md](../design/policy_simulator_design_v0.md).

| # | Tài liệu | Nội dung |
|---|---|---|
| 01 | [Kiến trúc tổng thể](01-architecture.md) | Các lớp, luồng một chuyến đi, ánh xạ sang design doc |
| 02 | [Simulation engine](02-engine.md) | Vòng lặp sự kiện, cơ chế thời gian, `SimConfig`, API cho policy |
| 03 | [Sự kiện](03-events.md) | Danh mục sự kiện, payload, thứ tự ưu tiên, sự kiện chỉ ghi log |
| 04 | [Agents](04-agents.md) | Rider, Driver, Job, Leg, Stop, Quote, PoolOffer và state machine |
| 05 | [Common Random Numbers](05-crn.md) | Thiết kế CRN, danh mục khoá, quy tắc giữ CRN |
| 06 | [Behavior models](06-behavior.md) | Interface từng điểm quyết định, model mặc định, registry |
| 07 | [Policy plugin](07-policy.md) | Hook, API, policy dựng sẵn, cách viết policy mới |
| 08 | [Network, zone & traffic](08-network-traffic.md) | Lưới synthetic, mạng FleetPy, zone, ETA theo giờ/thời tiết, sự cố |
| 09 | [Kịch bản](09-scenario.md) | `Scenario`, preset, sinh synthetic, replay FleetPy/CSV |
| 10 | [Matching, pooling, pricing](10-matching-pooling-pricing.md) | Batch matching, insertion pooling, mô hình cước |
| 11 | [Metrics](11-metrics.md) | Định nghĩa từng metric, đơn vị, chiều "tốt hơn" |
| 12 | [Evaluation](12-evaluation.md) | Experiment CRN, CI, decision rule, sensitivity, grid search, report |
| 13 | [Event log](13-eventlog.md) | Định dạng, export CSV/JSONL/pandas/Parquet |
| 14 | [Training & model registry](14-training-registry.md) | Fit model ngoài simulator, checkpoint JSON |
| 15 | [CLI](15-cli.md) | `python -m kami presets/run/compare` |
| 16 | [Tái sử dụng FleetPy](16-fleetpy-integration.md) | Phần dùng lại, phần viết lại và lý do |
| 17 | [Giới hạn & lộ trình](17-limitations-roadmap.md) | Phần chưa làm, rủi ro, việc tiếp theo |

**Quy ước đơn vị trong code:** thời gian là giây, khoảng cách là mét, tiền là VND. Riêng metric báo cáo
thời gian theo phút và khoảng cách theo km (xem [11-metrics.md](11-metrics.md)). Thời điểm mô phỏng tính bằng giây
kể từ 0h của ngày kịch bản, ví dụ 7h sáng = `25200`.
