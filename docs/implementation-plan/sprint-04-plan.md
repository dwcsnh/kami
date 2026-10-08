# Implementation plan — Sprint 04: Hiệu năng quy mô GreenSM

| | |
|---|---|
| Sprint | [sprint-04-scale-performance.md](../sprint/sprint-04-scale-performance.md) |
| Backlog đầu vào | [sprint-03-backlog.md](../backlog/sprint-03-backlog.md) — xử lý trong plan này: **B03-2** (replay quy mô thành phố), **B03-3** (độ ổn định benchmark), **B03-10** (phương án routing); từ [sprint-02-backlog.md](../backlog/sprint-02-backlog.md): **B02-3** (thông lượng trên mạng Hà Nội), **B02-4** (seed phụ thuộc đường dẫn file), **B02-5** (`_environment_change` khởi động lại chặng chưa xuất phát), **B02-9** (phần ghi dần — qua B03-2); từ [sprint-01-backlog.md](../backlog/sprint-01-backlog.md): **B01-5** (case benchmark GreenSM), **B01-6** (ghi solver/môi trường thực dùng), **B01-7** (event log ghi dần), **B01-8** (case ngắn nhạy nhiễu). Mốc benchmark: [`2026-10-08-sprint03.json`](../../benchmarks/results/2026-10-08-sprint03.json) |
| Trạng thái | Chờ duyệt |

## 1. Tóm tắt hướng tiếp cận

**Đo trước, tối ưu sau, và tách hai loại tối ưu.**

1. **Số liệu ban đầu (đã đo khi lập plan, env `fleetpy`, router C++, máy dev Ryzen 9 6900HS):**

   | Lần chạy | Kết quả |
   |---|---|
   | `scenarios/hanoi/weekday.json` (98.968 request, 8.000 xe, 24h, không cProfile) | 0h–6h (đêm, ít khách): **365 s**, ≈ 110k sự kiện/giờ mô phỏng; riêng giờ 6h–7h: **294 s**; RSS 513 MB sau 7 giờ mô phỏng và tăng dần. Ngoại suy cả ngày (các giờ ban ngày ~300 s/giờ): **~1,5–2 giờ** — chưa đạt PERF-2 |
   | Lát cắt 7h–8h cùng kịch bản (8.130 request, 8.000 xe, cProfile) | **483 s** cho 1 giờ mô phỏng, 157.904 sự kiện (≈ 330 sự kiện/s) |

   Phân rã thời gian của lát cắt 7h–8h (cProfile, thời gian tích luỹ):

   | Nhóm | Thời gian | Tỷ lệ | Nguyên nhân |
   |---|---|---|---|
   | `_quote_eta` (báo ETA cho mỗi request) | 310 s | 64% | Duyệt **mọi xe** (8k) mỗi request: `current_loc` → `_leg_position` (quét tuyến tính lộ trình), toạ độ, sắp xếp toàn bộ danh sách để lấy 3 xe gần nhất |
   | `candidate_pairs` (sinh ứng viên matching) | 138 s | 29% | Mỗi job duyệt **mọi xe rảnh**, sắp xếp toàn bộ để lấy 12 xe gần nhất (46 triệu lần gọi lambda khoá sắp xếp trong 1 giờ) |
   | Routing (1→1, X→1, lộ trình) | 23 s | 5% | 1→1 C++ ≈ 0,27 ms, X→1 ≈ 0,07 ms (đã có cache) |
   | Giải gán Hungarian | < 1 s | — | Ma trận nhỏ (≤ 12 ứng viên/job) |
   | Hazard hủy, sự kiện, behavior | < 5 s | ~1% | |

   Trên kịch bản nhỏ `hanoi_am_peak_small` (300 xe) thì ngược lại: routing chiếm ~80% (X→1 47%, 1→1 28%). **Ở quy mô
   8k xe, điểm nóng là các phép quét O(số xe) bằng Python, không phải routing.** Ban đêm (ít request, 8k xe rảnh đi
   lòng vòng ~110k sự kiện/giờ) chi phí chính là routing 1→1 của di chuyển rảnh (`IDLE_MOVE`).

2. **Hai tầng tối ưu:**
   - **Tầng chính xác** (mặc định, luôn bật): kết quả **giống hệt từng sự kiện** so với engine trước tối ưu — chỉ số
     ngoại vi, cấu trúc dữ liệu, cache, bớt tính lại; mọi phép so sánh/thứ tự hoà giữ nguyên. Kiểm bằng bộ "golden"
     (S04-8).
   - **Tầng xấp xỉ** (sau cờ cấu hình, mặc định tắt): thay đổi kết quả có kiểm soát (ví dụ ALT routing, chia bài toán
     gán quá lớn). Chỉ bật khi tầng chính xác chưa đủ PERF-2; kiểm bằng ngưỡng sai khác metric (D11).

3. Thứ tự: sửa các lỗi đổi kết quả có sẵn trong backlog (B02-4, B02-5) **trước**, chốt bộ golden mới, rồi mới tối ưu
   — để mọi thay đổi kết quả sau đó đều là lỗi.

4. Visualizer: định dạng phát lại nhị phân chia theo giờ (`kami.replay` v2), exporter ghi dần trong lúc chạy; web tải
   dần theo khung giờ và vẽ 8k xe bằng buffer nhị phân của deck.gl.

## 2. Quyết định kỹ thuật

