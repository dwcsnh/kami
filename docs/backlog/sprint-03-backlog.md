# Backlog sau Sprint 03 — Bản đồ vận hành (fleet operation visualizer) trên web

| | |
|---|---|
| Sprint | [sprint-03-map-visualizer.md](../sprint/sprint-03-map-visualizer.md) |
| Plan | [sprint-03-plan.md](../implementation-plan/sprint-03-plan.md) |
| Ngày kết thúc | 2026-10-08 |

Mục backlog đầu vào đã xử lý: **B02-9** (định dạng fixture cho visualizer: `kami.replay` v1 theo khu vực + giản lược
điểm — fixture demo 1,14 MB thay vì `trajectories.parquet` 55 MB của `am_peak`; ghi dần cho cả ngày vẫn mở ở Sprint
04, xem B03-2), **B02-11** (mốc benchmark đo lại trên `0e4e0d0` sạch).

## Trạng thái acceptance criteria

| AC | Kết quả | Bằng chứng / ghi chú |
|---|---|---|
| AC03-1 | Đạt | `python -m kami replay demo` (mạng `hanoi`, ≈ 15 s): `tests/test_replay.py::TestDemoFixture` chạy lệnh hai lần → mọi file giống hệt từng byte, giống fixture commit ở `web/public/fixtures/hanoi_center_demo/`, `validate()` không lỗi. `TestReplayGrid`/`TestReplayRoad`: xuất hai lần cùng byte (lưới, OSM Hồ Gươm); `validate` bắt thiếu file, sai sha256, thời gian giảm, trạng thái lạ, `schema_version` mới hơn; trường/trạng thái lạ được chấp nhận |
| AC03-2 | Đạt | Hướng dẫn chạy ở docs/engine/20 §3. Trình duyệt: bản đồ Mapbox `light-v11` nền sáng căn vào khu vực demo; zoom (cuộn, nút +/−, giới hạn 10–18), xoay, nghiêng 3D (nút 2D/3D, chuột phải/Ctrl + kéo) — ảnh `overview.jpg`, `tilt-3d.jpg`, `zoom16-street.jpg` |
| AC03-3 | Đạt | Tự động: (1) điểm giữ lại là điểm của polyline theo `edge_geometry`, điểm bỏ đi lệch ≤ 1 m và ≤ 0,5 s, mọi điểm xuất ra cách polyline gốc ≤ 1,5 m (`test_ac03_3_points_stay_on_the_road`, OSM Hồ Gươm có tắc đường, sự cố, hai nhóm xe); (2) 2.000 mẫu (xe, t) ngẫu nhiên seed cố định: trạng thái replay = trạng thái suy độc lập từ event log (`test_ac03_3_states_match_event_log` trên lưới, đường OSM và lưới có policy `heatmap_reposition`); (3) Vitest: `stateAt`/`positionAt` của web = 200 mẫu do `kami.replay.query` xuất. Bằng mắt: zoom 16–16,5, xe chạy trên đường, vệt mờ dần (`tilt-3d.jpg`, `zoom16-street.jpg`) |
| AC03-4 | Đạt | Vitest `layerPlan.test.ts` (ẩn trạng thái bỏ vệt và xe; chế độ quỹ đạo tích luỹ, không mờ); trình duyệt: `toggle-states.jpg` (ẩn "chở khách" và "rảnh – đứng yên"), `trajectories.jpg` |
| AC03-5 | Đạt | Python: `metrics.json` = `sim.timeseries.rows` (cùng cột, NaN → null); Vitest: `metricsAt(t)` = dòng cuối có `t_row ≤ t`; trình duyệt: tua tới 07:15:30, 08:00:00, 08:53:07 — 4 KPI trên màn hình (đọc DOM) khớp dòng `metrics.json` 07:15, 08:00, 08:53 |
| AC03-6 | Đạt | `scripts/fps.mjs` (Chrome 1920 × 1080, fixture 300 xe phát 60×, 60 s mỗi mức). GPU tích hợp Radeon 680M: zoom 12 285,7 / 108,7 fps (trung vị / p5), zoom 14 277,8 / 107,5, zoom 16 nghiêng 60° 277,8 / 107,5; RTX 3050: 357 / 151, 370 / 156, 357 / 149 — ngưỡng D16 (≥ 55 / ≥ 30). Lần đo đầu (deck.gl interleaved) zoom 16 nghiêng chỉ 48,8 / 29,0 → tách canvas (lịch sử thay đổi của plan). Đo headless (không khoá vsync) |
| AC03-7 | Đạt | Vitest `tokens.test.ts`: mọi cặp chữ/nền ≥ 4,5 : 1 (chữ chính 14,8, chữ phụ 6,5, chữ trắng trên nút chính 5,0), đồ hoạ ≥ 3 : 1; màu trạng thái (cả A và B) ≥ 3 : 1 với nền bản đồ và nền panel, khác nhau đôi một và khác Tiffany ΔE ≥ 20. Ảnh light mode `components.jpg`. **Bảng màu A/B chờ người dùng chọn** (B03-1) |
| AC03-8 | Đạt | Đủ khối (bản đồ, KPI, 3 biểu đồ, đồng hồ + phát lại, chú giải/công tắc, chi tiết xe). Ảnh 1440 × 900 và 1280 × 800 (`overview-1280.jpg`); thu gọn bảng metric (`panels-hidden.jpg`), ẩn mọi bảng bằng `F`. Ảnh trong docs/engine/20 |
| AC03-9 | Đạt | `tests/test_isolation.py` thêm 4 test: `import kami` không nạp `kami.replay`, lõi không import `kami.replay`, không file Python nào import thư viện web, replay chạy không cần DB. **191 test pass** (env `fleetpy`). Benchmark: sự kiện và metric **giống hệt** mốc sạch Sprint 02; thời gian xem "Số liệu mốc" |

