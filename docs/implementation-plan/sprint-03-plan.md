# Implementation plan — Sprint 03: Bản đồ vận hành (fleet operation visualizer) trên web

| | |
|---|---|
| Sprint | [sprint-03-map-visualizer.md](../sprint/sprint-03-map-visualizer.md) |
| Backlog đầu vào | [sprint-02-backlog.md](../backlog/sprint-02-backlog.md) — xử lý trong plan này: **B02-9** (dung lượng quỹ đạo → định dạng phát lại theo khu vực + giản lược điểm), **B02-11** (đo lại mốc benchmark trên commit sạch `0e4e0d0`). Các mục B02 khác thuộc sprint 04/05 hoặc chưa xếp. Mốc benchmark: `benchmarks/results/2026-10-07-sprint02.json` |
| Trạng thái | Đã thực hiện (duyệt 2026-10-08) |

## 1. Tóm tắt hướng tiếp cận

Ba phần, nối với nhau bằng một **hợp đồng dữ liệu** có phiên bản (`kami.replay` v1):

```
 (A) Python — kami/replay/ (không nằm trong lõi engine)          (B) Web — web/ (Next.js + TypeScript)    
 ┌───────────────────────────────────────────────┐              ┌──────────────────────────────────────────────┐
 │ run engine (record_trajectories, timeseries)  │              │ Mapbox GL JS (nền sáng) + deck.gl overlay    │
 │  → dòng thời gian trạng thái từng xe          │   replay/    │  • xe di chuyển: IconLayer (vị trí nội suy)  │
 │    (legs + khoảng đứng yên)                   │──manifest───▶│    + TripsLayer (vệt mờ dần theo trạng thái) │
 │  → giản lược điểm (≤ 1 m, ≤ 0,5 s)            │  vehicles    │  • quỹ đạo: TripsLayer vệt dài = tích luỹ    │
 │  → events (đón/trả/hủy), metrics (60 s)       │  trips       │  • panel: KPI, biểu đồ ECharts, chú giải/    │
 │  → validate()  — cùng seed → cùng byte        │  events      │    công tắc, điều khiển phát lại, chi tiết xe│
 │ python -m kami replay demo|export|validate    │  metrics     │  • design tokens (Tiffany, light mode)       │
 └───────────────────────────────────────────────┘              └──────────────────────────────────────────────┘
 (C) Fixture demo: scenarios/hanoi/demo_center.json → web/public/fixtures/hanoi_center_demo/ (commit, gzip ~1–3 MB)
```

- Lõi engine không đổi hành vi; chỉ thêm hai trường **tuỳ chọn** (vùng giới hạn của nguồn `zonal`, một cột chuỗi
  thời gian) — kịch bản cũ cho kết quả giống hệt (AC03-9).
- Visualizer chỉ **phát lại từ file** (không backend). Sprint 08 trả đúng các file/khối JSON này qua API; Sprint 09
  ghép trang này vào ứng dụng quản lý và dùng lại design tokens + thành phần.

## 2. Quyết định kỹ thuật

