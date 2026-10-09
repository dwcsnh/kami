# Yêu cầu kami 0.2 — mô phỏng vận hành GreenSM tại Hà Nội

> Nguồn: [`draft/draft.md`](../draft/draft.md). File này chuẩn hoá bản nháp thành các yêu cầu có **mã định danh** để
> sprint, implementation plan và backlog tham chiếu. Khi bản nháp thay đổi, cập nhật file này trước rồi mới sửa
> sprint. Shared ride được bổ sung theo yêu cầu trong hội thoại ngày 2026-10-09; không sửa bản nháp gốc.

## 1. Bối cảnh và mục tiêu

kami 0.1 là engine agent-based, discrete-event chạy bằng CLI/thư viện Python, mạnh ở phần **policy plugin, behavior
model và đánh giá nhân quả bằng CRN** (xem [engine/README.md](engine/README.md)). kami 0.2 biến engine đó thành
**nền tảng mô phỏng vận hành** cho một hãng gọi xe điện quy mô GreenSM tại Hà Nội: có bản đồ thật, nhiều fleet xe
điện cần sạc, dynamic pricing, cấu hình và chạy qua giao diện web.

**Phạm vi được mở rộng ngày 2026-10-09:** matching đi riêng và shared ride theo từng phiên bản, mỗi booking
một người, mỗi cặp đúng hai booking. Hiện chỉ có **Shared Only** và **Exclusive Only**; Shared Fallback Exclusive
tạm hoãn để người dùng nghiên cứu thêm. Hệ thống policy vẫn ngoài phạm vi; xem §5.

Các nguyên tắc của kami 0.1 vẫn giữ nguyên: policy chỉ tác động qua API của engine, hành vi là model tại điểm quyết
định, ngẫu nhiên đi qua CRN, phần ngoại sinh của kịch bản được replay y hệt cho mọi cấu hình.

## 2. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| **Vehicle type** (loại xe) | Mẫu xe: tên, nhóm (bike/car), số chỗ, quãng đường tối đa khi đầy pin, thông số sạc |
| **Fleet** | Một đội xe: tên, danh sách (vehicle type × số lượng), sản phẩm phục vụ (bike, car 4 chỗ, car 7 chỗ…) |
| **Charging station** | Trạm sạc: vị trí, số cổng, công suất |
| **Simulation scenario** (kịch bản) | Cấu hình một lần chạy: bản đồ, khung thời gian, demand, thời tiết/sự cố, fleet, seed |
| **Simulation run** | Một lần thực thi một kịch bản, có trạng thái, tiến độ, metric và event log |

## 3. Yêu cầu chức năng

### 3.1 Hiệu năng và quy mô — `PERF`

| Mã | Yêu cầu |
|---|---|
| PERF-1 | Mô phỏng trọn một ngày vận hành tại Hà Nội với **~100.000 request/ngày** và **~8.000 xe** trên mạng đường thật |
| PERF-2 | Thời gian chạy và bộ nhớ có mục tiêu đo được (đề xuất: ≤ 30 phút wall-clock và ≤ 8 GB RAM cho 1 ngày trên máy dev — **cần chốt**, xem §6) |
| PERF-3 | Có bộ benchmark cố định chạy lại được để phát hiện thoái lui hiệu năng sau mỗi sprint |
| PERF-4 | Khi bật visualizer/live metric, engine vẫn chạy nhanh hơn thời gian thực ít nhất nhiều lần (hệ số cụ thể **cần chốt**) |

### 3.2 Bản đồ, đường đi và giao thông — `MAP`

| Mã | Yêu cầu |
|---|---|
| MAP-1 | Dùng mạng đường thật của Hà Nội (OSM), theo định dạng mạng của FleetPy để tái sử dụng router C++ |
| MAP-2 | Xe di chuyển theo **lộ trình thật** trên mạng đường; lưu được quỹ đạo để vẽ lại |
| MAP-3 | Mô phỏng **tắc đường giờ cao điểm**: thời gian di chuyển thay đổi theo giờ và theo khu vực (zone × giờ) |
| MAP-4 | Hệ thống zone cho Hà Nội (quận/phường hoặc H3) dùng cho metric, surge và vùng sự cố |
| MAP-5 | Tốc độ khác nhau theo nhóm xe (xe máy và ô tô) và cấm đường theo nhóm xe nếu dữ liệu cho phép |

### 3.3 Loại xe và sạc xe — `EV`

