# 13 · Event log (`kami/eventlog.py`)

Mọi sự kiện engine đã xử lý và mọi hành động của nền tảng được ghi theo đúng thứ tự xử lý vào `sim.log`.

## Định dạng

Mỗi dòng là tuple `(t, event, rider_id, driver_id, info)`:
- `t`: giây, làm tròn 3 chữ số;
- `event`: tên sự kiện (`EventType`) hoặc nhãn hành động (`POOL_OFFER`, `POOL_MERGE`…). Danh mục ở docs/engine/03;
- `rider_id` / `driver_id`: có thể là `None`;
- `info`: dict thông tin bổ sung, ví dụ `{"fare": 64000, "surcharge": 20000, "ivt": 812.4, "pooled": True}`.

## API

```python
sim.log.counts()                                  # {"PICKUP": 958, …}
sim.log.filter(event="RIDER_CANCEL")              # danh sách dòng
sim.log.filter(rider_id=42)                       # toàn bộ lịch sử của một khách
sim.log.to_csv("out/events.csv")                  # cột info dạng JSON
sim.log.to_csv("out/events.csv.gz")               # nén gzip (tự nhận theo đuôi .gz, hoặc compress=True)
sim.log.to_jsonl("out/events.jsonl")              # mỗi dòng một object, info được trải phẳng
df = sim.log.to_pandas()                          # cần pandas
sim.log.to_parquet("out/events.parquet")          # cần pandas + pyarrow (design doc §12), info trải phẳng
sim.log.save("runs/7/events.parquet", "parquet")  # định dạng file của run (docs/engine/18), chỉ cần pyarrow
from kami.eventlog import load
rows = load("runs/7/events.parquet")              # đọc lại .parquet / .csv.gz / .csv thành list tuple
log.subscribe(fn)                                 # fn(t, event, rider_id, driver_id, info) cho mọi dòng
```

## Định dạng file của run (Sprint 01)

`EventLog.save(path, fmt)` là định dạng event log của một lần chạy được lưu (`kami.store`, `run --spec --out`):

- `parquet` (mặc định, cần `pyarrow` — `pip install 'kami[store]'`): ghi theo lô 100.000 dòng, nén zstd;
- `csv.gz`: thư viện chuẩn.

Cả hai có đúng 5 cột `t, event, rider_id, driver_id, info`; `info` là chuỗi JSON (khác `to_parquet`/`to_pandas`
trải phẳng `info` thành cột). Lõi engine không import `pyarrow`: chỉ `save`/`load` import khi được gọi.

## Listener

`EventLog.subscribe(fn)` đăng ký hàm được gọi cho **mọi** dòng, kể cả khi `record_events=False` (khi đó dòng không
được giữ trong bộ nhớ). Bộ thu chuỗi thời gian (docs/engine/18) dùng cơ chế này; Sprint 04/09 sẽ dùng để ghi dần ra
file và stream live. Khi không có listener và không ghi log, `add` không làm gì như 0.1.

`SimConfig(record_events=False)` tắt ghi log. Metric vẫn tính được vì chỉ dựa trên trạng thái agent, và cách này
nhanh hơn khoảng 5% và tiết kiệm RAM khi chạy hàng nghìn replication.

## Dùng event log để

- **Kiểm chứng và gỡ lỗi:** dựng lại timeline của một khách hay một tài xế.
- **Hiệu chỉnh:** so phân bố thời gian chờ và tỷ lệ hủy theo giờ với log thật (`by_hour`).
- **Training:** sinh dữ liệu tổng hợp cho pipeline fit, như trong `examples/04_train_and_register.py`.
- **Trực quan hoá:** các mốc `TRIP_ACCEPTED`/`PICKUP`/`DROPOFF` + quỹ đạo xe. Từ Sprint 02 quỹ đạo không cần dựng
  lại từ log: bật `SimConfig.record_trajectories` (spec: `outputs.trajectories = "parquet"`) để có
  `trajectories.parquet` — lộ trình thật của mọi chặng với thời điểm qua từng điểm, đúng dạng deck.gl `TripsLayer`
  (docs/engine/02, mục "Quỹ đạo"). Event log ghi thời gian làm tròn 3 chữ số thập phân; quỹ đạo giữ thời gian đầy đủ.

## Shared V1 và time-series

Payload Shared là phần bổ sung khi bật V1; log cũ giữ nguyên khi tắt.
SHARED_PAIR_CREATED ghi ids/stops, pickup/dropoff/extra/overlap dự kiến;
SHARED_PAIR_DISSOLVED và SHARED_PARTNER_LOST ghi reason. PICKUP/DROPOFF là các
mốc thực tế để đối chiếu accumulator; timestamp log làm tròn 0,001 giây.
Time-series thêm các khóa shared.* và CSV lấy fieldnames của row; record_events
false vẫn có summary/time-series. Xem [Shared V1](23-shared-rides-v1.md).