| # | Quyết định | Phương án đã cân nhắc | Lý do chọn |
|---|---|---|---|
| D1 | **Frontend (requirements Q5): Next.js (App Router) + React + TypeScript** — người dùng chốt Q-A. Thư mục `web/` ở gốc repo (Node ≥ 20; máy dev có Node 24). Sprint này build tĩnh (`output: "export"`, không backend); trang bản đồ là client component, Mapbox/deck.gl nạp bằng `next/dynamic` với `ssr: false`. State bằng Zustand. Test logic bằng Vitest | React + Vite (đề xuất ban đầu); Svelte/SvelteKit; Vue 3; HTML + JS thuần | Sprint 09 là ứng dụng nhiều trang (kịch bản, fleet, policy, metric): React có hệ sinh thái lớn nhất cho form/bảng/router và binding chính thức của deck.gl. TypeScript giữ hợp đồng dữ liệu kiểu tĩnh. JS thuần không mở rộng được cho Sprint 09 |
| D2 | **Bản đồ: Mapbox GL JS v3** (nền, camera, zoom/xoay/nghiêng) + **deck.gl v9 qua `MapboxOverlay`** (chế độ interleaved) cho các lớp xe | Chỉ dùng layer của Mapbox (line-gradient, symbol); Kepler.gl | `TripsLayer` của deck.gl làm đúng "vệt đường chạy mờ dần theo thời gian" trên GPU (một buffer cho mọi xe, chỉ đổi `currentTime` mỗi khung hình) — mượt với hàng nghìn xe (Sprint 04). Layer Mapbox phải dựng lại GeoJSON mỗi khung. Kepler.gl là ứng dụng hoàn chỉnh, khó áp design tokens riêng |
| D3 | **Biểu đồ: Apache ECharts 5** (import theo module, `echarts/core`), theme sinh từ design tokens | uPlot; Recharts; Chart.js | Cần cột (đơn theo khung giờ), miền xếp chồng (tỷ lệ trạng thái xe), đường (thời gian chờ/đón), đường kẻ thời điểm đang xem — ECharts có đủ, có theme, nhanh với vài nghìn điểm. uPlot nhẹ nhưng cột/miền xếp chồng thủ công; Recharts chậm khi cập nhật liên tục |
| D4 | **Định dạng phát lại `kami.replay` v1 = một thư mục JSON** (`manifest.json`, `vehicles.json`, `trips.json`, `events.json`, `metrics.json`), mỗi file có thể nén `.json.gz`. Toạ độ 6 chữ số thập phân (~0,1 m), thời gian giây kể từ 0h, 1 chữ số thập phân. Chi tiết ở §2.1 | Parquet + đọc bằng parquet-wasm/Arrow trong trình duyệt; một file JSON duy nhất; định dạng nhị phân riêng | JSON đọc thẳng được trong trình duyệt, dễ kiểm tra, dễ trả qua API REST ở Sprint 08 (mỗi file = một endpoint). Arrow/Parquet thêm ~2 MB WASM và phức tạp cho quy mô vài trăm xe; xem lại ở Sprint 04 nếu 8k xe cần định dạng nhị phân (ghi vào backlog nếu cần) |
| D5 | **Dòng thời gian trạng thái xe** dựng trong Python từ quỹ đạo Sprint 02: mỗi chặng → một *segment* có trạng thái; khoảng hở giữa hai chặng → segment đứng yên (một điểm). Trạng thái: `idle` (rảnh, đứng yên), `cruising` (rảnh, đang chạy — `IdleMoveModel`), `pickup` (đi đón), `on_trip` (chở khách, gồm lúc khách lên/xuống), `reposition` (nền tảng điều xe). Danh sách trạng thái nằm trong `manifest.states` (id, nhãn, khoá màu) — Sprint 05 thêm `to_charger`/`charging` **không** phải tăng `schema_version` | Tính trạng thái trong trình duyệt từ event log | Một nguồn sự thật, kiểm tra tự động được bằng Python (AC03-3); trình duyệt chỉ tra cứu |
| D6 | **Giản lược điểm (S03-2):** bỏ điểm trùng; bỏ điểm `p_i` khi khoảng cách tới đoạn `p_{i−1}p_{i+1}` ≤ **1 m** **và** thời gian lệch so với nội suy tuyến tính ≤ **0,5 s** (giản lược trong không gian–thời gian, lặp kiểu Douglas–Peucker). Luôn giữ điểm đầu/cuối segment | Douglas–Peucker chỉ theo không gian; giữ mọi điểm | Trình duyệt nội suy tuyến tính theo cả vị trí lẫn thời gian, nên bỏ điểm chỉ theo không gian làm xe chạy sai nhịp. Ngưỡng 1 m giữ xe trên đường (độ rộng làn ~3 m); có test đo độ lệch lớn nhất |
| D7 | **Fixture demo `hanoi_center_demo`:** kịch bản `scenarios/hanoi/demo_center.json` — khu vực **Hoàn Kiếm, Ba Đình, Đống Đa, Hai Bà Trưng** (bbox lon 105,80–105,87, lat 20,995–21,050, ≈ 44 km²), **7h00–9h00** (cao điểm sáng), **300 xe** (200 ô tô + 100 xe máy), demand ≈ 2.000 request (chỉnh `demand_per_hour` để tỷ lệ hoàn thành ~0,85), tắc đường zone × giờ, seed 0, chuỗi metric mỗi **60 s**. Request và vị trí đầu ca giới hạn trong khu vực bằng trường mới `zonal.area` (zone có tâm trong bbox); xe vẫn chạy trên toàn mạng | Chạy cả Hà Nội rồi cắt vùng; khu vực nhỏ hơn (chỉ Hoàn Kiếm) | Đủ "đông" để thấy vệt dày ở trung tâm mà vẫn nhìn rõ từng xe; giới hạn ngay từ kịch bản giữ fixture nhỏ và nhất quán (không có xe "biến mất" ở biên) |
| D8 | **Fixture được commit** ở `web/public/fixtures/hanoi_center_demo/` (dạng `.json.gz`, dự kiến 1–3 MB) để mở web không cần build mạng Hà Nội. `python -m kami replay demo` sinh lại; chạy hai lần → **cùng byte** (JSON khoá sắp xếp, số làm tròn cố định, gzip `mtime=0`, không ghi thời điểm tạo) | Chỉ sinh lại bằng lệnh (không commit) | Mạng Hà Nội không commit (Sprint 02) nên người xem demo cần file sẵn; vài MB chấp nhận được |
| D9 | **Design tokens** một nguồn: `web/src/design/tokens.json` → sinh `tokens.css` (CSS custom properties) và `tokens.ts` (deck.gl/ECharts cần RGB). Thành phần cơ bản viết tay bằng React + CSS Modules (Panel, Button, IconButton, Toggle, Segmented, KpiCard, Slider/Timeline, Legend, Tooltip) trong `web/src/ui/` để Sprint 09 dùng lại | Tailwind; thư viện UI (MUI, Mantine) | Ít phụ thuộc, khớp đúng tokens; thư viện UI kéo theo phong cách riêng khó đưa về Tiffany/light. Có thể đổi sang thư viện ở Sprint 09 nếu cần form phức tạp (giữ tokens) |
| D10 | **Màu chủ đạo Tiffany** (đã kiểm tương phản WCAG): `brand-500 #0ABAB5` cho nhấn, viền đang chọn, đường biểu đồ chính, nền nút nhạt; **`brand-700 #077C79`** cho nền nút chính với chữ trắng (5,0 : 1) và chữ/liên kết trên nền trắng; `brand-50 #E6F7F6` nền chọn nhạt. Chữ chính `#1F2933` (14,8 : 1 trên trắng), chữ phụ `#52606D` (6,5 : 1). Thang đầy đủ 50…900 trong tokens | Dùng `#0ABAB5` cho cả nút có chữ trắng | `#0ABAB5` với chữ trắng chỉ 2,4 : 1 — trượt AA; giữ đúng sắc Tiffany ở vai trò nhấn, dùng sắc đậm hơn khi có chữ |
| D11 | **Bản đồ nền:** style `mapbox://styles/mapbox/light-v11`, chỉnh lúc chạy: giảm bão hoà, nước pha sắc `brand-50`, ẩn POI/nhãn phụ, giữ tên phố mờ. **Không có khối nhà 3D** (Q-C: nhà 3D che vệt xe) — light-v11 vốn không có lớp `fill-extrusion`; lớp mặt bằng nhà 2D làm rất mờ hoặc ẩn. **Nghiêng/xoay** là tính năng sẵn có của Mapbox GL, không cần dữ liệu hay style riêng: bật mặc định (chuột phải/Ctrl + kéo, hai ngón trên touchpad), `NavigationControl` (la bàn: nhấp = về hướng bắc), nút 2D/3D chuyển `pitch` 0° ↔ 50°; giới hạn `maxPitch` 60° (nghiêng quá làm vệt xa bị dồn, khó đọc). **Zoom** sẵn có: cuộn chuột/chụm hai ngón, nhấp đúp, nút +/− của `NavigationControl`, phím `+`/`−`; giới hạn `minZoom` 10 (ra ngoài Hà Nội không có dữ liệu) – `maxZoom` 18 (nền không thêm chi tiết); độ dày vệt và cỡ biểu tượng xe co giãn theo zoom. Các lớp deck.gl qua `MapboxOverlay` tự theo camera nên xe, vệt, picking (nhấp chọn xe) vẫn đúng khi nghiêng/xoay | Mapbox Standard (`theme: monochrome`, có nhà 3D sẵn); tự làm style trong Mapbox Studio | light-v11 đã gần đúng yêu cầu "sáng, ít chi tiết", chỉnh được bằng code (không cần tài khoản Studio của người dùng). Standard đẹp khi nghiêng nhưng nặng hơn, có nhà 3D che vệt |
| D12 | **Bảng màu trạng thái — hai phương án** (đều ≥ 3 : 1 so với nền đất của bản đồ `#F3F4F2`, WCAG 1.4.11), chọn sau khi xem ảnh chụp trên bản đồ thật ở mốc kiểm tra đầu (§4, S03-6): **A** idle `#7A7F87` · cruising `#C77700` · pickup `#3B5BDB` · on_trip `#D6336C` · reposition `#7048E8`; **B** (theo bảng màu thân thiện mù màu của Paul Tol, làm đậm cho nền sáng) idle `#7A7F87` · cruising `#C77700` · pickup `#0077BB` · on_trip `#CC3311` · reposition `#AA3377`. Không dùng xanh lục/xanh ngọc để tránh lẫn với Tiffany. Chú giải luôn có nhãn chữ + số xe; vệt `on_trip` dày hơn | Một bảng màu cố định | Sprint yêu cầu thử trên nền thật và cho người dùng chọn |
| D13 | **Vị trí xe tại thời điểm `t`** tính trên CPU mỗi khung hình: mỗi xe tìm segment chứa `t` bằng tìm kiếm nhị phân (con trỏ tăng dần khi đang phát), nội suy tuyến tính giữa hai điểm; hướng xe theo đoạn hiện tại. Vệt: `TripsLayer` với `trailLength` 180 s mô phỏng (chế độ "xe di chuyển") hoặc toàn khung giờ (chế độ "quỹ đạo"); bật/tắt theo trạng thái bằng lọc dữ liệu theo nhóm (một layer mỗi trạng thái) | Tính vị trí trên GPU | 300 xe × tìm nhị phân là không đáng kể; cần vị trí trên CPU cho picking/tooltip và đếm số xe theo trạng thái |
| D14 | **Panel metric:** KPI và biểu đồ đọc **chuỗi metric của engine** (`metrics.json` = `sim.timeseries` mỗi 60 s), hiển thị dòng cuối có `t ≤ thời điểm đang xem` (đúng định nghĩa snapshot của S01-6); biểu đồ chỉ vẽ dữ liệu tới thời điểm đang xem. Số xe theo trạng thái (chú giải, biểu đồ tỷ lệ) tính từ dòng thời gian trạng thái của replay — khớp với màu trên bản đồ. Thêm cột `rider.pickup_mean` vào chuỗi metric (thời gian từ lúc nhận chuyến tới lúc đón, phút) để có KPI "thời gian đón TB"; "thời gian chờ TB" = `rider.wait_mean` hiện có | Tính KPI trong trình duyệt từ events | AC03-5 yêu cầu khớp chuỗi metric engine xuất; thêm cột chỉ là đọc thêm sự kiện `TRIP_ACCEPTED` (bộ thu không đổi kết quả mô phỏng) |
| D15 | **Mapbox token** đọc từ `web/.env.local` (người dùng đã đặt; tên biến chuẩn `NEXT_PUBLIC_MAPBOX_TOKEN` — Next.js chỉ đưa biến có tiền tố `NEXT_PUBLIC_` ra trình duyệt; nếu file dùng tên khác, `next.config` ánh xạ sang; `.env.local` đã có trong `.gitignore`), commit `web/.env.example`. Thiếu token → màn hình hướng dẫn cấu hình (không lỗi trắng). Dùng **token public (`pk.`) giới hạn URL** cho demo | Nhập token qua ô trên trang | Đúng yêu cầu không commit token; token public là loại Mapbox thiết kế cho trình duyệt |
| D16 | **Hiệu năng (AC03-6), chốt con số:** trên máy dev (Ryzen 9 6900HS, GPU Radeon 680M tích hợp), Chrome, cửa sổ 1920×1080, fixture 300 xe, phát 60×: **trung vị ≥ 55 fps và phân vị 5% ≥ 30 fps** trong 60 s, ở 3 mức thu phóng (toàn khu vực zoom 12, quận zoom 14, phố zoom 16 nghiêng 60°). Đo bằng bộ đếm khung hình tích hợp (`?debug=1`, ghi `requestAnimationFrame` delta) | Chỉ "≥ 30 fps" trung bình | Trung bình che giấu giật; p5 bắt được khung hình chậm |
| D17 | **Tài liệu:** `docs/engine/20-visualizer.md` (sprint ghi `19-visualizer.md` nhưng số 19 đã dùng cho pipeline OSM ở Sprint 02) | Đổi tên file 19 cũ | Giữ link của Sprint 02 |
| D18 | **Spec (thêm, không tăng `schema_version`):** `ZonalSourceSpec.area` (`{"bbox": [lon0, lat0, lon1, lat1]}`), `outputs.replay` (`"none"` \| `"json"`) để `run --spec --out` ghi thư mục replay. Không khai báo → hành vi cũ | Lệnh export riêng chỉ đọc từ thư mục run | Một run lưu DB (Sprint 08) cần cùng cơ chế sinh artifact |

