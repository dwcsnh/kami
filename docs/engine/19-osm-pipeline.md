# 19 · Pipeline OSM → mạng Hà Nội (`kami/osm/`)

Công cụ **lúc build** (Sprint 02, S02-1/S02-3): tạo mạng đường định dạng FleetPy + hệ zone từ một file OSM có ghi
phiên bản. Engine không import gói này; mạng tạo ra được `RoadNetwork` / `FileZoneSystem` đọc bằng thư viện chuẩn.

```bash
pip install -e ".[osm]"                     # osmium (pyosmium), pyproj, h3 — chỉ cần để build
python -m kami.osm build hanoi              # tải PBF nếu chưa có (kiểm sha256) → data/networks/hanoi, data/zones/hanoi_*
python -m kami.osm check hanoi              # S02-2: kích thước mạng, tỷ lệ có đường, thời gian truy vấn, C++ vs Python
python -m kami.osm fetch hanoi              # chỉ tải + kiểm sha256
```

`hanoi` là `data/osm/hanoi.json`; có thể truyền đường dẫn một file cấu hình khác và `--data-root` cho thư mục ra.
Dữ liệu sinh ra **không commit** (`.gitignore`): tạo lại bằng lệnh trên. Một lần build Hà Nội mất khoảng 95 s và
1,6 GB RAM (đọc hai lượt file PBF Việt Nam, mỗi lượt ≈ 60 s).

## Dữ liệu nguồn

| | |
|---|---|
| File | `vietnam-261006.osm.pbf` của Geofabrik (bản ngày 2026-10-06, 330 MB), cache ở `data/osm/cache/` |
| sha256 | `121ba51ac35afa6a5f662d4e63c1798273333b940386a153cc914974de92795b` (ghi trong `data/osm/hanoi.json`) |
| Giấy phép | © OpenStreetMap contributors, **ODbL 1.0** — mạng, zone và mọi sản phẩm phái sinh phải ghi nguồn OSM; chia sẻ cơ sở dữ liệu phái sinh theo cùng giấy phép |
| Phạm vi | `data/osm/hanoi_area.geojson`: đa giác xấp xỉ 12 quận nội thành cũ (Ba Đình, Hoàn Kiếm, Tây Hồ, Long Biên, Cầu Giấy, Đống Đa, Hai Bà Trưng, Hoàng Mai, Thanh Xuân, Nam Từ Liêm, Bắc Từ Liêm, Hà Đông), bbox lon 105,720–105,945, lat 20,933–21,100, **353 km²** |

`fetch` từ chối build nếu sha256 của file khác cấu hình: cùng phiên bản dữ liệu luôn cho cùng mạng. Geofabrik không
giữ file theo ngày mãi mãi — muốn tái tạo đúng từng byte cần giữ file PBF đã cache. Đổi phạm vi = sửa polygon, không
sửa code.

## Các bước

1. **Đọc** (`extract.py`, pyosmium, hai lượt): way `highway` thuộc loại giữ lại có ít nhất một node trong bbox (+0,02°);
   toà nhà và POI trong bbox; quan hệ `boundary=administrative` có `admin_level` cấu hình (lượt 2 lấy hình học các
   way thành viên trong bbox + 0,12°, ghép thành vòng khép kín).
2. **Lọc loại đường** (quyết định D3): giữ `motorway, trunk, primary, secondary, tertiary` (+ `_link`),
   `unclassified, residential, living_street`. Bỏ `service`, `track`, `path`, `footway`, `cycleway`, `construction`,
   `area=yes` và way không xe cơ giới nào được đi (`access`/`motor_vehicle` = `no`, `private`…; 218 way).
3. **Quyền theo nhóm xe** (D7): tag cụ thể nhất thắng — `access` < `motor_vehicle` < `motorcar` / `motorcycle`.
   Hà Nội: 5.190 cạnh cấm ô tô (gần hết là ngõ `motorcar=no` + `motorcycle=yes`), 214 cạnh cấm xe máy (cao tốc, đường
   trên cao, một số cầu).
4. **Cắt theo polygon**: mỗi way tách thành các đoạn node liên tiếp nằm trong polygon.
5. **Tách tại node quan trọng** (D4): node dùng chung bởi nhiều way hoặc đầu mút đoạn. Mỗi đoạn → cạnh có hướng theo
   `oneway` (`yes`/`-1`; `junction=roundabout` và `motorway` mặc định một chiều; `reversible` bị bỏ). Cạnh song song
   hoặc vòng (định dạng FleetPy không biểu diễn được) được tách tại node OSM ở giữa; không có node giữa thì giữ cạnh
   nhanh hơn.
6. **Gộp chuỗi bậc 2**: node chỉ nối hai hàng xóm, các cạnh qua nó cùng thuộc tính (loại đường, quyền đi, tốc độ) →
   gộp thành một cạnh; hình học đầy đủ giữ trong `edge_geometry.csv`.
7. **Thành phần liên thông mạnh lớn nhất** của đồ thị ô tô ∪ xe máy (Tarjan lặp). Node ngoài bị bỏ.
8. **Đánh số lại** node theo id OSM (`0..N−1`), sắp cạnh theo `(from, to)`, chiếu sang **UTM 48N** (`EPSG:32648`)
   bằng `pyproj`. Số ghi với độ chính xác cố định: hai lần build cùng đầu vào cho file **giống hệt từng byte** (có
   test trên fixture).