| # | Quyết định | Phương án đã cân nhắc | Lý do chọn |
|---|---|---|---|
| D1 | **Mục tiêu PERF-2 (đề xuất, chờ chốt — Q-A):** `hanoi_greensm_day` trên máy dev (AMD Ryzen 9 6900HS 8 nhân/16 luồng, 27 GB RAM, Linux, env `fleetpy` CPython 3.10 + router C++, một tiến trình): **wall-clock `Simulation.run` ≤ 30 phút** và **RSS đỉnh ≤ 8 GB**, event log ghi dần ra Parquet. Biến thể có xuất replay (S04-10): **≤ 40 phút, ≤ 8 GB**. Mục tiêu "kéo dài" (không bắt buộc): ≤ 15 phút | ≤ 10 phút (cần routing CCH + viết lại lõi bằng C++/Numba); không giới hạn RAM | Đúng con số đề xuất trong requirements Q1. Ước tính sau tầng chính xác: giờ cao điểm ~30–60 s, cả ngày ~10–20 phút — đạt 30 phút với biên an toàn; ≤ 10 phút cần đổi kiến trúc, ngoài phạm vi |
| D2 | **Kịch bản `hanoi_greensm_day`** (`benchmarks/scale/hanoi_greensm_day.json`, sao từ `scenarios/hanoi/weekday.json`): 0h–24h, `zonal`, H3 r8, tắc đường zone × giờ, ~100k request theo profile giờ weekday, 5.000 ô tô + 3.000 xe máy, seed 0, chuỗi metric 300 s, event log Parquet. **Ca làm việc** (Q-C): thêm tham số kịch bản `zonal.shifts` = danh sách mẫu ca có trọng số (ví dụ sáng 5h–13h, ngày 9h–17h, chiều 14h–22h, hai đầu cao điểm 6h–10h + 16h–20h, đêm 21h–5h); không khai báo → hành vi cũ (70% xe cả ngày) | Giữ sinh ca của 0.1 (70% xe online 24h); làm ca theo fleet ngay | 8k xe online cả đêm là phi thực tế và tạo ~110k sự kiện/giờ đi lòng vòng vô ích. Ca theo **fleet** (FLEET-1/2, B01-2) vẫn thuộc Sprint 05 — `zonal.shifts` là tham số sinh kịch bản, Sprint 05 có thể ghi đè theo fleet |
| D3 | **Hai bộ benchmark:** `benchmarks/specs/` (bộ nhanh, như cũ + thêm case dài hơn `hanoi_peak_8k_1h`: 7h–8h, 8k xe — đủ dài để ổn định và đại diện cho điểm nóng quy mô) và `benchmarks/scale/` (chỉ `hanoi_greensm_day`, `--repeat 1` mặc định, ~15–30 phút). `kami bench` thêm `--suite scale` (bí danh) và cột `peak_rss_mb` như cũ | Đưa case cả ngày vào bộ nhanh | `--repeat 5` cho case 20 phút = gần 2 giờ; bộ nhanh phải chạy được mỗi sprint |
| D4 | **Ổn định đo (B03-3, B01-8):** so sánh thoái lui dùng **`min`** của các lần lặp (ít nhạy tải nền hơn median) — vẫn ghi median/max; `--repeat` mặc định 5 cho bộ nhanh; tuỳ chọn `--pin-cpu N` (Linux `os.sched_setaffinity` cho tiến trình con) | Tăng ngưỡng lên 15%; chỉ tăng `--repeat` | `min` là ước lượng tốt nhất của "chi phí thật" khi nhiễu chỉ cộng thêm; không nới yêu cầu 10% của "Định nghĩa xong" |
| D5 | **Profile (S04-2) không sửa engine:** `python -m kami.bench --profile <case>` chạy cProfile và gom hàm theo **nhóm** bằng bảng ánh xạ (routing: `kami/network/**`, `traffic.*`; ứng viên: `matching.candidate_pairs`, `_quote_eta`, `current_loc`, `_leg_position`; giải gán: `matching.solve`/`_hungarian`; behavior/hazard: `kami/behavior/**`, `_arm_cancel`, `_accrue`, `_hazard_per_s`; event log: `EventLog.*`; còn lại: vòng lặp sự kiện). RAM theo thành phần: RSS sau từng bước (nạp mạng → sinh kịch bản → chạy với event log/quỹ đạo tắt → bật từng thứ), cộng `sys.getsizeof` sâu trên mẫu agent. Báo cáo ghi ra `benchmarks/results/<ngày>-profile-<case>.md` | Đồng hồ đo trong engine (`perf_counter` theo khối); `py-spy`; `tracemalloc` | Không tốn chi phí khi tắt, không thêm phụ thuộc; cProfile làm chậm ~2× nhưng tỷ lệ giữa các nhóm đủ dùng để chọn việc. `tracemalloc` làm chậm 5–10× trên case 8k xe |
| D6 | **Chỉ mục không gian cho xe rảnh — chính xác (S04-3):** lớp `AvailableIndex` (lưới ô 250 m, `kami/core/spatial.py`) giữ mọi xe `available`. Xe đứng yên: một ô. Xe rảnh **đang chạy** (đi lòng vòng, điều xe): khi bắt đầu chặng, tính lộ trình (đằng nào `current_loc` cũng cần) và đăng ký vào **mọi ô mà lộ trình đi qua, kèm khoảng thời gian** xe ở trong ô (nới ±1 ms để bao lỗi làm tròn). Truy vấn k-gần-nhất (có điều kiện: tabu, sức chứa) duyệt ô theo vòng tròn đồng tâm, với mỗi ứng viên tính `current_loc` **bằng hàm cũ**, sắp theo `(khoảng cách², id)` như cũ, và chỉ dừng khi khoảng cách thứ k **nhỏ hơn hẳn** bán kính trong của vòng chưa duyệt (giữ đúng thứ tự hoà). Cập nhật chỉ mục ở `_set_driver_state`, `going_offline`, bắt đầu/kết thúc chặng; mục cũ bị bỏ lười theo `plan_version` | Chụp vị trí xe mỗi `DISPATCH_TICK` rồi dùng cho cả báo giá (đổi kết quả: vị trí cũ tới 10 s); KD-tree dựng lại mỗi tick (`scipy`); chỉ lưới cho xe đứng yên + quét tuyến tính xe đang chạy | Đây là điểm nóng 93% (§1). Cách đăng ký theo lộ trình cho **đúng** tập k xe gần nhất mà cách cũ chọn ⇒ kết quả giống hệt. KD-tree dựng lại O(N log N) mỗi tick và không dùng được cho báo giá giữa hai tick. Chụp vị trí theo tick đổi kết quả mà không cần thiết |
| D7 | **Báo giá ETA (`_quote_eta`) — chính xác:** dùng `AvailableIndex` (k = 3) thay cho duyệt mọi xe; 3 truy vấn 1→1 giữ nguyên (đã đi qua cache; gộp thành X→1 có thể lệch vài ULP do thứ tự cộng khác của Dijkstra một chiều/hai chiều — xếp vào tầng xấp xỉ, chỉ làm nếu cần) | Gộp 3 truy vấn 1→1 thành một X→1 ngay | Sau D6 phần còn lại của `_quote_eta` là ~3 truy vấn đã cache — nhỏ |
| D8 | **`_leg_position` — chính xác:** lộ trình mang thêm mảng `cum/total` (tính một lần khi có `path`) và dùng `bisect_right` thay vòng lặp tuyến tính; điều kiện `cum/total ≤ frac` giữ nguyên phép chia nên cho đúng node cũ | Lưu thời điểm tới từng node | Bisect trên cùng giá trị số ⇒ giống hệt; từ O(độ dài lộ trình) xuống O(log) |
| D9 | **Routing (B03-10) — chọn theo profile:** profile ở §1 cho thấy routing chỉ ~5% ở quy mô 8k xe giờ cao điểm nhưng là chi phí chính ban đêm (đi lòng vòng). Kế hoạch theo bậc: **(c) cache / giảm truy vấn — làm, chính xác:** (i) router C++ trả **chi phí + lộ trình trong một lần** Dijkstra hai chiều (`computeRouteAndCost1To1` — chi phí lấy từ chính lần chạy đó nên bằng `computeTravelCosts1To1` từng bit) và chặng mới dùng nó khi cần lộ trình ngay (D6: xe rảnh đang chạy), bỏ lần tính lộ trình thứ hai; (ii) giữ cache 1→1 qua các giờ tắc đường khi hệ số zone × giờ **không đổi** giữa hai giờ liên tiếp (hiện cache bị xoá mỗi `CONGESTION_UPDATE`); (iii) `estimate` dùng lại kết quả `travel` cùng (o, d, t, nhóm) khi nền tảng và thực tế trùng nhau (không có sự cố). **(b) ALT — chỉ làm nếu sau tầng chính xác vẫn chưa đạt D1:** A\* với 16 landmark (chọn xa nhất, tính lại bảng khi đổi giờ tắc đường ~0,5 s × 2 nhóm × 24 giờ), sau cờ `routing.algorithm = "alt"`, mặc định `"dijkstra"`; sửa cả C++ và Python, test đối chiếu chi phí hai backend (sai số ≤ 1e-6 tương đối) — lộ trình cùng chi phí có thể khác ⇒ tầng xấp xỉ. **(a) A\* khoảng cách chim bay:** không làm (lợi 1–2×, ALT hơn hẳn với cùng công sức hạ tầng). **(d) CCH:** không làm trong sprint này (phức tạp nhất; chỉ cần nếu mục tiêu kéo dài ≤ 10 phút) → backlog. Truy vấn X→1 của matching không đổi thuật toán (Dijkstra ngược có giới hạn thời gian đã nhanh: ~0,07 ms) | Theo thứ tự trong B03-10; chuyển hết sang CCH | Tối ưu đúng chỗ nóng: ở quy mô thật routing không phải nút thắt chính; (c) giữ kết quả giống hệt; ALT là phương án dự phòng có cờ |
| D10 | **Giải gán batch lớn (S04-5) — chính xác:** tách đồ thị ứng viên (job–xe) thành **thành phần liên thông**, giải Hungarian từng thành phần, gộp kết quả theo thứ tự job id. Với chi phí "không có cặp" = `INF` (như hiện tại) lời giải tối ưu toàn cục = hợp các lời giải tối ưu từng thành phần. Rủi ro duy nhất: khi có **nhiều** lời giải cùng tối ưu, `linear_sum_assignment` có thể chọn khác — test golden sẽ phát hiện; nếu gặp, thêm phá hoà xác định (cộng `ε·thứ hạng` vào chi phí). Thêm tham số `MatchingParams.max_component` (mặc định không giới hạn = chính xác): thành phần lớn hơn thì cắt theo ô lưới (tầng xấp xỉ, đo chất lượng theo tổng ETA so với lời giải toàn cục, ngưỡng mặc định ≤ 1%) | Chia theo zone cố định; dùng `scipy.sparse.csgraph.min_weight_full_bipartite_matching` | Profile cho thấy giải gán < 1% vì mỗi job chỉ có ≤ 12 ứng viên ⇒ ma trận vốn thưa; tách thành phần giữ đúng tối ưu và giới hạn chi phí xấu nhất O(n³) khi batch lớn (mưa, sự cố) |
| D11 | **Ngưỡng cho tầng xấp xỉ (chờ chốt — Q-B):** so với chế độ chính xác trên `hanoi_peak_8k_1h`, cùng seed: tỷ lệ hoàn thành lệch ≤ 1 điểm %, thời gian chờ TB và p90 lệch ≤ 3%, utilization lệch ≤ 1 điểm %, tổng ETA đón lệch ≤ 1%. Mỗi cờ xấp xỉ có test riêng kiểm các ngưỡng này | Không cho phép tối ưu đổi kết quả | AC04-4 cho phép sai khác "được giải thích và chấp nhận trong plan"; có ngưỡng thì có thể bật khi cần mà không phải xin duyệt lại |
| D12 | **Hủy/hazard và tick định kỳ (S04-6) — chính xác:** (i) `_arm_cancel`/`_accrue`: dựng `Context` một lần, gắn sẵn model và hằng số vào biến cục bộ, tránh gọi lại `_hazard_per_s` qua thuộc tính (cùng công thức, cùng thứ tự phép tính ⇒ cùng số); (ii) `_riders_in_wait` duy trì tập rider đang chờ (thay vì quét mọi rider mỗi giờ tắc đường); (iii) `idle_drivers()` dùng tập xe `available` duy trì sẵn (cùng thứ tự id); (iv) `DISPATCH_TICK` khi không có job mở và không có xe rảnh vẫn giữ nhịp (đổi sẽ đổi `seq` của sự kiện) — chỉ bỏ phần tính toán thừa trong handler. Đo lại sau D6–D8; nếu nhóm này < 5% thì dừng ở (i)–(iii) | Bước tích phân thích nghi (đổi kết quả); lập lịch hủy dạng nghịch đảo giải tích | Ở 8k xe nhóm này ~1% (§1); chỉ dọn phần O(N) để không thành nút thắt khi 100k rider tích luỹ |
| D13 | **Event log ghi dần (S04-7, B01-7):** `EventLog.stream_to(path, fmt, batch_rows=50_000)` — mỗi `batch_rows` dòng ghi một row group Parquet (cùng schema, cùng cột `info` JSON như `save`) hoặc nối vào CSV gzip, rồi xoá khỏi RAM; `close()` ghi phần còn lại. Khi streaming: `rows` rỗng, `len(log)` = số dòng đã ghi, listener (chuỗi metric, live) vẫn nhận mọi dòng. Bật qua spec `outputs.event_log_mode: "memory" | "stream"`; CLI `run --spec --out` và `kami.store` mặc định `"stream"` khi có ghi file. API Python `Simulation` mặc định giữ `"memory"` (tương thích 0.1). File tạo ra giống hệt `save` (test so từng dòng). Replay export đọc lại event log từ file khi streaming | Giữ trong RAM rồi ghi một lần (hiện tại); SQLite cho event log | Metric (`kami.metrics`) không đọc event log (đã kiểm), chuỗi thời gian dùng listener ⇒ streaming không ảnh hưởng kết quả |
| D14 | **Bộ nhớ trạng thái agent:** `__slots__` cho `Rider`, `Driver`, `Leg`, `Stop`, `Job`, `Event` (viết tay vì phải chạy trên Python 3.9 — `dataclass(slots=True)` cần 3.10); lộ trình của chặng đã đóng bị bỏ (`leg.path = None`) khi không ghi quỹ đạo; `TrajectoryRecorder` ghi dần như D15 | Lưu agent dạng mảng NumPy (đổi API thuộc tính) | `__slots__` giảm ~40–50% RAM mỗi object mà không đổi API (trừ việc gán thuộc tính lạ — sẽ kiểm `examples/` và policy thư viện) |
| D15 | **Replay quy mô thành phố — `kami.replay` v2 (S04-10, B03-2, B02-9):** thư mục gồm `manifest.json` (như v1 + danh sách **chunk theo giờ**) và mỗi giờ một chunk nhị phân `trips-HH.bin.gz` / `events-HH.bin.gz` + `vehicles.json`, `metrics.json`. Chunk = header JSON nhỏ + các mảng kiểu cố định little-endian: `vehicle u32`, `state u8`, `start_index u32`, toạ độ **int32 lượng tử 1e-6 độ** (~0,1 m, như 6 chữ số của v1), thời gian **float32 giây tính từ đầu giờ của chunk** (sai số < 1 ms). Segment cắt qua ranh giới giờ được ghi vào mọi chunk nó chạm. Exporter **ghi dần** từ `TrajectoryRecorder` (đệm theo giờ, xả chunk khi mọi chặng bắt đầu trước giờ đó đã đóng) — không giữ cả ngày trong RAM. Web: `Float32Array`/`Int32Array` đọc thẳng từ `ArrayBuffer`, đưa vào deck.gl dưới dạng **binary attributes** (không tạo object JS cho từng điểm), tải chunk giờ hiện tại + giờ kế tiếp trước, bỏ chunk cũ quá 2 giờ. v2 **thay** v1: fixture demo sinh lại ở v2, web chỉ đọc v2 (Q-E) | Giữ JSON, chỉ chia theo giờ; Apache Arrow IPC + `apache-arrow` JS (~200 KB); Parquet + `parquet-wasm` (~2 MB WASM); protobuf | Ước tính một ngày: ~600k segment, ~10 triệu điểm (mật độ như fixture demo) ⇒ JSON ~300 MB nén (B03-2). Nhị phân lượng tử + gzip ≈ 6–8 byte/điểm ⇒ **~60–80 MB/ngày, ~3–5 MB/giờ cao điểm** — tải dần được. Mảng kiểu cố định đọc không cần thư viện, dùng thẳng làm buffer GPU; Arrow mạnh hơn nhưng thừa cho dữ liệu cột cố định |
| D16 | **Hiển thị 8k xe ở mức toàn thành phố:** xe = `ScatterplotLayer` binary (vị trí tính trên CPU mỗi khung như D13 Sprint 03 nhưng duyệt mảng kiểu cố định, không object), vệt = `TripsLayer` với binary attributes của chunk đang phát; ở zoom ≤ 12 tự giảm `trailLength` và độ dày vệt để tránh vẽ chồng; chú giải/đếm trạng thái tính bằng một lần duyệt mảng mỗi 250 ms (không mỗi khung) | Tính vị trí trên GPU (shader nội suy) | CPU duyệt 8k xe × tìm nhị phân ~1 ms/khung — đủ; giữ được picking/tooltip như Sprint 03. Chuyển lên GPU chỉ khi đo không đạt |
| D17 | **FPS (AC04-8), chờ chốt — Q-D:** đo bằng `web/scripts/fps.mjs` như AC03-6 (Chrome 1920×1080, phát 60×, 60 s mỗi mức) trên replay `hanoi_greensm_day` khung 7h–9h: zoom 11 (toàn thành phố) và zoom 13. Ngưỡng: **GPU tích hợp Radeon 680M: trung vị ≥ 30 fps, p5 ≥ 20 fps; RTX 3050: trung vị ≥ 55 fps, p5 ≥ 30 fps**. Dung lượng replay một ngày và thời gian hiện khung hình đầu (≤ 5 s từ đĩa cục bộ) ghi vào backlog | Giữ ngưỡng của Sprint 03 (≥ 55/≥ 30) cho mọi GPU | Sprint ghi "tối thiểu ~30 fps"; 8k xe trên GPU tích hợp nặng hơn 300 xe ~27 lần |
| D18 | **Sửa lỗi đổi kết quả trong backlog — làm đầu sprint, đặt lại mốc:** **B02-4**: seed RNG của nguồn `fleetpy_demand`/`csv` dùng **tên file + sha256 nội dung** thay cho đường dẫn tuyệt đối; **B02-5**: `_environment_change` giữ giờ xuất phát của chặng chưa xuất phát (như `CONGESTION_UPDATE` đã làm). Đổi kết quả `road_example_400` và preset `accident`/`rain` — mốc benchmark mới đo sau bước này (Q-F) | Để sang sprint sau | Sprint này đặt lại mốc và dựng bộ golden; làm sau sẽ phải đặt lại mốc lần nữa |
| D19 | **Ghi solver/môi trường (B01-6):** `matching.solve` ghi solver thực dùng (`"hungarian"` hoặc `"greedy"` khi thiếu `scipy`) vào `sim.matching_solver_used`; snapshot run (DB) và kết quả bench ghi thêm `scipy` có/không, phiên bản Python, backend router; phát `RuntimeWarning` một lần khi `solver="hungarian"` mà phải rơi về greedy. Không báo lỗi (giữ hành vi 0.1, NFR-2) | Báo lỗi khi thiếu `scipy` | Báo lỗi phá ví dụ 0.1 trên Python không có `scipy` |
| D20 | **Không dùng song song/biên dịch thêm trong sprint này:** không Numba/Cython mới cho engine Python; không đa luồng. Chỉ sửa router C++ hiện có (D9) | Numba cho quét xe; chạy matching các vùng song song | Sau D6 phần quét không còn là O(N) ⇒ không cần; Numba thêm phụ thuộc nặng và khó giữ CRN/thứ tự. Xem lại nếu sau tầng chính xác vẫn > 30 phút |