### 2.1 Hợp đồng dữ liệu `kami.replay` v1 (tóm tắt — đầy đủ trong docs/engine/20)

| File | Nội dung |
|---|---|
| `manifest.json` | `schema_version: 1`, `kind: "kami.replay"`, `kami_version`, `run` (tên, kịch bản, seed, crn_seed, policy, mạng, sha256 của RunSpec đã giải), `area` (tên, `bbox`, `center`, `zoom`), `time` (`start`, `end` — giây từ 0h), `states` (`[{id, label, color}]` — `color` là khoá token), `fleets`, `counts` (xe, segment, sự kiện), `files` (tên file + sha256 + nén), `simplify` (ngưỡng đã dùng) |
| `vehicles.json` | `[{id, fleet, vehicle_type, group, seats, shift: [t0, t1]}]` |
| `trips.json` | Segment theo cột, sắp theo (xe, t): `{vehicle: [...], state: [...], rider: [...], t0, t1, dist_m, path: [[lon, lat, …phẳng]], ts: [[…]]}` — path phẳng `lon, lat` xen kẽ, `ts` cùng độ dài ÷ 2. Segment đứng yên có một điểm |
| `events.json` | `{t, type: request \| booked \| matched \| pickup \| dropoff \| cancel \| declined, rider, vehicle, lon, lat}` theo cột |
| `metrics.json` | `{interval_s, t: [...], series: {tên: [...]}}` — đúng các cột của `sim.timeseries` (NaN → `null`) |

