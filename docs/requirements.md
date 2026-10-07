# Yêu cầu kami 0.2 — mô phỏng vận hành GreenSM tại Hà Nội

> Nguồn: [`draft/draft.md`](../draft/draft.md). File này chuẩn hoá bản nháp thành các yêu cầu có **mã định danh** để
> sprint, implementation plan và backlog tham chiếu. Khi bản nháp thay đổi, cập nhật file này trước rồi mới sửa
> sprint.

## 1. Bối cảnh và mục tiêu

kami 0.1 là engine agent-based, discrete-event chạy bằng CLI/thư viện Python, mạnh ở phần **policy plugin, behavior
model và đánh giá nhân quả bằng CRN** (xem [engine/README.md](engine/README.md)). kami 0.2 biến engine đó thành
**nền tảng mô phỏng vận hành** cho một hãng gọi xe điện quy mô GreenSM tại Hà Nội: có bản đồ thật, nhiều fleet xe
điện cần sạc, dynamic pricing, policy lưu trong DB và cấu hình qua giao diện web.

Các nguyên tắc của kami 0.1 vẫn giữ nguyên: policy chỉ tác động qua API của engine, hành vi là model tại điểm quyết
định, ngẫu nhiên đi qua CRN, phần ngoại sinh của kịch bản được replay y hệt cho mọi cấu hình.

## 2. Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| **Vehicle type** (loại xe) | Mẫu xe: tên, nhóm (bike/car), số chỗ, quãng đường tối đa khi đầy pin, thông số sạc |
| **Fleet** | Một đội xe: tên, danh sách (vehicle type × số lượng), sản phẩm phục vụ (bike, car 4 chỗ, car 7 chỗ…) |
| **Charging station** | Trạm sạc: vị trí, số cổng, công suất |
| **Policy plugin** | Một đơn vị logic vận hành (matching, pricing, pooling, reposition, sạc, khuyến khích…) viết bằng code, có tham số khai báo được |
| **Policy group** | Tập policy plugin đã cấu hình tham số, áp cùng nhau cho một lần chạy |
| **Simulation scenario** (kịch bản) | Cấu hình một lần chạy: bản đồ, khung thời gian, demand, thời tiết/sự cố, fleet, policy group, seed |
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
| EV-5 | Policy có thể tác động vào việc sạc (ví dụ điều xe đi sạc ngoài giờ cao điểm) qua API của engine |

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
| PRICE-1 | Có interface chiến lược pricing dạng policy plugin; hiện thực lại các chiến lược của FleetPy (`TimeBasedDP`, `UtilizationBasedDP`) cùng `SurgePricing` hiện có |
| PRICE-2 | Giá ảnh hưởng tới **offer** gửi cho khách (giá, ETA, sản phẩm) |
| PRICE-3 | Quyết định **đặt / hủy** của khách phụ thuộc vào giá (độ co giãn theo giá), qua behavior model và CRN |
| PRICE-4 | Bảng giá theo sản phẩm (bike, các loại car) cấu hình được |

### 3.6 Policy — `POL`

| Mã | Yêu cầu |
|---|---|
| POL-1 | Policy plugin được thiết kế để **mô phỏng được policy ngoài đời thật bằng code** (đủ hook và API cho matching, pricing, pooling, reposition, sạc, khuyến khích tài xế…) |
| POL-2 | Có thể **tạo và nhóm** policy plugin thành **policy group** |
| POL-3 | Policy plugin và policy group **lưu được vào DB** (định nghĩa, tham số, phiên bản) |
| POL-4 | UI cho người dùng tự định nghĩa policy (chọn plugin, nhập tham số) và apply policy |
| POL-5 | Người dùng chọn được hệ thống đang **apply / không apply** policy nào |
| POL-6 | Có **policy agent** giúp người dùng tạo policy mới từ ngôn ngữ tự nhiên |

### 3.7 Chạy mô phỏng — `RUN`

| Mã | Yêu cầu |
|---|---|
| RUN-1 | Người dùng tạo và chạy kịch bản mô phỏng; hiện tại **chỉ cho phép 1 kịch bản chạy tại một thời điểm** |
| RUN-2 | Người dùng xem được kịch bản nào đang chạy (trạng thái, tiến độ) |
| RUN-3 | Mỗi kịch bản cấu hình được: chọn fleet nào, policy group nào (và các tham số kịch bản khác) |
| RUN-4 | Metric của từng lần chạy được **lưu vào DB** |

### 3.8 Giao diện — `UI`

| Mã | Yêu cầu |
|---|---|
| UI-1 | **Simulation visualizer**: xem bản đồ mô phỏng (xe, khách, trạm sạc) cùng **live metric**. Chạy trên web, bản đồ **Mapbox** phóng to/thu nhỏ/nghiêng được, xe để lại **vệt đường chạy màu theo trạng thái**; tham khảo chức năng từ ảnh `draft/operation_visualizer_*.png` và video mẫu trong `draft/` (không sao chép phong cách). Giao diện hiện đại, **ưu tiên light mode**, **màu chủ đạo xanh Tiffany**. Có fixture demo (một số xe trong một khu vực Hà Nội) để xem trước khi có backend |
| UI-2 | Trang quản lý kịch bản mô phỏng |
| UI-3 | Trang quản lý fleet xe (và vehicle type) |
| UI-4 | Trang quản lý policy, tích hợp policy agent |
| UI-5 | Trang xem metric của các lần chạy (đọc từ DB), so sánh giữa các lần chạy |

## 4. Yêu cầu phi chức năng

| Mã | Yêu cầu |
|---|---|
| NFR-1 | **Tái lập**: cùng kịch bản + cùng seed + cùng phiên bản policy cho cùng kết quả |
| NFR-2 | **Tương thích**: API thư viện và CLI của kami 0.1 vẫn chạy; test hiện có không bị phá |
| NFR-3 | **An toàn khi chạy code policy**: policy do người dùng hoặc agent sinh ra không được truy cập tuỳ ý hệ thống file/mạng, không làm treo engine |
| NFR-4 | **Truy vết**: mỗi run lưu lại đầy đủ cấu hình đã dùng (snapshot fleet, policy group kèm phiên bản, kịch bản) |
| NFR-5 | Lõi engine vẫn dùng được không cần DB/UI (chế độ thư viện) |

## 5. Ngoài phạm vi (hiện tại)

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
| Q6 | Model LLM cho policy agent và nơi chạy? | Quyết định trong implementation plan Sprint 10 |
