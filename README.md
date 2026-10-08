# kami — mô phỏng & đánh giá policy cho hãng gọi xe

`kami` là simulation engine **agent-based, discrete-event** được dựng theo
[`policy_simulator_design_v0.md`](docs/design/policy_simulator_design_v0.md). Mục tiêu: đưa một policy mới (ghép chuyến,
giá, dispatch, điều xe…) vào môi trường mô phỏng, chạy **cặp baseline / treatment trên cùng kịch bản và cùng số
ngẫu nhiên (CRN)**, rồi báo cáo **hiệu ứng nhân quả ± khoảng tin cậy 95%** kèm quy tắc quyết định viết trước.

> **Phạm vi hiện tại (kami 0.2):** matching **1 tài xế – 1 khách**, chưa có ghép chuyến. Các ví dụ pooling bên dưới
> (`PoolAfterWait`, `02_pool_after_wait.py`) là của kami 0.1, vẫn chạy được nhưng tạm thời không dùng trong 0.2 — xem
> [docs/requirements.md §5](docs/requirements.md#5-ngoài-phạm-vi-hiện-tại).

```
Scenario (ngoại sinh, replay) ──▶ Simulation engine ◀──▶ Policy plugin (hooks)
                                     │      ▲
                                     │      └── Behavior models (registry, CRN)
                                     ▼
                               Event log ──▶ Metrics ──▶ Evaluator (CRN, bootstrap CI, decision rule)
```

## Hướng dẫn chạy kịch bản Hà Nội

Phần này đi từ lúc vừa `git clone` tới lúc chạy được kịch bản Hà Nội và xem nó trên bản đồ. Các lệnh khác của CLI
(lưới synthetic, mạng mẫu, so sánh policy, benchmark…) xem ở [docs/engine/15-cli.md](docs/engine/15-cli.md).

### Cần chuẩn bị

- Python ≥ 3.9, Node.js ≥ 20 (`web/.nvmrc`: 24), trình biên dịch C++ (`g++`) để build router C++.
- Khoảng 2 GB RAM trống và kết nối Internet (tải dữ liệu OSM, tile bản đồ Mapbox).
- Một **Mapbox public token** (`pk.…`), tạo miễn phí trên mapbox.com — chỉ cần cho phần bản đồ.

### Dữ liệu: cái gì có sẵn, cái gì phải tự tạo

| Dữ liệu | Có trong repo? | Ghi chú |
|---|---|---|
| Kịch bản `scenarios/hanoi/*.json` | Có | File cấu hình (RunSpec) của từng kịch bản |
| Cấu hình build mạng `data/osm/hanoi.json`, `data/osm/hanoi_area.geojson` | Có | Phiên bản dữ liệu OSM và phạm vi 12 quận |
| Replay demo `web/public/fixtures/hanoi_center_demo/` (~1,2 MB) | Có | Web mở được ngay, không cần build mạng |
| File OSM `data/osm/cache/vietnam-*.osm.pbf` (~330 MB) | **Không** | Tự tải ở bước 2 |
| Mạng `data/networks/hanoi/`, zone `data/zones/hanoi_*` | **Không** | Sinh ra ở bước 2 |
| Mapbox token `web/.env.local` | **Không** (bí mật) | Tự tạo ở bước 4 |

> Chỉ muốn **xem bản đồ demo**: bỏ qua bước 1–3, làm bước 4 rồi mở `http://localhost:3000`.

### Bước 1 — Cài môi trường Python

Cài môi trường python:

```bash
python -m venv .venv
source .venv/bin/activate
```

Cài kami ở chế độ editable (sửa code là có hiệu lực ngay) kèm các thư viện tuỳ chọn: `osm` (osmium, pyproj, h3 — đọc
dữ liệu OSM để dựng mạng Hà Nội), `cpp` (cython — build router C++), `store` (pyarrow — ghi nhật ký sự kiện dạng
Parquet mà các kịch bản Hà Nội dùng).

```bash
pip install -e ".[osm,cpp,store]"
```

Biên dịch router C++ (tính đường đi ngắn nhất). Không bắt buộc, nhưng router Python chậm hơn khoảng 10 lần trên mạng
Hà Nội. Phải build lại khi đổi môi trường Python.

```bash
python -m kami.network.road.cpp.build
```

### Bước 2 — Dựng mạng đường Hà Nội (một lần)

Tải file OSM Việt Nam của Geofabrik (~330 MB, cache ở `data/osm/cache/`, kiểm sha256), cắt theo phạm vi 12 quận nội
thành, rồi ghi mạng đường vào `data/networks/hanoi/` và hệ zone vào `data/zones/hanoi_h3_r8/`, `data/zones/hanoi_wards/`.
Mất khoảng 95 s (chưa tính thời gian tải) và 1,6 GB RAM. Chạy lại khi file OSM đã có thì không tải nữa.


```bash
python -m kami.osm build hanoi
```

Tuỳ chọn: in kích thước mạng, tỷ lệ cặp điểm có đường đi và thời gian truy vấn của router — để chắc mạng dựng đúng.

> Cấu hình khoá đúng bản `vietnam-261006.osm.pbf` (sha256 trong `data/osm/hanoi.json`) để mạng tái tạo được từng byte.
> Geofabrik không giữ bản theo ngày mãi mãi — nếu link hết hạn, xin file PBF từ người đã có và chép vào
> `data/osm/cache/`. Chi tiết: [docs/engine/19-osm-pipeline.md](docs/engine/19-osm-pipeline.md).

```bash
python -m kami.osm check hanoi
```

### Bước 3 — Chạy kịch bản

```bash
python -m kami presets
```
Không chạy mô phỏng; liệt kê các kịch bản có sẵn (phần "Scenario files") và các policy. Kịch bản Hà Nội:

| File | Nội dung |
|---|---|
| `scenarios/hanoi/demo_center.json` | Hoàn Kiếm, Ba Đình, Đống Đa, Hai Bà Trưng; 7h–9h; 300 xe — **dùng cho visualizer** |
| `scenarios/hanoi/am_peak.json` | Toàn mạng, cao điểm sáng 6h–10h; 1.500 xe |
| `scenarios/hanoi/pm_peak_rain.json` | Cao điểm chiều 16h–20h, trời mưa; 1.500 xe |
| `scenarios/hanoi/incident_arterial.json` | 16h–20h, có sự cố ở nút Nguyễn Trãi – Khuất Duy Tiến; 1.500 xe |
| `scenarios/hanoi/weekday.json` | Cả ngày 0h–24h; 8.000 xe |

Có hai cách chạy, tuỳ mục đích:

**a) Lấy số liệu** (không xem bản đồ):