`kami.replay.validate(path) → list lỗi` (thư viện chuẩn): đủ file, sha256 khớp, `schema_version` hỗ trợ, độ dài mảng
nhất quán, thời gian không giảm trong và giữa các segment của một xe, segment kề nhau nối tiếp (điểm cuối = điểm đầu),
trạng thái thuộc `manifest.states`, toạ độ trong bbox mở rộng của mạng. Trường lạ được bỏ qua (tương thích tiến);
phiên bản lớn hơn → lỗi rõ ràng.

### Câu hỏi mở — đã chốt (2026-10-08)

- **Q-A:** Next.js thay cho React + Vite (D1); deck.gl + ECharts giữ nguyên.
- **Q-B:** token public Mapbox người dùng đã đặt ở `web/.env.local` (D15).
- **Q-C:** theo đề xuất — `light-v11` chỉnh bằng code; **không** hiện nhà 3D (che vệt xe); vẫn nghiêng/xoay được (D11).
  Nghiêng không cần code/config đáng kể (vài dòng cấu hình + nút 2D/3D) và không ảnh hưởng tính năng: xe, vệt,
  chọn xe, tooltip vẫn đúng vì deck.gl dùng chung camera với Mapbox. Ảnh hưởng duy nhất: ở góc nghiêng lớn, phần xa
  hiển thị nhiều đường hơn nên tốn GPU hơn — đã nằm trong mức đo AC03-6 (zoom 16, nghiêng 60°, D16).
