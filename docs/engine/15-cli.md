# 15 · CLI (`kami/cli.py`)

Chạy từ thư mục `kami/`, hoặc cài bằng `pip install -e .` để có lệnh `kami`.

```bash
python -m kami presets        # liệt kê preset kịch bản, file kịch bản scenarios/*/*.json (0.2) và policy đã đăng ký
python -m kami run [...]      # một lần chạy
python -m kami compare [...]  # thí nghiệm cặp baseline vs treatment với CRN
python -m kami spec [...]     # in RunSpec JSON tương đương các cờ của run (0.2)
python -m kami run --spec F   # chạy từ file RunSpec (0.2)
python -m kami db init        # tạo / migrate DB (0.2)
python -m kami bench [...]    # benchmark suite (0.2)
python -m kami.osm build hanoi  # tạo lại mạng Hà Nội từ OSM (0.2, docs/engine/19)
```

`run --spec F --out DIR` ghi `metrics.json`, `run_spec.resolved.json`, `timeseries.json`, event log và — khi
`outputs.trajectories = "parquet"` — `trajectories.parquet` (Sprint 02). Kịch bản Hà Nội:
`python -m kami run --spec scenarios/hanoi/am_peak.json --out out/hanoi` (docs/engine/09).

## Tuỳ chọn chung

| Cờ | Mặc định | Ý nghĩa |
|---|---|---|
| `--network` | `grid` | `grid`, hoặc `road[:<tên mạng hoặc thư mục>]` (ví dụ `road:example_network`; `fleetpy:` là cách viết cũ, vẫn chạy) |
| `--zones` | (zone vuông) | Tên zone system trong `data/zones`, ví dụ `example_zones` |
| `--zone-m` | 1000 | Cạnh zone vuông (m) |
| `--grid-km` | 8 | Kích thước thành phố lưới |
| `--demand` | 200 | Request/giờ ở mức profile 1,0 |
| `--drivers` | 150 | Số tài xế |
| `--registry` | — | Thư mục model registry; nạp bản mới nhất của mọi slot có trong đó |
| `--employed-drivers` | tắt | Tài xế không được từ chối cuốc |

## `run`

> Ví dụ `pool_after_wait` dưới đây là của kami 0.1; pooling hiện ngoài phạm vi 0.2 (matching 1 tài xế – 1 khách) nhưng
> lệnh vẫn chạy.

```bash
python -m kami run --preset rain --seed 3 --policy pool_after_wait \
    --arg wait_threshold=300 --arg surcharge=20000 --arg include_matched=true --out out/run1
```

In thông tin kịch bản, cấu hình policy, thời gian chạy và toàn bộ metric. Nếu có `--out`, lệnh ghi thêm
`metrics.json` và `events.csv`. `--arg k=v` tự ép kiểu sang int, float hoặc bool.

### Chạy từ file cấu hình (kami 0.2)

```bash
python -m kami spec --preset rain --policy surge --arg every=60 --out run.json   # cách gọi cũ → spec
python -m kami run --spec run.json --out out/run1                              # chạy, không cần DB
python -m kami run --spec run.json --db kami.db --artifacts runs                # chạy và lưu vào DB
```

| Cờ | Ý nghĩa |
|---|---|
| `--spec` | File RunSpec JSON (docs/engine/18). Không dùng chung với các cờ kịch bản/policy cũ (`--preset`, `--policy`, `--arg`, `--network`…): lệnh báo lỗi và trả mã 2 |
| `--out` | Ghi `metrics.json`, `run_spec.resolved.json`, `timeseries.json` và event log theo `outputs.event_log` (`events.parquet` hoặc `events.csv.gz`) |
| `--db` | Lưu run vào DB SQLite (tạo/migrate nếu cần) và in `run_id`. Bắt buộc khi spec có tham chiếu `{"ref": …}` |
| `--artifacts` | Thư mục file event log của run lưu DB (mặc định `runs/`, file ở `runs/<run_id>/`) |

Spec sai trả mã 2 kèm danh sách trường sai; run thất bại khi chạy (đã có bản ghi `failed`) trả mã 1.

## `spec`

Nhận đúng các cờ của `run` (trừ `--out` là file đích) và in RunSpec tương đương. Chạy spec này bằng
`run --spec` cho metric giống hệt `run` với cùng cờ.

## `db init`

```bash
python -m kami db init --db kami.db      # tạo DB rỗng hoặc áp migration còn thiếu; chạy lại an toàn
```

## `bench`

```bash
python -m kami bench --repeat 5 --out benchmarks/results/<ngày>.json
python -m kami bench --compare benchmarks/results/2026-10-07-sprint01.json
```

| Cờ | Mặc định | Ý nghĩa |
|---|---|---|
| `--suite` | `benchmarks/specs` | Thư mục các case (mỗi file RunSpec là một case) |
| `--cases` | tất cả | Tên case (tên file không đuôi), cách nhau bởi dấu phẩy |
| `--repeat` | 3 | Số lần lặp mỗi case, mỗi lần một tiến trình riêng |
| `--out` | — | Ghi kết quả JSON |
| `--compare` | — | File kết quả mốc; trả mã 1 nếu case chậm hơn hoặc tốn RAM hơn quá ngưỡng |
| `--threshold` | 0,10 | Ngưỡng thoái lui |

Chi tiết ở docs/engine/18 §4.

## `compare`

```bash
python -m kami compare --presets weekday_am_peak,undersupply,rain,accident --seeds 30 --jobs -1 \
    --baseline baseline --treatment pool_after_wait --arg surcharge=20000 \
    --pooling-rule --report out/pool_report.md
```

| Cờ | Ý nghĩa |
|---|---|
| `--presets` | Danh sách preset, cách nhau bởi dấu phẩy |
| `--seeds` | Số replication cho mỗi kịch bản |
| `--baseline`, `--treatment` | Tên policy trong `POLICIES` |
| `--arg` | Tham số cho treatment |
| `--jobs` | Số tiến trình (−1 = mọi CPU) |
| `--no-crn` | Tắt CRN, để so sánh độ rộng CI |
| `--pooling-rule` | Đánh giá quy tắc mẫu ở design doc §10.5 |
| `--report` | Ghi báo cáo Markdown |

Muốn dùng policy tự viết qua CLI: thêm lớp đó vào dict `POLICIES` trong `kami/policy/library.py`.
