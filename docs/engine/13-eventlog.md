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
sim.log.to_jsonl("out/events.jsonl")              # mỗi dòng một object, info được trải phẳng
df = sim.log.to_pandas()                          # cần pandas
sim.log.to_parquet("out/events.parquet")          # cần pandas + pyarrow (design doc §12)
```

`SimConfig(record_events=False)` tắt ghi log. Metric vẫn tính được vì chỉ dựa trên trạng thái agent, và cách này
nhanh hơn khoảng 5% và tiết kiệm RAM khi chạy hàng nghìn replication.

## Dùng event log để

- **Kiểm chứng và gỡ lỗi:** dựng lại timeline của một khách hay một tài xế.
- **Hiệu chỉnh:** so phân bố thời gian chờ và tỷ lệ hủy theo giờ với log thật (`by_hour`).
- **Training:** sinh dữ liệu tổng hợp cho pipeline fit, như trong `examples/04_train_and_register.py`.
- **Trực quan hoá:** `REQUEST_CREATED` (`origin`/`dest`), `IDLE_MOVE` (`origin`/`dest`) và các mốc
  `TRIP_ACCEPTED`/`PICKUP`/`DROPOFF` đủ để dựng animation quỹ đạo (deck.gl `TripsLayer`, kepler.gl).
  Đổi node sang lon/lat bằng `network.lonlat(node)`; lộ trình chi tiết lấy từ `sim.traffic.path(o, d)`
  (mạng FleetPy).