- **Q-D:** gửi ảnh chụp cả hai bảng màu ở mốc kiểm tra S03-6, người dùng chọn.
- **Q-E, Q-F:** đồng ý (D7–D8, D16).

## 3. Thay đổi theo module

| Module | Thay đổi | Interface công khai |
|---|---|---|
| `kami/replay/__init__.py`, `export.py` | Mới. `export(sim, out_dir, area=None, simplify=…)`, dựng dòng thời gian trạng thái từ `sim.trajectories` + khoảng đứng yên, events từ event log, metrics từ `sim.timeseries`; ghi xác định (sorted keys, làm tròn, gzip `mtime=0`) | Mới |
| `kami/replay/simplify.py` | Giản lược không gian–thời gian (D6) | Mới |
| `kami/replay/schema.py` | `SCHEMA_VERSION = 1`, `STATES`, `validate(path)`, `load(path)` | Mới |
| `kami/replay/__main__.py` + `kami/cli.py` | `python -m kami replay demo [--out]`, `replay export <run-folder hoặc --spec>`, `replay validate <dir>` | Bổ sung CLI |
| `kami/timeseries.py` | Cột `rider.pickup_mean` (nhận chuyến → đón, phút, trong cửa sổ) | Bổ sung cột |
| `kami/scenario.py`, `kami/config/specs.py`, `build.py` | `zonal(area=…)`; `ZonalSourceSpec.area`; `outputs.replay`; `run --spec --out` ghi `replay/` | Bổ sung, mặc định = cũ |
| `kami/store/runs.py` | Artifact `replay` khi `outputs.replay = "json"` | Bổ sung |
| `scenarios/hanoi/demo_center.json` | Kịch bản fixture (D7) | — |
| `web/` (mới) | `package.json` (khoá phiên bản trong `package-lock.json`), `next.config.mjs`, `src/app/` (trang `/`, `/ui`), `src/data/` (kiểu TS của hợp đồng, loader, `stateAt`/`positionAt`/`metricsAt`), `src/map/` (Mapbox + deck.gl layers), `src/panels/` (KPI, biểu đồ, chú giải, phát lại, chi tiết xe), `src/ui/` (thành phần), `src/design/` (tokens), `public/fixtures/hanoi_center_demo/` | Mới |
| `.gitignore` | `web/node_modules/`, `web/.next/`, `web/out/`, `web/.env.local` (đã thêm `.env.local`) | — |
| `docs/engine/20-visualizer.md` (mới), `docs/engine/README.md`, `02`, `18`, `09`, `15` | Tài liệu S03-13 | — |

## 4. Kế hoạch theo hạng mục