```bash
python -m kami run --spec scenarios/hanoi/am_peak.json --out out/hanoi_am_peak
```
Chạy mô phỏng theo file kịch bản và ghi kết quả vào `out/hanoi_am_peak/`: `metrics.json` (chỉ số tổng: tỷ lệ hoàn
thành, huỷ, thời gian chờ…), `timeseries.json` (chỉ số theo thời gian), `run_spec.resolved.json` (cấu hình đầy đủ đã
dùng) và nhật ký sự kiện. Đổi `--spec` sang file kịch bản khác để chạy kịch bản đó.

```bash
python -m kami run --spec scenarios/hanoi/am_peak.json --db kami.db
```
Cách khác của lệnh trên: lưu lần chạy vào cơ sở dữ liệu SQLite `kami.db` (in ra `run_id`, file lớn ở `runs/<run_id>/`)
để tra cứu, so sánh nhiều lần chạy về sau.

**b) Xem trên bản đồ:**

```bash
python -m kami replay export --spec scenarios/hanoi/demo_center.json --out web/public/fixtures/my_run
```
Chạy kịch bản (có ghi quỹ đạo từng xe) rồi xuất thư mục replay cho visualizer — vị trí xe theo thời gian, sự kiện của
khách (đặt, đón, trả, huỷ), chỉ số theo phút. Kịch bản demo mất khoảng 15 s. Thư mục ra phải nằm dưới `web/public/`
để web đọc được. Hiện chỉ `demo_center.json` được thiết kế cho visualizer; các kịch bản 1.500–8.000 xe cho file rất
lớn và web có thể chậm.

```bash
python -m kami replay validate web/public/fixtures/my_run
```
Tuỳ chọn: kiểm tra thư mục replay hợp lệ (đủ file, sha256 khớp, dữ liệu nhất quán); báo lỗi nếu có.

### Bước 4 — Chạy visualizer web

```bash
cd web
```
Vào thư mục ứng dụng web.