### Câu hỏi mở cần người dùng chốt

- **Q-A (AC04-1):** mục tiêu PERF-2 = **≤ 30 phút wall-clock, ≤ 8 GB RAM** cho `hanoi_greensm_day` trên máy dev
  Ryzen 9 6900HS / 27 GB, env `fleetpy` + router C++, event log ghi dần; biến thể có xuất replay ≤ 40 phút (D1)?
- **Q-B:** đồng ý ngưỡng sai khác cho tầng tối ưu xấp xỉ (D11)? Hay chỉ chấp nhận tối ưu giữ kết quả giống hệt (nếu
  vậy, ALT và cắt thành phần gán sẽ không được bật trong `hanoi_greensm_day`)?
- **Q-C:** mẫu ca làm việc cho `hanoi_greensm_day` (D2) — đề xuất: 30% ca sáng 5h–13h, 25% ca ngày 9h–17h, 25% ca
  chiều 14h–22h, 15% hai đầu cao điểm 6h–10h + 16h–20h, 5% ca đêm 21h–5h; tổng 8.000 xe (5.000 ô tô + 3.000 xe
  máy như `weekday.json`). Có số liệu ca thật của GreenSM không?
- **Q-D (AC04-8):** ngưỡng FPS theo loại GPU (D17)?
- **Q-E:** `kami.replay` v2 **thay** v1 (fixture demo sinh lại, web chỉ đọc v2) — hay giữ web đọc cả hai?
- **Q-F:** đồng ý sửa B02-4 và B02-5 trong sprint này (đổi kết quả `road_example_400`, preset `accident`/`rain`; đặt
  lại mốc benchmark)?

