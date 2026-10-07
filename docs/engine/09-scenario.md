# 09 · Kịch bản (`kami/scenario.py`)

## `Scenario` là gì

Một "thế giới" tất định: **phần ngoại sinh** mà baseline và treatment phải gặp y hệt nhau (design doc §2.5, §9).

| Trường | Kiểu | Nội dung |
|---|---|---|
| `name`, `seed` | | Nhận diện và cặp ghép trong `Experiment` |
| `t_start`, `t_end` | giây | Cửa sổ có request. Engine chạy tiếp `drain_s` sau `t_end` |
| `network`, `zones` | | Dùng chung, không copy |
| `requests` | `RequestSpec(id, t, origin, dest, attrs)` | Dòng nhu cầu và thuộc tính cá nhân của khách |
| `drivers` | `DriverSpec(id, loc, shift_start, shift_end, capacity, attrs)` | Nguồn cung, vị trí ban đầu, ca làm |
| `weather` | `[(t, "rain"), …]` | Các lần đổi thời tiết |
| `incidents` | `IncidentSpec(id, t_start, t_end, center, radius_m, factor, cancel_multiplier)` | Sự cố |
| `traffic` | dict | Tham số `TrafficLayer` |
| `tags` | dict | `measure_from` (đầu cửa sổ đo metric, bỏ warm-up), `preset`, `generator`, `source` |

`scenario.summary()` cho bản tóm tắt; `scenario.with_(...)` tạo bản sao có sửa đổi.

**Phần nào thuộc kịch bản, phần nào do mô hình sinh ra:**

| Ngoại sinh (trong `Scenario`) | Nội sinh (do engine và model sinh) |
|---|---|
| Thời điểm, điểm đi/đến của *ý định* gọi xe | Khách có đặt không, có hủy không, có nhận ghép không |
| Thuộc tính cá nhân (kiên nhẫn, độ nhạy giá…) | Tài xế nhận/từ chối cuốc, đi đâu khi rảnh, nghỉ sớm |
| Ca làm, vị trí đầu ca | Vị trí xe sau đó, thời gian chờ, thu nhập |
| Thời tiết, sự cố | ETA thật, sai lệch ETA |

## `ScenarioBuilder`

```python
builder = ScenarioBuilder(network, zones, traffic={...})
```

### Sinh synthetic: `builder.synthetic(...)`

- **Nhu cầu:** Poisson không thuần nhất (thinning). Tốc độ = `demand_per_hour × profile[giờ] ×
  demand_weather_multiplier`. Có `profile` `weekday` (đỉnh 7–9h, 17–19h), `weekend`, hoặc danh sách 24 số tự định.
- **Không gian:** `n_hotspots` cụm Gauss (cụm 0 là trung tâm, trọng số 2), độ rộng `hotspot_sigma_m`. 70% điểm đón
  và 50% điểm đến rơi vào các cụm. Chuyến ngắn hơn `min_trip_m` được rút lại.
- **Nguồn cung:** `n_drivers × supply_multiplier` xe. 70% làm trọn cửa sổ, số còn lại làm một ca 50–90% cửa sổ.
  Vị trí ban đầu lệch về các cụm.
- **Sự cố:** `incidents=[{"t_offset":1800, "duration":3600, "at":"hotspot0" | node, "radius_m":1000, "factor":3.0}]`.
- `warmup_s`: bắt đầu sớm hơn để hệ thống "ấm". Metric chỉ tính từ `t_start` (lưu ở `tags["measure_from"]`).
- RNG là `random.Random("scenario|{name}|{seed}")`: cùng tên và seed thì ra cùng kịch bản.

### Thư viện preset (design doc §9: thư viện kịch bản tối thiểu)

| Preset | Khung giờ | Đặc điểm |
|---|---|---|
| `weekday_am_peak` | 7h–10h | Ngày thường, cao điểm sáng |
| `weekday_pm_peak` | 16h30–19h30 | Cao điểm tối |
| `weekday_offpeak` | 13h–16h | Thấp điểm |
| `weekend` | 10h–14h | Profile cuối tuần |
| `rain` | 16h30–19h30 | Mưa cả buổi: ETA ×1,25, nhu cầu ×1,3, khách thiếu kiên nhẫn hơn |
| `accident` | 7h–10h | Tai nạn tại hotspot chính từ 7h30 đến 8h30, bán kính 1 km, chậm ×3 |
| `undersupply` | 7h–10h | Còn 60% số xe |
| `oversupply` | 13h–16h | Tăng lên 160% số xe |

```python
builder.preset("rain", seed=3, demand_per_hour=200, n_drivers=150)      # mặc định 200 req/h, 150 xe
builder.preset("accident", seed=1, t_end=9 * 3600)                     # ghi đè bất kỳ tham số nào
builder.library(seed=0)                                                # 6 preset chính
```

### Replay dữ liệu

| Hàm | Đầu vào | Ghi chú |
|---|---|---|
| `from_fleetpy_demand(csv, n_drivers, …)` | File demand FleetPy `rq_time,start,end,request_id` (node của cùng mạng FleetPy) | Dùng lại demand mẫu của FleetPy |
| `from_csv(path, time_col, origin, dest, coords)` | Đơn lịch sử. `coords`: `"xy"` (m, CRS của mạng), `"node"`, hoặc `"lonlat"` (chuyển qua `pyproj` theo `crs.info` của FleetPy) | Điểm được gán về `nearest_node` |

Với replay, thuộc tính cá nhân vẫn rút từ phân phối (mức 2 của design doc). Muốn dùng thuộc tính theo từng người
(mức 3): sửa `RequestSpec.attrs` sau khi tạo.

**Lưu ý quan trọng (design doc §5, §9):** replay chỉ đúng cho phần **ngoại sinh**. Không replay trạng thái "đã hủy"
hay "tài xế đi đâu" từ lịch sử, vì các thứ đó thay đổi khi policy thay đổi.

## Hiệu chỉnh baseline

Trước khi đánh giá policy, baseline phải tái tạo được lịch sử (design doc §11):
- dùng `kami.metrics.by_hour(sim)` và `by_zone(sim)` để so thời gian chờ, tỷ lệ hủy, số chuyến theo giờ và khu
  với số thật;
- chỉnh `demand_per_hour`, `n_drivers`, profile và tham số behavior cho tới khi khớp **phân bố**, không cần khớp
  từng cá nhân.