```bash
cp .env.example .env.local
```
Tạo file cấu hình cục bộ, rồi mở `web/.env.local` và điền token: `NEXT_PUBLIC_MAPBOX_TOKEN=pk.…`. File này đã có trong
`.gitignore`, không commit. Thiếu token thì trang hiện hướng dẫn cấu hình thay cho bản đồ.

```bash
npm ci
```
Cài thư viện JavaScript đúng phiên bản trong `package-lock.json` (chỉ cần lần đầu hoặc khi `package-lock.json` đổi).

```bash
npm run dev
```
Chạy web ở chế độ phát triển tại `http://localhost:3000`. Giữ terminal này mở trong lúc xem.

Mở trình duyệt:

- `http://localhost:3000/?replay=/fixtures/my_run` — replay vừa xuất ở bước 3b;
- `http://localhost:3000` — replay demo có sẵn trong repo.

Cách dùng màn hình (phát lại, tua, chọn xe, ẩn trạng thái, chế độ quỹ đạo) và các tham số URL khác:
[docs/engine/20-visualizer.md](docs/engine/20-visualizer.md).

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
| `kami/network/`, `kami/traffic.py` | Mạng đường (lưới / mạng thật `network/road`), zone, traffic layer, sự cố | [docs/engine/08-network-traffic.md](docs/engine/08-network-traffic.md) |
| `kami/scenario.py` | Kịch bản, preset, replay FleetPy / CSV | [docs/engine/09-scenario.md](docs/engine/09-scenario.md) |
| `kami/matching.py`, `kami/pooling.py`, `kami/pricing.py` | Matching, ghép chuyến, cước | [docs/engine/10-matching-pooling-pricing.md](docs/engine/10-matching-pooling-pricing.md) |
| `kami/metrics.py` | Bộ metric | [docs/engine/11-metrics.md](docs/engine/11-metrics.md) |
| `kami/evaluation/` | Experiment CRN, thống kê, decision rule, sensitivity, report | [docs/engine/12-evaluation.md](docs/engine/12-evaluation.md) |
| `kami/eventlog.py` | Event log & export | [docs/engine/13-eventlog.md](docs/engine/13-eventlog.md) |
| `kami/training/` | Pipeline fit model → registry | [docs/engine/14-training-registry.md](docs/engine/14-training-registry.md) |
| `kami/cli.py` | `python -m kami …` | [docs/engine/15-cli.md](docs/engine/15-cli.md) |
| `kami/config/`, `kami/timeseries.py` | Spec JSON, bộ dựng spec → engine, chuỗi thời gian metric | [docs/engine/18-config-persistence.md](docs/engine/18-config-persistence.md) |
| `kami/store/`, `kami/bench.py`, `benchmarks/` | DB SQLite, lưu run, benchmark | [docs/engine/18-config-persistence.md](docs/engine/18-config-persistence.md) |
| — | Phần lấy từ FleetPy | [docs/engine/16-fleetpy-integration.md](docs/engine/16-fleetpy-integration.md) |
| — | Giới hạn & lộ trình | [docs/engine/17-limitations-roadmap.md](docs/engine/17-limitations-roadmap.md) |

Bắt đầu từ [docs/README.md](docs/README.md) (mục lục chung), [docs/engine/README.md](docs/engine/README.md) (tài liệu
engine) và [docs/engine/01-architecture.md](docs/engine/01-architecture.md).

## Hướng phát triển tiếp theo (kami 0.2)

kami đang được mở rộng từ một engine chạy bằng CLI thành **nền tảng mô phỏng vận hành GreenSM tại Hà Nội**
(~100k request/ngày, ~8k xe điện): bản đồ Hà Nội thật, tắc đường giờ cao điểm, nhiều fleet và loại xe, sạc xe,
dynamic pricing, kèm giao diện quản lý và visualizer. Hệ thống policy (policy plugin, policy group, policy agent) hiện
nằm ngoài phạm vi (xem [requirements §5](docs/requirements.md#5-ngoài-phạm-vi-hiện-tại)).

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
| 3h có tai nạn, ~740 request, 60 xe | `example_network` (7,6k node), router C++ | ~1,7 s |
| như trên | `example_network`, router Python | ~20–25 s |
| 960 lần chạy (4 kịch bản × 30 seed × 2 arm × 4 biến thể) | Lưới, 16 tiến trình | ~70 s |