Test: Python `python -m unittest discover -s tests -t .` — 191 test pass (thêm `test_replay` 25, `test_isolation` +4);
web `cd web && npm test` — 56 test Vitest pass; `npm run typecheck`, `npm run build` sạch.

## Mục còn mở

| Mã | Loại | Mức độ | Mô tả | Lý do chưa làm | Sprint dự kiến xử lý | Trạng thái |
|---|---|---|---|---|---|---|
| B03-1 | Chờ phụ thuộc | Thấp | **Chọn bảng màu trạng thái A hoặc B** (plan Q-D). Ảnh so sánh zoom 12/15 ở docs/engine/20 §4. Mặc định đang là A; đổi = sửa `paletteFromUrl` (`web/src/map/palette.ts`) và bỏ bảng còn lại khỏi `tokens.json` | Chờ người dùng xem ảnh | 03 (ngay khi người dùng chọn) | Mở |
| B03-2 | Nợ kỹ thuật | Cao | Định dạng JSON đủ cho vài trăm xe trong 2 giờ (1,14 MB). Ngoại suy 8.000 xe × cả ngày ≈ 27 × 10 × 1,1 MB ≈ 300 MB nén — cần định dạng nhị phân (Arrow/protobuf) và chia theo khung thời gian / tải dần; exporter cũng giữ toàn bộ chặng trong RAM | Ngoài phạm vi (UI quy mô thành phố) | 04 | Mở |
| B03-3 | Nợ kỹ thuật | Thấp | Benchmark dao động ±15% giữa các lần chạy cùng mã khi máy có tải khác (Chrome, dev server): hai lần `--compare` liên tiếp báo `grid_am_peak_surge` +11,8% rồi +38%. A/B cùng điều kiện (mã Sprint 02 tạm stash ↔ Sprint 03) cho −13,6%…+2,8% — không có thoái lui do code. Ngưỡng 10% trên median của 5 lần quá nhạy; cân nhắc so `min`, tăng `--repeat`, ghim CPU (`taskset`) hoặc chạy khi máy rảnh | Công cụ đo, không thuộc phạm vi sprint | 04 | Mở |
| B03-4 | Nợ kỹ thuật | Thấp | deck.gl vẽ trên canvas riêng nên vệt nằm **trên** tên phố (interleaved cho vệt dưới tên phố nhưng buộc Mapbox vẽ lại mọi tile mỗi khung — 49 fps khi nghiêng trên GPU tích hợp). Hướng: layer tuỳ biến của Mapbox chỉ vẽ lại khi cần, hoặc tự vẽ lại nhãn phố phía trên | Ưu tiên hiệu năng (AC03-6) | Chưa xếp | Mở |
| B03-5 | Nợ kỹ thuật | Thấp | `npm audit`: 13 lỗ hổng (5 trung bình, 8 cao) trong phụ thuộc gián tiếp (ví dụ `sprintf-js` qua `argparse` của chuỗi `@deck.gl/geo-layers`); `npm audit fix --force` hạ deck.gl xuống 9.0 (phá vỡ). Chỉ là công cụ phía trình duyệt/dev, chưa triển khai công khai | Chờ bản vá upstream | 09 (trước khi triển khai ứng dụng quản lý) | Mở |
| B03-6 | Ý tưởng | Thấp | Xe hiện là chấm tròn; mũi tên theo hướng chạy (đã có `Replay.headingAt`) giúp đọc chiều di chuyển ở zoom gần | Không bắt buộc | 09 | Mở |
| B03-7 | Ý tưởng | Thấp | KPI thời gian đón/chờ là TB trong cửa sổ metric 60 s — dao động, phút không có lượt đón hiện "—". Thêm TB trượt 15 phút (cột time-series mới hoặc tính trong trình duyệt) | Cần chốt định nghĩa KPI với người dùng | 09 | Mở |
| B03-8 | Ý tưởng | Thấp | Dark mode (tokens đã tách biến, chưa có bộ màu tối) | Ngoài phạm vi nghiệm thu | 09 | Mở |
| B03-9 | Nợ kỹ thuật | Thấp | Kiểm thử tương tác trình duyệt (nhấp xe, tua, công tắc) mới chạy thủ công + script (`scripts/screenshots.mjs`, `scripts/fps.mjs`, cần token Mapbox và Chrome); chưa có E2E tự động trong bộ test | Cần token trong môi trường test | 09 | Mở |
| B03-10 | Ý tưởng | Cao | **Phương án thuật toán routing cho S04-4** (người dùng yêu cầu, 2026-10-08): plan Sprint 04 phải đưa vào mục "phương án đã cân nhắc" và chọn sau khi profile (S04-2): (a) **A\*** — heuristic khoảng cách chim bay ÷ tốc độ lớn nhất có thể (tốc độ tự do cao nhất × hệ số tắc đường nhỏ nhất × nhóm xe nhanh nhất, để heuristic chấp nhận được); rẻ (~100 dòng C++ + bản Python), dự kiến ~1–2× so với Dijkstra hai chiều hiện tại, không giúp truy vấn X→1 của matching; (b) **ALT** (A\* với landmark) — heuristic chặt hơn, vài lần nhanh hơn, tính lại khi hệ số tắc đường đổi; (c) **cache / giảm số truy vấn** (cặp node hay dùng, bảng theo zone, gộp 3 truy vấn 1→1 của `_quote_eta`); (d) **Contraction Hierarchies có tuỳ biến (CCH)** — hàng chục–trăm lần cho 1→1, cập nhật trọng số mỗi giờ tắc đường, phức tạp nhất. Ràng buộc: sửa cả router C++ lẫn Python và giữ test đối chiếu hai backend; đường cùng chi phí có thể khác → metric lệch so với mốc phải được giải thích (AC04-4); đổi thuật toán đặt sau cờ cấu hình, mặc định giữ kết quả mốc cho tới khi người dùng duyệt | Thuộc tối ưu routing (Sprint 04) | 04 | Mở |