| Mã | Yêu cầu |
|---|---|
| EV-1 | Có danh mục loại xe: **1 loại bike, 4–5 loại car**, mỗi loại có tên, số chỗ, quãng đường tối đa khi đầy pin, thời gian/công suất sạc |
| EV-2 | Mỗi xe theo dõi mức pin (SOC) giảm theo quãng đường đã đi; xe không thể nhận chuyến vượt quá quãng đường còn lại |
| EV-3 | Có hạ tầng sạc: trạm sạc với vị trí, số cổng, công suất; xe xếp hàng khi trạm đầy |
| EV-4 | Có **behavioral model cho quyết định sạc** của tài xế (khi nào sạc, sạc ở đâu, sạc đến mức nào), đi qua CRN như các điểm quyết định khác |

### 3.4 Fleet — `FLEET`

| Mã | Yêu cầu |
|---|---|
| FLEET-1 | Có thể có **nhiều fleet** trong một lần chạy; mỗi fleet gồm số lượng xe theo từng loại xe |
| FLEET-2 | Vehicle type có tối thiểu: tên, số km đi được tối đa trước khi phải sạc (và các thông số ở EV-1) |
| FLEET-3 | Cấu hình fleet và vehicle type **chỉnh được qua UI** và **lưu trong DB** |
| FLEET-4 | Request của khách gắn với một sản phẩm (bike/car…) và chỉ được phục vụ bởi fleet/loại xe phù hợp |

### 3.5 Dynamic pricing — `PRICE`

| Mã | Yêu cầu |
|---|---|
| PRICE-1 | Có interface chiến lược pricing, chọn và cấu hình tham số qua kịch bản; hiện thực lại các chiến lược của FleetPy (`TimeBasedDP`, `UtilizationBasedDP`) cùng `SurgePricing` hiện có |
| PRICE-2 | Giá ảnh hưởng tới **offer** gửi cho khách (giá, ETA, sản phẩm) |
| PRICE-3 | Quyết định **đặt / hủy** của khách phụ thuộc vào giá (độ co giãn theo giá), qua behavior model và CRN |
| PRICE-4 | Bảng giá theo sản phẩm (bike, các loại car) cấu hình được |

### 3.6 Chạy mô phỏng — `RUN`

| Mã | Yêu cầu |
|---|---|
| RUN-1 | Người dùng tạo và chạy kịch bản mô phỏng; hiện tại **chỉ cho phép 1 kịch bản chạy tại một thời điểm** |
| RUN-2 | Người dùng xem được kịch bản nào đang chạy (trạng thái, tiến độ) |
| RUN-3 | Mỗi kịch bản cấu hình được: chọn fleet nào (và các tham số kịch bản khác: bản đồ, khung giờ, demand, pricing, seed…) |
| RUN-4 | Metric của từng lần chạy được **lưu vào DB** |

### 3.7 Giao diện — `UI`

| Mã | Yêu cầu |
|---|---|
| UI-1 | **Simulation visualizer**: xem bản đồ mô phỏng (xe, khách, trạm sạc) cùng **live metric**. Chạy trên web, bản đồ **Mapbox** phóng to/thu nhỏ/nghiêng được, xe để lại **vệt đường chạy màu theo trạng thái**; tham khảo chức năng từ ảnh `draft/operation_visualizer_*.png` và video mẫu trong `draft/` (không sao chép phong cách). Giao diện hiện đại, **ưu tiên light mode**, **màu chủ đạo xanh Tiffany**. Có fixture demo (một số xe trong một khu vực Hà Nội) để xem trước khi có backend |
| UI-2 | Trang quản lý kịch bản mô phỏng |
| UI-3 | Trang quản lý fleet xe (và vehicle type) |
| UI-5 | Trang xem metric của các lần chạy (đọc từ DB), so sánh giữa các lần chạy |

### 3.8 Ghép chuyến — `SR`

Nguồn: [research](research/shared-rides.md), [lộ trình phiên bản](research/shared-rides-versions.md) và chỉ đạo
mới nhất ngày 2026-10-09. Bắt đầu V1; chi tiết hiện thực và các đề xuất của Sprint 12 chờ duyệt plan.

