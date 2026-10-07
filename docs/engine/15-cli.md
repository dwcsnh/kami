# 15 · CLI (`kami/cli.py`)

Chạy từ thư mục `kami/`, hoặc cài bằng `pip install -e .` để có lệnh `kami`.

```bash
python -m kami presets        # liệt kê preset kịch bản và policy đã đăng ký
python -m kami run [...]      # một lần chạy
python -m kami compare [...]  # thí nghiệm cặp baseline vs treatment với CRN
```

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