Thứ tự: B02-11 → S03-1 → S03-2 → S03-3 → S03-4 + S03-5 → S03-6 (**mốc kiểm tra: gửi ảnh chụp hai bảng màu, chờ
chọn Q-D**) → S03-7 → S03-8 → S03-9 → S03-10 → S03-11 → (S03-12) → S03-13.

**B02-11.** Chạy lại `python -m kami bench --repeat 5` trên commit `0e4e0d0` (working tree sạch), ghi
`benchmarks/results/2026-10-08-sprint02-clean.json`, cập nhật số liệu mốc trong backlog 02.

**S03-1 — Định dạng.** Viết `schema.py` (hằng số, `validate`, `load`), kiểu TypeScript tương ứng trong
`web/src/data/types.ts`; tài liệu hợp đồng đầy đủ (từng trường, đơn vị, quy tắc tương thích: thêm trường/trạng thái =
cùng phiên bản, đổi nghĩa = tăng phiên bản).

**S03-2 — Xuất từ run.**
1. Trạng thái segment: chặng `idle` → `cruising`, `reposition` → `reposition`, `stop` không khách → `pickup`, có
   khách → `on_trip`; khoảng hở giữa hai chặng → `idle` đứng yên, trừ khoảng lên/xuống xe (chặng sau xuất phát theo
   lịch ngay sau khi tới điểm đón/trả) → trạng thái của chặng sau (`on_trip` khi khách đang lên) hoặc `on_trip` khi
   khách đang xuống.
2. Hình học: `path_lon/path_lat/path_t` của Sprint 02 (theo `edge_geometry`), giản lược (D6), làm tròn.
3. Events từ event log; metrics từ `sim.timeseries`; quãng đường tích luỹ theo segment (cho S03-11).
4. `outputs.replay` + `replay export`.

**S03-3 — Fixture.** `zonal.area`; `scenarios/hanoi/demo_center.json` (chỉnh demand để hoàn thành ~0,85);
`python -m kami replay demo` = chạy kịch bản + export vào `web/public/fixtures/hanoi_center_demo/`; ghi kích thước,
thời gian sinh vào tài liệu.

**S03-4 — Design tokens & thành phần.** `tokens.json` (màu: thang brand 50–900, xám trung tính, nền/chữ/viền, trạng
thái xe A/B, cảnh báo; chữ: Inter (tự host, có số tabular), cỡ 12/13/14/16/20/28; khoảng cách 4-pt; bo góc 6/10/14;
bóng 2 mức; chuyển động 150/250 ms) → script sinh `tokens.css`/`tokens.ts`; thành phần UI cơ bản + trang
`/ui` hiển thị toàn bộ thành phần (dùng cho Sprint 09 và để chụp ảnh tài liệu).

**S03-5 — Bản đồ nền.** Mapbox light-v11 + chỉnh lớp (D11), `NavigationControl` (zoom, xoay, nghiêng), nút 2D/3D,
nút "căn khung khu vực" (fitBounds theo `manifest.area.bbox`), màn hình thiếu token.

**S03-6 — Xe di chuyển.** Loader → mảng typed theo segment; `positionAt` (D13); `IconLayer` xe (mũi tên/chấm theo
hướng, màu trạng thái, viền trắng để nổi trên nền sáng); `TripsLayer` mỗi trạng thái với `trailLength` 180 s, độ mờ
dần, độ dày 2–4 px theo zoom. **Mốc kiểm tra:** ảnh chụp bảng màu A và B ở zoom 12 và 15 → người dùng chọn.