9. **Zone** (D8, `zones.py`): H3 độ phân giải 8 (`h3.latlng_to_cell`) và đơn vị hành chính `admin_level=6`
   (point-in-polygon thuần Python, index lưới 0,01°). Node rơi ngoài mọi polygon nhận zone của node gần nhất.
10. **Trọng số zone** (D15): đếm toà nhà ở (`building=yes/house/residential/apartments…`), nơi làm việc
    (`office=*`, trường học, bệnh viện, toà nhà thương mại/công nghiệp…) và POI khác (`amenity`, `shop`) trong mỗi zone.

## Tốc độ free-flow (giả định, D6)

Travel time = độ dài (haversine dọc polyline) / tốc độ. Tốc độ theo bảng mặc định của loại đường (ô tô, nội đô,
km/h); tag `maxspeed` (18,6% cạnh có) chỉ được dùng khi **thấp hơn** bảng — `maxspeed` là giới hạn pháp lý, cao hơn
tốc độ thực tế nội đô (xem "Lịch sử thay đổi" của plan Sprint 02). Bảng ghi trong `manifest.json`.

| motorway | trunk | primary | secondary | tertiary | unclassified | residential | living_street | `_link` |
|---|---|---|---|---|---|---|---|---|
| 70 | 50 | 40 | 35 | 30 | 25 | 20 | 10 | motorway 40, trunk 35, primary 30, secondary/tertiary 25 |

Xe máy: `speed_factor` 0,9 so với ô tô (docs/engine/08). Các số này **chưa hiệu chỉnh** bằng GPS.

## File đầu ra

```
data/networks/hanoi/
  base/nodes.csv              node_index,is_stop_only,pos_x,pos_y,lon,lat,osm_id
  base/edges.csv              from_node,to_node,distance,travel_time,source_edge_id (= id way OSM)
  base/edge_attributes.csv    from_node,to_node,road_class,allow_car,allow_bike,speed_kmh,maxspeed_tag
  base/edge_geometry.csv      from_node,to_node,lons,lats
  base/crs.info               EPSG:32648
  manifest.json               phiên bản dữ liệu (PBF, ngày, sha256, pipeline_version), số liệu, bảng tốc độ
data/zones/hanoi_h3_r8/hanoi/ node_zone_info.csv, zone_definitions.csv, zone_weights.csv
data/zones/hanoi_wards/hanoi/ (như trên)
```

Định dạng các phần mở rộng: docs/engine/16.

## Số liệu mạng Hà Nội (build 2026-10-07)

| | |
|---|---|
| Way giữ lại / cắt trong polygon | 39.797 / 25.915 |
| Cạnh sau tách → sau gộp | 79.225 → 71.549 |
| Node sau tách → sau gộp | 34.827 → 29.984 |
| **Mạng cuối** (SCC 96,7% số node sau gộp) | **28.983 node, 70.186 cạnh có hướng, 6.312 km cạnh** |
| Cạnh theo loại | residential 52.238, tertiary 7.863, primary 3.651, secondary 3.121, trunk 742, motorway 83, … |
| SCC theo nhóm xe | ô tô 93,1%, xe máy 99,5% số node |
| `location_nodes` (tới được bằng **mọi** nhóm) | 26.845 (92,6%) |
| Zone H3 r8 | 452 ô, 1–221 node/ô (trung vị 58) |
| Phường/xã (sau sắp xếp 2025) | 60 (68 ranh giới chạm vùng; trung vị 373 node/zone), 0 node ngoài polygon |
| Toà nhà ở / nơi làm việc / POI | 131.775 / 6.736 / 14.191 |

**Router** (`python -m kami.osm check hanoi`, 1.000 cặp OD ngẫu nhiên trong `location_nodes`, môi trường mốc):

| | |
|---|---|
| Nạp mạng | Python 0,76 s, C++ 0,95 s; RAM tiến trình ≈ 160 MB |
| Tỷ lệ cặp có đường | 100% |
| C++ 1→1 | trung bình 1,90 ms, p95 4,51 ms |
| C++ X→1 (12 điểm, bán kính 900 s — truy vấn của matching) | trung bình 1,84 ms |
| Python 1→1 | 27,2 ms (≈ 14× chậm hơn) |
| Lộ trình C++ = Python | 200/200 cặp |
| Thời gian free-flow giữa hai điểm ngẫu nhiên | trung vị 19,6 phút, tối đa 46,9 phút |

## Fixture cho test

`tests/data/osm/hoan_kiem.osm.pbf` (310 KB, ~1,6 km² quanh Hồ Gươm, cắt từ cùng file Việt Nam bằng
`tests/data/osm/make_fixture.py`) + `hoan_kiem.json`. Một way (Phố Đinh Tiên Hoàng) được thêm `motorcycle=no` giả lập
để test cạnh cấm xe máy — thay đổi duy nhất so với dữ liệu OSM. Fixture build ra 220 node, 479 cạnh, 7 ô H3, 3 phường (5 ranh giới chạm vùng).
Test cần `osmium`, `pyproj`, `h3`; thiếu thì tự bỏ qua. Test trên mạng Hà Nội đầy đủ chỉ chạy khi đã build.