## 3. Thay đổi theo module

| Module / file | Thay đổi | Interface công khai |
|---|---|---|
| `kami/core/spatial.py` (mới) | `AvailableIndex`: lưới ô, đăng ký điểm/lộ trình có khoảng thời gian, `nearest(x, y, t, k, accept)` | Nội bộ engine (policy dùng qua `Simulation`) |
| `kami/core/engine.py` | Dùng `AvailableIndex` trong `_quote_eta`, cập nhật chỉ mục ở các điểm đổi trạng thái/chặng; `_leg_position` bisect; tập xe rảnh / rider đang chờ duy trì sẵn; hazard gọn; B02-5 | Thêm `Simulation.nearest_available(node, k, accept=None)` (policy có thể dùng); `idle_drivers()` giữ nguyên kết quả |
| `kami/core/agents.py`, `kami/core/events.py` | `__slots__`; `Leg` thêm `frac` cache của lộ trình | Không đổi thuộc tính hiện có |
| `kami/matching.py` | `candidate_pairs` dùng `sim.nearest_available`; `solve` tách thành phần; `max_component`; ghi solver thực dùng | `MatchingParams.max_component: Optional[int] = None` |
| `kami/traffic.py`, `kami/network/road/network.py` | Cache giữ qua giờ tắc đường không đổi; `travel_and_path`; tái dùng `estimate` | Thêm `TrafficLayer.travel_and_path(o, d, t, group)` |
| `kami/network/road/cpp/*` | `computeRouteAndCost1To1`; (nếu cần) ALT + `setLandmarks` | Thêm phương thức `PyNetwork`; build lại router |
| `kami/eventlog.py` | `stream_to`, `close`, đếm dòng | Thêm API; `save`/`load` không đổi |
| `kami/trajectory.py`, `kami/replay/*` | Recorder có sink theo giờ; `kami.replay` v2 (export ghi dần, `validate`, `query`, CLI) | `schema_version: 2`; `python -m kami replay export/validate/demo` giữ cú pháp, thêm `python -m kami replay greensm` |
| `kami/scenario.py`, `kami/config/specs.py`, `kami/config/build.py` | `zonal.shifts`; B02-4; `outputs.event_log_mode`; `matching.max_component`, `routing.algorithm` (nếu làm ALT) | Trường spec mới tuỳ chọn, không tăng `schema_version` của RunSpec |
| `kami/bench.py`, `kami/cli.py` | `--suite scale`, `--profile`, `--pin-cpu`, so sánh theo `min`, ghi môi trường (B01-6) | Tuỳ chọn CLI mới; định dạng JSON kết quả thêm trường |
| `kami/store/runs.py` | Event log ghi dần; ghi môi trường vào snapshot | — |
| `benchmarks/specs/hanoi_peak_8k_1h.json`, `benchmarks/scale/hanoi_greensm_day.json` (mới) | Case mới | — |
| `tests/golden/` (mới), `tests/test_equivalence.py`, `tests/test_spatial_index.py`, `tests/test_eventlog_stream.py`, `tests/test_replay.py` (sửa cho v2), `tests/test_matching.py` (mới) | Test mới (xem §5) | — |
| `web/src/data/*`, `web/src/map/*` | Đọc v2 nhị phân theo chunk, binary attributes, tải dần | `ReplaySource.chunk(kind, hour)` |
| Tài liệu | `README.md` (bảng hiệu năng), `docs/engine/02-engine.md`, `10-matching-pooling-pricing.md`, `13-eventlog.md`, `20-visualizer.md`, `08-network-traffic.md`, `15-cli.md` | — |

