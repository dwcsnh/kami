# kami — mô phỏng & đánh giá policy cho hãng gọi xe

`kami` là simulation engine **agent-based, discrete-event** được dựng theo
[`policy_simulator_design_v0.md`](docs/design/policy_simulator_design_v0.md). Mục tiêu: đưa một policy mới (ghép chuyến,
giá, dispatch, điều xe…) vào môi trường mô phỏng, chạy **cặp baseline / treatment trên cùng kịch bản và cùng số
ngẫu nhiên (CRN)**, rồi báo cáo **hiệu ứng nhân quả ± khoảng tin cậy 95%** kèm quy tắc quyết định viết trước.

```
Scenario (ngoại sinh, replay) ──▶ Simulation engine ◀──▶ Policy plugin (hooks)
                                     │      ▲
                                     │      └── Behavior models (registry, CRN)
                                     ▼
                               Event log ──▶ Metrics ──▶ Evaluator (CRN, bootstrap CI, decision rule)
```

## Cài đặt & chạy nhanh

Lõi engine chỉ dùng **thư viện chuẩn Python ≥ 3.9**. `numpy`/`scipy` (Hungarian matching) và FleetPy là tuỳ chọn.

```bash
cd kami
python examples/01_quickstart.py                     # 1 lần chạy baseline trên thành phố lưới synthetic
python examples/02_pool_after_wait.py 30             # ví dụ đầy đủ của design doc: ghép sau 5' +20k
python -m kami compare --presets weekday_am_peak,undersupply --seeds 10 \
       --treatment pool_after_wait --arg surcharge=20000 --pooling-rule --report out/report.md
python -m unittest discover -s tests -t .            # 36 test
```

Với mạng đường thật của FleetPy (cần môi trường có `numpy`, `pandas`, `pyproj`, ví dụ `conda activate fleetpy`):

```bash
python examples/03_fleetpy_network.py
python -m kami run --network fleetpy:example_network --zones example_zones --preset accident
```

## Ví dụ tối thiểu

```python
from kami import GridNetwork, SquareZoneSystem, ScenarioBuilder, Experiment, Baseline, PoolAfterWait
from kami import pooling_rule_example

net = GridNetwork(); zones = SquareZoneSystem(net, 1000)
builder = ScenarioBuilder(net, zones)

exp = Experiment(
    scenario_fn=lambda name, seed: builder.preset(name, seed=seed),
    scenarios=["weekday_am_peak", "rain", "accident", "undersupply"],
    seeds=range(30),
    arms={"baseline": Baseline,
          "pool": lambda: PoolAfterWait(wait_threshold=300, surcharge=20_000)},
)
cmp = exp.run(n_jobs=-1).compare("baseline", "pool")
print(cmp.table(["rider.cancel_rate", "rider.wait_p90", "rider.pool_rate", "platform.contribution_margin"]))
print(pooling_rule_example().evaluate(cmp))
```

## Cấu trúc thư mục

| Đường dẫn | Thành phần | Docs |
|---|---|---|
| `kami/core/engine.py` | Simulation engine: event loop, handlers, API cho policy | [docs/engine/02-engine.md](docs/engine/02-engine.md) |
| `kami/core/events.py` | Danh mục sự kiện, thứ tự ưu tiên | [docs/engine/03-events.md](docs/engine/03-events.md) |
| `kami/core/agents.py` | Rider, Driver, Job, Leg, Stop, Quote | [docs/engine/04-agents.md](docs/engine/04-agents.md) |
| `kami/core/crn.py` | Common Random Numbers | [docs/engine/05-crn.md](docs/engine/05-crn.md) |
| `kami/behavior/` | Interface điểm quyết định, model mặc định, registry | [docs/engine/06-behavior.md](docs/engine/06-behavior.md) |
| `kami/policy/` | Policy plugin + policy dựng sẵn | [docs/engine/07-policy.md](docs/engine/07-policy.md) |
| `kami/network/`, `kami/traffic.py` | Mạng đường (lưới / FleetPy), zone, traffic layer, sự cố | [docs/engine/08-network-traffic.md](docs/engine/08-network-traffic.md) |
| `kami/scenario.py` | Kịch bản, preset, replay FleetPy / CSV | [docs/engine/09-scenario.md](docs/engine/09-scenario.md) |
| `kami/matching.py`, `kami/pooling.py`, `kami/pricing.py` | Matching, ghép chuyến, cước | [docs/engine/10-matching-pooling-pricing.md](docs/engine/10-matching-pooling-pricing.md) |
| `kami/metrics.py` | Bộ metric | [docs/engine/11-metrics.md](docs/engine/11-metrics.md) |
| `kami/evaluation/` | Experiment CRN, thống kê, decision rule, sensitivity, report | [docs/engine/12-evaluation.md](docs/engine/12-evaluation.md) |
| `kami/eventlog.py` | Event log & export | [docs/engine/13-eventlog.md](docs/engine/13-eventlog.md) |
| `kami/training/` | Pipeline fit model → registry | [docs/engine/14-training-registry.md](docs/engine/14-training-registry.md) |
| `kami/cli.py` | `python -m kami …` | [docs/engine/15-cli.md](docs/engine/15-cli.md) |
| — | Tái sử dụng FleetPy | [docs/engine/16-fleetpy-integration.md](docs/engine/16-fleetpy-integration.md) |
| — | Giới hạn & lộ trình | [docs/engine/17-limitations-roadmap.md](docs/engine/17-limitations-roadmap.md) |

Bắt đầu từ [docs/README.md](docs/README.md) (mục lục chung), [docs/engine/README.md](docs/engine/README.md) (tài liệu
engine) và [docs/engine/01-architecture.md](docs/engine/01-architecture.md).

## Hướng phát triển tiếp theo (kami 0.2)

kami đang được mở rộng từ một engine chạy bằng CLI thành **nền tảng mô phỏng vận hành GreenSM tại Hà Nội**
(~100k request/ngày, ~8k xe điện): bản đồ Hà Nội thật, tắc đường giờ cao điểm, nhiều fleet và loại xe, sạc xe,
dynamic pricing, policy lưu trong DB và tạo được bằng ngôn ngữ tự nhiên, kèm giao diện quản lý và visualizer.

| Tài liệu | Nội dung |
|---|---|
| [docs/requirements.md](docs/requirements.md) | Yêu cầu chức năng / phi chức năng có mã (`PERF-1`, `EV-2`…) |
| [docs/sprint/README.md](docs/sprint/README.md) | Lộ trình chia sprint, phụ thuộc, ma trận yêu cầu → sprint |
| [docs/implementation-plan/](docs/implementation-plan/README.md) | Hướng triển khai từng sprint (cần người dùng duyệt) |
| [docs/backlog/](docs/backlog/README.md) | Phần còn dở / đang mock sau mỗi sprint |
| [AGENTS.md](AGENTS.md) | Quy trình làm việc bắt buộc cho agent (và người) phát triển kami |

## Hiệu năng tham khảo

Đo trên máy phát triển, Python 3.10:

| Kịch bản | Mạng | Thời gian / lần chạy |
|---|---|---|
| 3h cao điểm, ~1.000 request, 150 xe | Lưới 8×8 km | ~0,4–0,7 s |
| 3h có tai nạn, ~800 request, 60 xe | FleetPy `example_network` (7,6k node), router C++ | ~1,5 s |
| như trên | FleetPy, router Python | ~35 s |
| 960 lần chạy (4 kịch bản × 30 seed × 2 arm × 4 biến thể) | Lưới, 16 tiến trình | ~70 s |