| Mã | Yêu cầu |
|---|---|
| SR-1 | Hai lựa chọn Shared Only / Exclusive Only. Shared Only chỉ dispatch khi có cặp khả thi; Exclusive Only luôn đi riêng, không tham gia ghép. Không fallback giữa hai lựa chọn |
| SR-2 | Một cặp gồm đúng hai booking, mỗi booking một người; đón/trả tại địa chỉ riêng, có thời gian onboard chồng lấn. V1 chỉ tạo cặp khi cả hai WAITING và có xe rảnh cùng tuyến khả thi |
| SR-3 | Hạn đón tính từ lúc đặt, mặc định demo `max_pickup_wait_s = 600`; Shared Only còn chờ mà không có cặp khi hết hạn chuyển CANCELLED, lý do `no_shared_match_timeout`. Khách đã MATCHED chưa pickup hết hạn hủy với `pickup_wait_timeout`. Exclusive Only dùng cùng hạn đón trong kịch bản bật shared. Pickup đúng hạn được xử lý trước timeout; không áp timeout đón cho ONBOARD |
| SR-4 | Tăng thời gian trên xe tối đa `max_shared_extra_ride_s = 450` riêng cho từng khách, gồm dừng/vòng phục vụ người kia; baseline trực tiếp cùng quy ước boarding. Kiểm tra pickup/dropoff đã cam kết, không nới deadline khi đổi plan. Ghi riêng dự đoán và vi phạm thực tế do traffic thay đổi |
| SR-5 | Admin cấu hình hai tỷ lệ lựa chọn, hạn đón, cận tăng thời gian và bán kính ứng viên theo kịch bản; UI dùng phút, engine giây/mét. Lưu cấu hình đã resolve trong snapshot. Shared tắt giữ hành vi kịch bản cũ và API/CLI/ví dụ 0.1 |
| SR-6 | Hủy một khách phải dọn stop/job/liên kết và giữ đồng hồ của người còn lại. Khi chưa ai onboard, người còn lại trở về tìm ghép theo lựa chọn. Khi đã có người onboard, tiếp tục chở tới điểm đến; ghi ngoại lệ mất đối tác, không tự tăng giá hoặc nhận khách thứ ba |
| SR-7 | Library, CLI, service và manager chạy được V1; log/metric/replay phân biệt lựa chọn, cặp đã lập và overlap thực tế. Báo served/cancel/wait/detour theo lựa chọn, km xe và vi phạm deadline; không coi có cặp là bằng chứng đã đi chung |
| SR-8 | Lộ trình V1 ghép WAITING gần điểm cuối → V2 ghép dọc tuyến → V3 ghép trước pickup khi xe đang tới đón. V4 nhận request mới khi ONBOARD là tùy chọn cuối, mặc định tắt. Mỗi bản có plan và nghiệm thu riêng, không triển khai các bản sau trong Sprint 12 |
| SR-9 | **Đã chốt ngày 2026-10-09:** mỗi khách Shared trả **70% cước Exclusive trực tiếp của chính booking đó**. Báo giá này trước quyết định đặt; giữ giá khi tìm lại đối tác, traffic đổi hoặc đối tác hủy. Không thu thêm quãng đường/thời gian vòng phục vụ người kia; Exclusive trả cước thông thường. Không dùng công thức tổng tuyến chung ×1,5 |

Bộ mặc định 600/450 giây là cấu hình **demo**, chưa hiệu chỉnh bằng dữ liệu Hà Nội. Mốc tìm ghép 300 giây
trong research cũ chỉ dành cho fallback, không có hiệu lực trong V1 hai lựa chọn hiện tại.
Giá Shared đã được người dùng chốt tại SR-9. Cước tham chiếu đi riêng dùng FareModel hiện có (phí ban đầu,
km, phút, surge và minimum); tính 70% sau khi có cước tham chiếu, không áp lại minimum Exclusive lên phần shared.
Các default FareModel là giả định mô phỏng, không phải biểu giá Green SM đã xác minh.

## 4. Yêu cầu phi chức năng

| Mã | Yêu cầu |
|---|---|
| NFR-1 | **Tái lập**: cùng kịch bản + cùng seed cho cùng kết quả |
| NFR-2 | **Tương thích**: API thư viện và CLI của kami 0.1 vẫn chạy; test hiện có không bị phá |
| NFR-4 | **Truy vết**: mỗi run lưu lại đầy đủ cấu hình đã dùng (snapshot fleet, loại xe, trạm sạc, kịch bản) |
| NFR-5 | Lõi engine vẫn dùng được không cần DB/UI (chế độ thư viện) |

## 5. Ngoài phạm vi (hiện tại)