## 4. Kế hoạch theo hạng mục

Thứ tự thực hiện: **S04-1 → S04-2 → (B02-4, B02-5, golden) S04-8 → S04-3 → S04-4 → S04-6 → S04-5 → S04-7 → S04-10 →
S04-9**. Sau mỗi bước tối ưu: chạy test golden + `hanoi_peak_8k_1h`, ghi số liệu vào bảng tiến độ trong backlog.

### S04-1 — Kịch bản benchmark `hanoi_greensm_day`
1. `zonal.shifts` trong `ZonalSourceSpec` (danh sách `{start_h, end_h, weight}`, ca qua nửa đêm và ca hai khúc) +
   sinh ca bằng cùng RNG của kịch bản; validate (trọng số > 0, giờ trong 0–48).
2. `benchmarks/scale/hanoi_greensm_day.json` (D2), `benchmarks/specs/hanoi_peak_8k_1h.json` (D3); tự bỏ qua khi
   mạng chưa build (như `hanoi_am_peak_small`).
3. `kami bench --suite scale`, `--repeat` mặc định theo bộ; `--pin-cpu`; so sánh theo `min` (D4); ghi môi trường (D19).
4. Đo **mốc trước tối ưu** của `hanoi_peak_8k_1h` và `hanoi_greensm_day` (chạy một lần; nếu cả ngày > 2 giờ thì ghi
   "> 2 giờ" kèm số giờ mô phỏng đã chạy được).

