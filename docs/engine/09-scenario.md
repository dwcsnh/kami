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
- **Sự cố:** `incidents=[{"t_offset":1800, "duration":3600, "at":"hotspot0" | node | {"lon":…, "lat":…},
  "radius_m":1000, "factor":3.0}]`. Vị trí lon/lat (Sprint 02) được gán về location node gần nhất
  (`builder.node_at_lonlat`; mạng cần lon/lat).
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

### Demand theo zone × giờ: `builder.zonal(...)` (Sprint 02, quyết định D15)

Nguồn demand cho mạng thật, thay hotspot ngẫu nhiên bằng trọng số không gian của từng zone:

- **Thời gian:** như `synthetic` (Poisson không thuần nhất, `demand_per_hour × profile[giờ] ×
  demand_weather_multiplier`).
- **Điểm đón:** zone rút theo trọng số `count + smoothing × nodes`, trong đó `count` là số **toà nhà ở** trong cao điểm
  sáng (`am_hours`, mặc định 6–10h), số **nơi làm việc** trong cao điểm chiều (`pm_hours`, 16–20h), tổng nhà ở + nơi
  làm việc + POI ở giờ khác. Node rút đều trong các location node của zone.
- **Điểm đến:** mô hình trọng lực: trọng số "ngược" của khung giờ (sáng: nơi làm việc; chiều: nhà ở) ×
  `exp(−khoảng_cách_tâm_zone / gravity_lambda_m)` (mặc định λ = 3 km). Chuyến ngắn hơn `min_trip_m` được rút lại.
- **Nguồn cung:** vị trí đầu ca rút theo nhà ở + POI; ca làm như `synthetic`.
- `weights`: `{zone: {"nodes","residential","work","poi"}}` — `read_zone_weights(path)` đọc `zone_weights.csv` của
  pipeline OSM. Không có thì mọi zone theo số node.
- RNG là `random.Random("zonal|{name}|{seed}")`.
- `area` (Sprint 03): khung `[lon0, lat0, lon1, lat1]` (lưới không có lon/lat: toạ độ x/y của mạng). Chỉ các zone có
  **trung bình toạ độ các location node** nằm trong khung mới sinh request và vị trí đầu ca; xe vẫn chạy trên toàn mạng
  (đi rảnh, đón/trả ở biên). Không khai báo → như cũ (cùng kết quả).

Trọng số mặc định của Hà Nội đếm từ OSM trong mỗi ô H3 (131.775 toà nhà ở, 6.736 nơi làm việc, 14.191 POI). Đây là
**xấp xỉ** khi chưa có dữ liệu chuyến thật (requirements Q4), chưa hiệu chỉnh.

### Kịch bản Hà Nội (`scenarios/hanoi/`, Sprint 02, quyết định D16)

File RunSpec chạy bằng `python -m kami run --spec scenarios/hanoi/<tên>.json` (`python -m kami presets` liệt kê). Cần
mạng `hanoi` đã build (`python -m kami.osm build hanoi`, docs/engine/19). Mọi file dùng zone `hanoi_h3_r8`, tắc đường
zone × giờ mặc định, nhóm xe `car` + `bike`, nguồn `zonal`.

`demo_center.json` (Sprint 03) là kịch bản của fixture visualizer: khu vực Hoàn Kiếm, Ba Đình, Đống Đa, Hai Bà Trưng
(`area.bbox` = [105,80, 20,995, 105,87, 21,050], ≈ 44 km²), 7h–9h, 750 request/giờ × profile (≈ 2.900 request), 200 ô
tô + 100 xe máy, chuỗi metric mỗi 60 s, `drain_s` 1.800, `outputs.replay = "json"`. Sinh fixture:
`python -m kami replay demo` (docs/engine/20).

| File | Khung giờ | Demand | Xe (ô tô + xe máy) | Đặc điểm |
|---|---|---|---|---|
| `am_peak.json` | 6h–10h | ≈ 15.200 request | 1.000 + 500 | Preset nghiệm thu AC02-8; ghi quỹ đạo (`outputs.trajectories`) |
| `weekday.json` | 0h–24h | ≈ 100.000 request | 5.000 + 3.000 | Cả ngày; chạy đầy đủ từ Sprint 04 (hiệu năng) |
| `pm_peak_rain.json` | 16h–20h | ≈ 15.200 × 1,3 | 1.000 + 500 | Mưa từ 16h30 |
| `incident_arterial.json` | 16h–20h | ≈ 15.200 request | 1.000 + 500 | Sự cố ngã tư Nguyễn Trãi – Khuất Duy Tiến 17h30–18h30, bán kính 800 m, chậm ×2,5 |

Kết quả `am_peak` (seed 0, router C++, môi trường mốc): 105.834 sự kiện trong 125 s, tỷ lệ hoàn thành 0,90, chờ
trung bình 4,9 phút, 1,93 chuyến/xe-giờ — số liệu đầy đủ ở backlog Sprint 02.

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