- **Pooling legacy 0.1 và Shared Fallback Exclusive.** Shared mới thuộc §3.8; fallback tạm hoãn theo chỉ đạo
  ngày 2026-10-09. Các thành phần pooling của kami 0.1 được **giữ nguyên trong code** để API/CLI/ví dụ 0.1 vẫn chạy (NFR-2), nhưng **không dùng cho shared mới**: không
  đưa vào preset/kịch bản 0.2, danh mục policy plugin, policy group mặc định, UI, benchmark, và không phát triển thêm.
  Gồm: `kami/pooling.py` (`Pooling`, `PoolingParams`), policy `PoolAfterWait`, API `sim.merge_jobs` /
  `sim.pooling.*` / `sim.behavior.pool_accept`, slot behavior `pool_accept` (`PoolAcceptModel`, `LogitPoolAccept`,
  `PoolOffer`, thuộc tính khách `pool_willingness`), sự kiện `POOL_OFFER` / `POOL_MERGE`, metric `rider.pool_*`,
  `rider.pooled_*`, `rider.detour_ratio`, `platform.pooled_jobs`, `platform.surcharge_total`, quy tắc
  `pooling_rule_example`, ví dụ `examples/02_pool_after_wait.py`. Shared mới dùng cấu hình và module riêng,
  không mở lại policy plugin/group/agent.
- **Policy plugin, policy group và mọi tính năng xoay quanh policy** (trước đây là `POL-1`…`POL-6`, `EV-5`, `UI-4`,
  `NFR-3`): manifest/`params_schema`, plugin tuỳ biến lưu mã trong DB, sandbox chạy code policy, policy group
  (nhóm, bật/tắt thành viên), chọn policy group cho kịch bản, policy lưu DB qua API/UI, trang quản lý policy, policy
  agent sinh policy từ ngôn ngữ tự nhiên, hook policy điều xe đi sạc. Cơ chế `Policy` của kami 0.1 (`kami/policy/`,
  `POLICIES`, `Composite`, các policy dựng sẵn, bảng `policy`/`policy_version`/`policy_group` và `PolicySpec`/
  `PolicyGroupSpec` của Sprint 01) **giữ nguyên trong code** để API/CLI/ví dụ 0.1 và cấu hình hiện có vẫn chạy
  (NFR-2), nhưng không phát triển thêm và không đưa lên backend/UI 0.2. Matching, pricing của 0.2 là tham số của
  kịch bản. Khi đưa policy trở lại phạm vi, cập nhật mục này và thêm yêu cầu riêng.
- Chạy song song nhiều kịch bản trên giao diện (RUN-1 giới hạn 1 run/lần). Experiment nhiều seed vẫn chạy được
  qua thư viện/CLI.
- Đồng mô phỏng vi mô với SUMO (traffic mức 3).
- Xác thực người dùng nhiều vai trò, multi-tenant.
- Fit behavior model bằng dữ liệu thật của GreenSM (phụ thuộc dữ liệu; công cụ fit đã có trong `kami.training`).

## 6. Giả định và câu hỏi mở

| # | Câu hỏi | Giả định tạm |
|---|---|---|
| Q1 | Mục tiêu thời gian chạy cho PERF-2/PERF-4? | ≤ 30 phút / ngày mô phỏng; visualizer ≥ 60× thời gian thực |
| Q2 | Thông số thật của các loại xe (tên, pin, quãng đường, sạc)? | Dùng thông số công khai của các mẫu xe điện phổ biến làm seed data, chỉnh qua UI |
| Q3 | Vị trí và quy mô trạm sạc tại Hà Nội? | Seed data giả lập từ OSM (`amenity=charging_station`) + nhập tay |
| Q4 | Phân bố demand theo giờ/khu của Hà Nội? | Sinh synthetic theo profile giờ cao điểm; thay bằng dữ liệu thật khi có |
| Q5 | Công nghệ DB / backend / frontend? | DB quyết định trong plan Sprint 01 (đề xuất SQLite/PostgreSQL); bản đồ: **Mapbox** (người dùng chốt); framework frontend quyết định trong plan Sprint 03; backend trong plan Sprint 08 (đề xuất FastAPI) |
| Q6 | Giá Shared so với Exclusive ở V1? | **Đã chốt 2026-10-09:** Shared = 70% cước đi riêng của mỗi khách (SR-9). Toàn bộ plan V1 vẫn Chờ duyệt; fallback tạm hoãn |