### S04-2 — Báo cáo profile ban đầu
1. `python -m kami.bench --profile <case>` (D5): cProfile + bảng nhóm + RSS theo bước.
2. Chạy trên `hanoi_am_peak_small`, `hanoi_peak_8k_1h` và 2 giờ đầu + 2 giờ cao điểm của `hanoi_greensm_day`.
3. Ghi `benchmarks/results/<ngày>-profile-*.md`; tóm tắt trong backlog. Xác nhận/điều chỉnh thứ tự ưu tiên của §1
   trước khi làm S04-3…S04-6 (nếu kết quả khác §1 nhiều → báo người dùng, đây là điểm chọn phương án routing B03-10).

### S04-8 — Kiểm tra tương đương (làm sớm, trước mọi tối ưu)
1. Sửa B02-4, B02-5 (D18) kèm test tái hiện (chạy `road_example_400` từ hai thư mục khác nhau → cùng kết quả; chặng
   đang cho khách lên xe khi mưa bắt đầu giữ `boarding_s`).
2. Dựng `tests/golden/equivalence.json`: với mỗi case (5 case lưới của bench, `road_example_400`, 8 preset × policy
   baseline, preset `accident`/`rain`, một case lưới có `heatmap_reposition` + `surge`, `hanoi_am_peak_small` khi có
   mạng) lưu `events_processed`, sha256 của toàn bộ event log (dòng đã chuẩn hoá JSON) và metric. Script sinh lại
   `python -m tests.golden.regen` (chỉ chạy khi chủ động đặt lại mốc).