**S03-7 — Chế độ quỹ đạo.** `TripsLayer` với `trailLength` = toàn khung giờ, độ mờ thấp (cộng dồn thành "bản đồ
nhiệt" đường); công tắc `Segmented` "Xe di chuyển ↔ Quỹ đạo".

**S03-8 — Chú giải / công tắc.** Mỗi trạng thái: chấm màu + nhãn + số xe tại thời điểm đang xem; nhấp để ẩn/hiện
vệt (và xe) của trạng thái đó.

**S03-9 — Phát lại.** Play/pause (phím cách), thanh thời gian có vạch giờ, tua (kéo, phím ←/→ ±1 phút), tốc độ
1×/10×/60×/120×/300×/600×, đồng hồ mô phỏng `HH:MM:SS` + ngày/khung giờ kịch bản. Đồng hồ là nguồn thời gian duy
nhất (store), mọi lớp và panel đọc từ đó.

**S03-10 — Panel metric.** KPI: đơn hoàn thành (luỹ kế), đơn hủy (luỹ kế), thời gian đón TB, thời gian chờ TB (cửa
sổ gần nhất, phút); biểu đồ cột hoàn thành/hủy theo khung 15 phút; miền xếp chồng tỷ lệ xe theo trạng thái; đường
thời gian chờ/đón; đường kẻ thời điểm đang xem. Panel thu gọn/mở rộng (và ẩn toàn bộ panel để xem bản đồ toàn màn
hình, phím `F`).

**S03-11 — Chi tiết xe.** Nhấp xe → thẻ: mã xe, fleet/loại xe/nhóm, trạng thái, chuyến hiện tại (khách, giờ nhận,
giờ đón dự kiến/thực tế), quãng đường đã chạy tới thời điểm đang xem; làm nổi lộ trình của segment hiện tại và
segment tiếp theo; bản đồ có thể "đi theo xe".

**S03-12 (tuỳ chọn) — OD demand.** `ArcLayer` từ `events` request → điểm trả trong cửa sổ 15 phút quanh thời điểm đang
xem. Làm nếu còn thời gian; không thì đưa vào backlog.

**S03-13 — Tài liệu.** `docs/engine/20-visualizer.md`: hợp đồng dữ liệu, lệnh sinh fixture, chạy web
(`cd web && npm ci && npm run dev`), cấu hình token, design tokens (bảng màu + tương phản), ảnh chụp màn hình (toàn
cảnh, quỹ đạo, nghiêng 3D, chi tiết xe, trang thành phần).

## 5. Kiểm chứng acceptance criteria

| AC | Cách kiểm chứng |
|---|---|
| AC03-1 | `tests/test_replay.py`: `replay demo` hai lần (khi đã build mạng Hà Nội) → mọi file giống hệt sha256; `validate()` không lỗi. Test luôn chạy được: export trên lưới và fixture OSM Hồ Gươm, chạy hai lần → cùng byte; `validate` bắt được lỗi cố ý (thiếu file, sai sha256, thời gian giảm, trạng thái lạ) |
| AC03-2 | Hướng dẫn trong docs/engine/20; mở bằng trình duyệt tích hợp → ảnh chụp: bản đồ sáng căn vào bbox khu vực demo; thao tác zoom/xoay/nghiêng (nút + chuột) — ảnh chụp trước/sau |
| AC03-3 | Python: (1) mọi điểm của segment nằm trên polyline của cạnh mạng trong ±1,5 m (bị giản lược ≤ 1 m), segment kề nhau liền mạch; (2) lấy 2.000 mẫu `(xe, t)` ngẫu nhiên (seed cố định): trạng thái theo replay = trạng thái suy độc lập từ event log (`TRIP_ACCEPTED` → pickup, `PICKUP` → on_trip, `DROPOFF` → idle, `IDLE_MOVE` purpose → cruising/reposition, `IDLE_ARRIVE` → idle) — bỏ mẫu cách mốc chuyển trạng thái < 1 s. Vitest: `positionAt`/`stateAt` trên fixture nhỏ khớp giá trị Python xuất kèm. Bằng mắt: ảnh chụp zoom 16 xe chạy trên đường |
| AC03-4 | Vitest cho bộ lọc layer theo công tắc và chế độ; kiểm tra trong trình duyệt (ảnh chụp: tắt `cruising`, chế độ quỹ đạo) |
| AC03-5 | Vitest: `metricsAt(t)` = dòng cuối có `t_row ≤ t` của `metrics.json`; Python: `metrics.json` = `sim.timeseries.rows` (cùng cột, NaN → null); trình duyệt: tua tới 3 thời điểm, so KPI trên màn hình với `metrics.json` (đọc DOM bằng `read_page`) |
| AC03-6 | `?debug=1` ghi thống kê khung hình; chạy kịch bản đo D16 trong Chrome của máy dev, ghi trung vị/p5 cho 3 mức zoom vào backlog. Không đạt → giảm số điểm vệt / bật `_pathType` tối ưu, đo lại |
| AC03-7 | Test tự động (Vitest) tính tỷ lệ tương phản WCAG từ `tokens.json`: mọi cặp chữ/nền khai báo ≥ 4,5 : 1 (chữ lớn ≥ 3 : 1), màu trạng thái ≥ 3 : 1 với nền bản đồ và khác nhau đôi một (ΔE ≥ 20); ảnh chụp light mode |
| AC03-8 | Ảnh chụp ở 1280×800 và 1920×1080: đủ khối; thu gọn panel / toàn màn hình bản đồ; ảnh đưa vào docs/engine/20 |
| AC03-9 | `tests/test_isolation.py` mở rộng: `kami.replay` không nằm trong import của lõi; không file Python nào import thư viện web; toàn bộ test cũ pass; `bench --compare` mốc Sprint 02 (sạch) không đổi kết quả, không thoái lui > 10% |

## 6. Mock & phần dự kiến chưa làm

- Không có backend: dữ liệu đọc từ file tĩnh (đúng phạm vi). Loader có interface `ReplaySource` để Sprint 08 thay bằng
  API — không phải mock trong code engine.
- Không có lớp khách đang chờ, trạm sạc, surge (Sprint 05/06/09); dark mode chỉ có biến token sẵn (tuỳ chọn), không
  nghiệm thu.
- Hiển thị 8k xe toàn thành phố (Sprint 04): định dạng JSON có thể cần chuyển nhị phân — sẽ ghi backlog kèm số đo.
- S03-12 (OD demand) có thể chuyển backlog.

## 7. Rủi ro & phương án dự phòng

| Rủi ro | Dự phòng |
|---|---|
| Chưa có token Mapbox → không chụp ảnh / kiểm tra bằng mắt được | Làm toàn bộ phần dữ liệu, logic, test tự động và giao diện (bản đồ hiện màn hình cấu hình); chụp ảnh khi có token. MapLibre chỉ khi người dùng đồng ý |
| Vệt màu kém nổi trên nền sáng | Viền trắng cho xe, tăng độ dày vệt theo zoom, giảm bão hoà nền; chọn bảng màu A/B bằng ảnh chụp thật |
| Fixture quá lớn | Tăng ngưỡng giản lược thời gian lên 1 s; giảm xuống 200 xe hoặc 1h30; mục tiêu ≤ 3 MB nén |
| GPU tích hợp không đạt FPS ở zoom thấp | Giảm `trailLength`, gộp layer trạng thái thành một layer có màu theo thuộc tính, không có khối nhà 3D |
| Phiên bản npm đổi gây vỡ build | Khoá `package-lock.json`, `npm ci`; ghi phiên bản Node trong `.nvmrc` |
| Định dạng chưa đủ tổng quát cho Sprint 05/08 | Trạng thái và fleet khai báo trong manifest; trường lạ bị bỏ qua; ví dụ thêm trạng thái `charging` trong test tương thích |

## 8. Lịch sử thay đổi

| Ngày | Thay đổi |
|---|---|
| 2026-10-08 | Tạo plan, trạng thái Chờ duyệt. Khảo sát: ảnh tham khảo `draft/operation_visualizer_1..3.png` (KPI, biểu đồ theo giờ, chú giải bật/tắt vệt, nghiêng 3D); máy dev có Node 24; tương phản WCAG của thang Tiffany và hai bảng màu trạng thái đã tính trước (D10, D12) |
| 2026-10-08 | Cập nhật theo câu trả lời Q-A…Q-F (vẫn **Chờ duyệt**): D1 đổi sang Next.js (build tĩnh); D11 bỏ khối nhà 3D, giữ nghiêng/xoay, `maxPitch` 60°; D15 token ở `web/.env.local`; Q-D chọn bảng màu qua ảnh chụp ở S03-6 |
| 2026-10-08 | D11 thêm zoom (giới hạn 10–18). **Người dùng duyệt plan** |
| 2026-10-08 | Lệch nhỏ khi implement: (1) **D2** — `MapboxOverlay` vẽ trên canvas riêng thay vì interleaved: interleaved buộc Mapbox vẽ lại mọi tile mỗi khung, zoom 16 nghiêng 60° trên GPU tích hợp chỉ 49 fps trung vị (ẩn hết lớp xe vẫn 50 fps), canvas riêng 270 fps; đổi lại vệt nằm trên tên phố (`?interleaved=1` giữ cách cũ để so sánh). (2) **D3** — ECharts 6 (bản hiện hành lúc cài, cùng API module). (3) **D13** — xe là chấm tròn viền trắng (luôn tròn khi nghiêng), chưa có mũi tên hướng (B03-6). (4) **S03-5** — thanh công cụ riêng (+, −, la bàn, 2D/3D, căn khung, ẩn bảng) dưới chú giải thay cho `NavigationControl` của Mapbox (tránh chồng panel ở màn hình thấp). (5) **D7** — demand 750/giờ × profile = 2.897 request (plan ước ≈ 2.000) để đạt hoàn thành ÷ đặt ≈ 0,84; `drain_s` 1.800. (6) **§2.1** — `events.json` thêm cột `to_lon`/`to_lat` (điểm đến của request, cho OD) và `eta` (giờ đón đã hứa, cho thẻ chi tiết xe); `outputs.replay` không khai báo thì không xuất hiện trong `to_dict` (spec cũ dump như trước). (7) Chặng độ dài 0 / bị cắt trước giờ xuất phát chỉ kết thúc khoảng hở trước nó (phát hiện nhờ test đối chiếu event log). (8) `tests/test_zonal.py` cập nhật danh sách file `scenarios/hanoi/` (thêm `demo_center.json`). (9) B02-11 đo trong thư mục repo (tạm `git stash`), vì đo ở thư mục khác tái hiện B02-4 |