Fixture demo trong repo được test so khớp với lệnh sinh lại: mọi thay đổi engine làm đổi kết quả kịch bản demo phải
chạy lại `python -m kami replay demo` và commit fixture mới (test `TestDemoFixture` báo lỗi nếu quên).

## Mock đang dùng

Không có mock. Web chỉ đọc file tĩnh qua `ReplaySource` (`StaticReplaySource`) — đúng phạm vi; Sprint 08 thêm nguồn
API cùng interface.

## Số liệu mốc

Môi trường như Sprint 02 (env `fleetpy`, CPython 3.10.21, router C++, Ryzen 9 6900HS). Mốc so sánh: 
[`2026-10-08-sprint02-clean.json`](../../benchmarks/results/2026-10-08-sprint02-clean.json) (B02-11). Kết quả Sprint 03:
[`2026-10-08-sprint03.json`](../../benchmarks/results/2026-10-08-sprint03.json) (`--repeat 5`, working tree Sprint 03).

| Case | wall_s median Sprint 03 | Mốc Sprint 02 sạch | Δ | Sự kiện (= mốc) | RAM đỉnh (MB) |
|---|---|---|---|---|---|
| `grid_am_peak_baseline` | 0,66 | 0,62 | +5,7% | 8.375 | 77 |
| `grid_am_peak_baseline_nots` | 0,69 | 0,60 | +14,8% | 8.375 | 77 |
| `grid_am_peak_surge` | 0,66 | 0,60 | +10,2% | 8.456 | 77 |
| `grid_pm_peak_x5` | 2,51 | 2,57 | −2,3% | 26.170 | 97 |
| `hanoi_am_peak_small` | 8,38 | 9,18 | −8,6% | 7.578 | 211 |
| `road_example_400` | 0,75 | 0,70 | +6,0% | 3.901 | 87 |

Hai case vượt 10% **không do code** (B03-3): `_nots` không chạy dòng code nào đã đổi trong sprint (chuỗi metric tắt,
nguồn preset); A/B 9 lần lặp trong cùng điều kiện máy — mã Sprint 02 (stash `kami/`) ↔ mã Sprint 03: baseline +1,6%,
`_nots` −3,1%, surge −13,6%, `pm_peak_x5` +2,8%. Metric vận hành của mọi case giống hệt mốc (không có cờ
`results changed`). Thêm cột `rider.pickup_mean` chỉ đọc sự kiện, không đổi kết quả.

**Fixture demo** (`scenarios/hanoi/demo_center.json`, seed 0): 2.897 request, 2.297 đã đặt, 1.928 hoàn thành
(hoàn thành ÷ đặt 0,84), 368 hủy; 300 xe, 8.361 segment, 136.112 điểm, 12.017 sự kiện; 1,14 MB nén (5,1 MB chưa nén);
sinh lại ≈ 15 s.

**Web (AC03-6):** xem bảng ở AC03-6 và docs/engine/20 §5. Bản build tĩnh `web/out/` 5,4 MB (gồm fixture).