3. `tests/test_equivalence.py` so từng case với golden. Mọi bước tối ưu chính xác phải giữ test này xanh.
4. Mỗi cờ xấp xỉ (ALT, `max_component`) có test ngưỡng D11 trên lát cắt nhỏ (giờ cao điểm 30 phút, 2.000 xe — để test
   chạy < 1 phút) và một lần đo trên `hanoi_peak_8k_1h` ghi vào backlog.

### S04-3 — Tối ưu sinh ứng viên matching
1. `AvailableIndex` (D6) + test riêng: so `nearest` với quét tuyến tính (hàm cũ giữ lại làm chuẩn trong test) trên
   10.000 truy vấn ngẫu nhiên seed cố định, gồm xe đứng yên, xe đang chạy, hoà khoảng cách, điều kiện tabu/sức chứa.
2. Gắn vào engine (cập nhật chỉ mục), `Simulation.nearest_available`.
3. `candidate_pairs` dùng chỉ mục; `_quote_eta` dùng chỉ mục (D7). Test golden xanh.
4. Đo lại `hanoi_peak_8k_1h`.

### S04-4 — Tối ưu routing
1. `_leg_position` bisect (D8).
2. C++ `computeRouteAndCost1To1` + `TrafficLayer.travel_and_path`; dùng cho chặng rảnh/điều xe (cần lộ trình cho
   chỉ mục). Build lại router, test đối chiếu C++ = Python giữ nguyên.
3. Cache qua giờ tắc đường không đổi; tái dùng `estimate` (D9 c-ii, c-iii).
4. Profile lại; **chỉ khi** chưa đạt D1 → ALT sau cờ (D9 b) + test D11.

### S04-6 — Hủy/hazard và tick định kỳ
1. (i)–(iii) của D12, test golden xanh.
2. Đo; nếu nhóm hazard/tick > 5% ở `hanoi_greensm_day` thì xem lại phương án.

### S04-5 — Giải gán batch lớn
1. Tách thành phần liên thông (D10); test: lời giải theo thành phần = lời giải toàn cục trên 1.000 bài toán ngẫu nhiên
   (tổng chi phí bằng nhau, và cùng cặp khi không có hoà); golden xanh.
2. `max_component` (tầng xấp xỉ) + test chất lượng ≤ 1% tổng ETA.
3. Đo kích thước batch lớn nhất trong `hanoi_greensm_day` (ghi backlog).

### S04-7 — Event log ghi dần + bộ nhớ agent
1. `EventLog.stream_to`/`close` (D13); test: file stream = file `save` từng dòng (Parquet và csv.gz), listener vẫn
   nhận đủ, `len(log)` đúng; replay export đọc lại từ file.
2. Nối vào `run --spec --out`, `kami.store` (`event_log_mode`), test CLI.
3. `__slots__` (D14), bỏ `leg.path` của chặng đã đóng khi không ghi quỹ đạo; chạy toàn bộ test + ví dụ 01–05.
4. Đo RSS đỉnh `hanoi_greensm_day` có/không streaming.

### S04-10 — Visualizer quy mô thành phố
1. Python: `kami.replay` v2 (D15) — writer nhị phân, chunk theo giờ, exporter ghi dần qua sink của
   `TrajectoryRecorder`, `validate` v2, `query` (cho test chéo với web); sinh lại fixture demo ở v2 (Q-E).
2. `python -m kami replay greensm` → `web/public/fixtures/hanoi_greensm_day/` (không commit, thêm vào `.gitignore`;
   ghi dung lượng, thời gian sinh).
3. Web: `parseChunk` (typed arrays), `ReplaySource.chunk`, bộ nạp dần theo giờ, layer binary (D16), đếm trạng thái
   theo nhịp 250 ms; Vitest: `stateAt`/`positionAt` của web = mẫu do Python `query` xuất (như AC03-3).
4. Đo FPS (D17) và thời gian hiện khung đầu; ảnh chụp toàn thành phố lúc 8h vào docs/engine/20.

### S04-9 — Tài liệu
Bảng hiệu năng mới trong `README.md`; `02-engine.md` (chỉ mục xe rảnh, tập duy trì, hai tầng tối ưu),
`10-matching-pooling-pricing.md` (ứng viên theo chỉ mục, tách thành phần, `max_component`), `13-eventlog.md`
(streaming), `08-network-traffic.md` (cache, `travel_and_path`, ALT nếu có), `20-visualizer.md` (v2, tải dần),
`15-cli.md` (`bench --suite/--profile/--pin-cpu`, `replay greensm`), `18-config-persistence.md` (trường spec mới).

## 5. Kiểm chứng acceptance criteria

| AC | Cách kiểm chứng |
|---|---|
| AC04-1 | Q-A được người dùng trả lời trong hội thoại; con số chốt ghi lại vào D1 và mục "Lịch sử thay đổi" khi duyệt plan |
| AC04-2 | `python -m kami bench --suite scale --repeat 1 --out benchmarks/results/<ngày>-sprint04-scale.json`: `wall_s` ≤ mục tiêu D1, `peak_rss_mb` ≤ 8.192, `requests` ≈ 100k, `drivers` = 8.000, mô phỏng tới hết 24h (+ drain). Chạy thêm biến thể có replay (`python -m kami replay greensm`) và ghi thời gian/RAM |
| AC04-3 | File kết quả trên + bảng "Số liệu mốc" trong `sprint-04-backlog.md` (wall-clock, sự kiện/s, RAM đỉnh cho cả hai bộ benchmark) |
| AC04-4 | `tests/test_equivalence.py` (golden, giống hệt từng sự kiện cho tầng chính xác); test ngưỡng D11 cho từng cờ xấp xỉ; test `AvailableIndex` = quét tuyến tính; test thành phần = Hungarian toàn cục |
| AC04-5 | Metric của `hanoi_greensm_day` (tỷ lệ hoàn thành, chờ TB/p90, tỷ lệ xe rỗng = 1 − utilization, quãng đường rỗng, chuyến/xe-giờ, theo giờ từ chuỗi metric) ghi vào backlog; tiêu chí "hợp lý" kiểm tay và ghi kèm: hoàn thành ÷ đặt 0,8–0,95, chờ p90 ≤ 15 phút ngoài giờ cao điểm, không giờ nào > 50% request bị hủy |
| AC04-6 | Bench `--suite scale --repeat 2` → cờ `deterministic: true` (metric và số sự kiện giống nhau giữa hai lần); test tự động hai lần chạy cho cùng sha256 event log trên lát cắt nhỏ có bật mọi cờ |
| AC04-7 | `python -m unittest discover -s tests -t .` (env `fleetpy` và Python hệ thống); `cd web && npm test && npm run typecheck && npm run build`; ví dụ 01–05 chạy |
| AC04-8 | `web/scripts/fps.mjs` trên replay `hanoi_greensm_day` (D17), kết quả + dung lượng replay (tổng, theo giờ) + thời gian hiện khung đầu ghi vào backlog và docs/engine/20 |

Định nghĩa xong chung: bench bộ nhanh `--compare` với mốc mới **sau B02-4/B02-5** (mốc trước sửa không so được cho
`road_example_400`, preset `accident`/`rain`); các case khác so với mốc Sprint 03.

## 6. Mock & phần dự kiến chưa làm

- Không dự kiến mock.
- Dự kiến chưa làm (sẽ ghi backlog nếu xác nhận): CCH (D9 d); gộp 3 truy vấn ETA thành X→1 (D7, tầng xấp xỉ); vị trí
  xe tính trên GPU (D16); ca làm việc theo fleet (Sprint 05); kiểm tra lại chi phí của sạc/pricing ở quy mô thành phố
  (Sprint 11).
- Profile tắc đường, demand theo zone, mẫu ca vẫn là **giả định** (B02-2) — số liệu vận hành của AC04-5 chỉ là mốc so
  sánh giữa các sprint, không phải hiệu chỉnh.

## 7. Rủi ro & phương án dự phòng

| Rủi ro | Phương án |
|---|---|
| Chỉ mục theo lộ trình (D6) phức tạp, dễ sót trường hợp (chặng bị ngắt giữa chừng, xe chuyển nhóm trạng thái) làm sai tập k gần nhất | Test đối chiếu với quét tuyến tính chạy **trong** engine ở chế độ kiểm tra (`KAMI_CHECK_INDEX=1`: mỗi truy vấn so với hàm cũ, dùng trong test golden); dự phòng: chỉ mục cho xe đứng yên + quét tuyến tính xe đang chạy (vẫn chính xác, chậm hơn) |
| Sau tầng chính xác vẫn > 30 phút | Bật lần lượt các cờ xấp xỉ (ALT, `max_component`) trong giới hạn D11; nếu vẫn chưa đạt → báo người dùng trước khi cân nhắc Numba/C++ cho vòng lặp sự kiện (D20) |
| `__slots__` phá code gán thuộc tính tuỳ ý lên agent (policy người dùng) | Giữ `attrs` dict cho dữ liệu tuỳ biến; chạy toàn bộ ví dụ + policy thư viện; nếu phá API 0.1 thì bỏ `__slots__` ở lớp đó |
| `linear_sum_assignment` chọn lời giải khác khi tách thành phần (hoà chi phí) | Phá hoà xác định bằng chi phí phụ rất nhỏ theo thứ hạng (id); nếu vẫn lệch golden thì ghi rõ trong backlog và xin người dùng chấp nhận |
| Replay một ngày quá lớn cho trình duyệt (> 150 MB) | Thêm mức chi tiết thô cho zoom ≤ 12 (ngưỡng giản lược 10 m / 2 s) tải trước, mức 1 m tải khi zoom gần |
| Máy dev bận (Chrome, dev server) làm nhiễu số đo | D4 (`min`, `--pin-cpu`), đo khi máy rảnh, ghi điều kiện đo |

## 8. Lịch sử thay đổi

| Ngày | Thay đổi | Người duyệt |
|---|---|---|
| 2026-10-08 | Tạo plan (số liệu §1 đo trên commit `c4c33c4` + working tree tài liệu) | — |
