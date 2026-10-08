# Sprint 03 — Bản đồ vận hành (fleet operation visualizer) trên web

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | UI-1 (phần bản đồ + metric, chế độ phát lại), MAP-2 (hiển thị) |
| Phụ thuộc | Sprint 02 (mạng Hà Nội, quỹ đạo xe) |
| Backlog đầu vào | [sprint-02-backlog.md](../backlog/sprint-02-backlog.md) — liên quan: B02-9 (kích thước `trajectories.parquet`, định dạng fixture cho visualizer), B02-11 (đo lại mốc benchmark sau commit). Đầu vào dữ liệu: mạng `hanoi` + `trajectories.parquet` (`python -m kami run --spec scenarios/hanoi/am_peak.json --out out/hanoi`, docs/engine/02 mục "Quỹ đạo") |
| Implementation plan | [sprint-03-plan.md](../implementation-plan/sprint-03-plan.md) (chưa có) |

## Mục tiêu

Ngay sau khi có bản đồ Hà Nội (Sprint 02), người dùng **nhìn thấy** đội xe vận hành trên bản đồ thật trong trình
duyệt: xe chạy theo đường thật, để lại **vệt đường chạy tô màu theo trạng thái**, bản đồ phóng to/thu nhỏ/nghiêng
được, kèm bảng metric chạy theo đồng hồ mô phỏng. Dữ liệu lấy từ **fixture** do engine sinh ra cho một số xe trong
một khu vực, dùng để demo.

Sprint này cũng đặt **ngôn ngữ thiết kế** cho toàn bộ giao diện kami 0.2 (Sprint 09 dùng lại): giao diện hiện đại,
gọn, **ưu tiên light mode**, **màu chủ đạo xanh Tiffany**.

### Tài liệu tham khảo

Các ảnh và video trong [`draft/`](../../draft/) chỉ là tham khảo về **chức năng và cách hiển thị chuyển động**,
**không** phải mẫu giao diện cần sao chép:

| Tham khảo | Lấy gì |
|---|---|
| [`operation_visualizer_1.png`](../../draft/operation_visualizer_1.png) | Các loại thông tin cần có cạnh bản đồ: KPI, biểu đồ theo thời gian, đồng hồ mô phỏng, chú giải trạng thái |
| [`operation_visualizer_2.png`](../../draft/operation_visualizer_2.png) | Vệt xe màu theo trạng thái khi nhìn toàn khu vực; bảng metric thu gọn được |
| [`operation_visualizer_3.png`](../../draft/operation_visualizer_3.png) | Thu phóng gần, góc nghiêng 3D, bật/tắt từng loại vệt |
| Video mẫu trong `draft/` | Chuyển động của vệt đường chạy; thao tác zoom/xoay/nghiêng |

Không dùng lại phong cách của ảnh tham khảo (nền tối, viền neon, font số kiểu LED, bố cục 3 cột dày đặc).

### Định hướng thiết kế

- **Light mode là mặc định** và là chế độ được nghiệm thu; dark mode là tuỳ chọn (có thì tốt, không bắt buộc).
- **Màu chủ đạo: xanh Tiffany** (khoảng `#0ABAB5`, sắc độ chính xác và thang màu chốt trong plan) cho nhận diện,
  nút chính, trạng thái đang chọn, điểm nhấn của biểu đồ. Nền trắng/xám rất nhạt, chữ xám đậm.
- **Bản đồ là trung tâm**: chiếm phần lớn màn hình; các bảng điều khiển và metric là panel nổi/thanh bên gọn, thu
  gọn được, không che bản đồ.
- **Bản đồ nền sáng, ít chi tiết** (đường, nước, nhãn nhẹ) để vệt xe nổi bật.
- **Màu trạng thái xe** là một bảng màu riêng, phân biệt rõ với nhau và với màu Tiffany trên nền sáng, đạt độ tương
  phản đủ đọc; không dựa chỉ vào màu (chú giải có nhãn chữ).
- Phong cách hiện đại: font sans-serif rõ ràng, số liệu dạng tabular, bo góc, bóng đổ nhẹ, khoảng trắng hợp lý,
  chuyển động mượt nhưng tiết chế.

Ở sprint này visualizer **chỉ phát lại từ file** (không cần backend). Chế độ live, tích hợp vào ứng dụng quản lý và
các lớp dữ liệu của tính năng sau (sạc, surge, khách chờ) được bổ sung ở sprint tương ứng (xem "Ngoài phạm vi").

## Phạm vi

- Ứng dụng web chạy trên trình duyệt, dùng **Mapbox** (Mapbox GL JS) làm bản đồ nền và lớp hiển thị.
- Bộ nguyên tắc thiết kế (design tokens: màu, chữ, khoảng cách, bo góc; màu trạng thái xe) dùng chung cho kami 0.2.
- Định dạng dữ liệu phát lại (quỹ đạo + trạng thái xe + chuỗi metric theo thời gian) — là **hợp đồng dữ liệu** mà
  API của Sprint 08 sẽ trả về sau này.
- Lệnh sinh fixture demo từ engine trên mạng Hà Nội của Sprint 02.
- Trang visualizer ở mức dữ liệu engine hiện có (trạng thái: rảnh/cruising, đi đón, chở khách, reposition).

## Ngoài phạm vi

- Chế độ **live** đọc stream từ engine đang chạy, ghép visualizer vào ứng dụng Simulation manager, lọc theo
  fleet/loại xe (Sprint 08 cung cấp stream/API, Sprint 09 ghép vào UI).
- Hiển thị mượt ~8k xe toàn thành phố (Sprint 04 — hiệu năng quy mô).
- Lớp trạm sạc, SOC, trạng thái đi sạc/đang sạc (Sprint 05); lớp hệ số surge/giá (Sprint 06).
- PERF-4 (engine bật stream vẫn nhanh hơn thời gian thực) — nghiệm thu ở Sprint 09 khi có live, đo lại ở Sprint 11.
- Chỉnh sửa kịch bản trên bản đồ; mô hình xe 3D chi tiết; dark mode hoàn chỉnh (tuỳ chọn, có thể đưa vào backlog).
- Các trang quản lý (kịch bản, fleet, policy, metric) — Sprint 09.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S03-1 | Định dạng dữ liệu phát lại có `schema_version`: metadata (kịch bản, seed, khu vực, khung giờ, phiên bản kami), quỹ đạo từng xe (chuỗi `lon, lat, t` kèm trạng thái theo đoạn), sự kiện chính (đón, trả, hủy), chuỗi metric theo thời gian (S01-6). Có tài liệu và hàm kiểm tra hợp lệ |
| S03-2 | Xuất dữ liệu phát lại từ một lần chạy engine (dùng quỹ đạo của S02-6 và metric của S01-6); giản lược điểm trùng/thẳng hàng để giảm dung lượng mà không làm xe rời khỏi đường |
| S03-3 | **Fixture demo**: một lệnh sinh lại được (cùng seed → cùng file) một kịch bản trong **một khu vực nội thành Hà Nội** (ví dụ vài quận trung tâm, chốt trong plan) với **vài trăm xe** trong khoảng **1–2 giờ** mô phỏng có giờ cao điểm; file fixture được lưu trong repo hoặc sinh lại được bằng lệnh |
| S03-4 | Design tokens và bộ thành phần giao diện cơ bản theo "Định hướng thiết kế": thang màu Tiffany, màu nền/chữ/viền, bảng màu trạng thái xe, kiểu chữ, khoảng cách, bo góc, bóng; panel, nút, công tắc, thẻ KPI, thanh trượt thời gian. Viết sao cho Sprint 09 dùng lại được |
| S03-5 | Bản đồ nền Mapbox kiểu sáng, tối giản, hài hoà với màu Tiffany: pan, **zoom in/zoom out**, xoay, **nghiêng 2D/3D**; nút điều khiển bản đồ; tự căn khung vào khu vực của fixture; access token đọc từ cấu hình, không commit vào repo |
| S03-6 | Lớp xe di chuyển: vị trí nội suy theo quỹ đạo thật tại thời điểm đang xem; mỗi xe kéo theo **vệt đường chạy** ngắn mờ dần, màu theo trạng thái (cruising/rảnh, đi đón, chở khách, reposition) |
| S03-7 | Chế độ bản đồ quỹ đạo: vẽ tích luỹ các đoạn đường đã chạy đến thời điểm đang xem, màu theo trạng thái; chuyển qua lại giữa "xe di chuyển" và "quỹ đạo" |
| S03-8 | Chú giải trạng thái kiêm **công tắc bật/tắt từng loại vệt**, hiển thị số xe đang ở mỗi trạng thái |
| S03-9 | Điều khiển phát lại: play/pause, thanh thời gian để tua, tốc độ phát (1× … vài trăm×), đồng hồ mô phỏng hiển thị giờ hiện tại |
| S03-10 | Panel metric đồng bộ theo thời điểm đang xem, thu gọn/mở rộng được: KPI (đơn hoàn thành, đơn hủy, thời gian đón TB, thời gian chờ TB); biểu đồ đơn hoàn thành/hủy theo khung giờ; tỷ lệ xe theo trạng thái theo thời gian; thời gian chờ/đón của khách theo thời gian. Kiểu biểu đồ do plan chọn, theo design tokens |
| S03-11 | Chi tiết khi nhấp vào xe: mã xe, trạng thái, chuyến hiện tại, quãng đường đã chạy; làm nổi lộ trình của xe đó |
| S03-12 | (Tuỳ chọn) Chế độ bản đồ OD demand: cung nối điểm đón → điểm trả theo khung giờ |
| S03-13 | Tài liệu: thêm `docs/engine/19-visualizer.md` (định dạng dữ liệu, lệnh sinh fixture, cách chạy web, cấu hình token, design tokens) kèm ảnh chụp màn hình |

## Acceptance criteria

- [ ] AC03-1 Một lệnh sinh fixture demo trên mạng Hà Nội; chạy hai lần cùng seed cho file giống hệt; file qua được
      hàm kiểm tra hợp lệ của S03-1.
- [ ] AC03-2 Mở ứng dụng trên trình duyệt (theo hướng dẫn trong tài liệu) thấy bản đồ Mapbox nền sáng căn vào khu vực
      demo; zoom in/out, xoay, nghiêng 3D hoạt động.
- [ ] AC03-3 Khi phát, xe di chuyển trên đường của mạng (không đi xuyên khối nhà), có vệt đường chạy mờ dần, màu khớp
      trạng thái trong event log tại cùng thời điểm (kiểm tra tự động trên mẫu điểm của fixture + kiểm tra bằng mắt).
- [ ] AC03-4 Bật/tắt từng loại vệt theo trạng thái và chuyển chế độ "xe di chuyển" ↔ "quỹ đạo" hoạt động.
- [ ] AC03-5 Tua đến thời điểm bất kỳ: vị trí xe, vệt và panel metric hiển thị đúng trạng thái tại thời điểm đó; số
      liệu KPI khớp chuỗi metric engine xuất ra.
- [ ] AC03-6 Fixture demo (vài trăm xe) phát mượt (≥ 30 fps trên máy dev, con số chốt trong plan) ở mọi mức thu phóng.
- [ ] AC03-7 Giao diện ở light mode dùng màu chủ đạo xanh Tiffany theo design tokens; màu các trạng thái xe phân biệt
      được với nhau và với nền bản đồ; chữ và số liệu đạt độ tương phản tối thiểu WCAG AA.
- [ ] AC03-8 Trang có đủ các khối: bản đồ, KPI, biểu đồ, đồng hồ mô phỏng + điều khiển phát lại, chú giải/công tắc
      trạng thái; dùng được trên màn hình ≥ 1280px; panel thu gọn được để xem bản đồ toàn màn hình; có ảnh chụp
      trong tài liệu.
- [ ] AC03-9 Lõi engine không import thư viện web (NFR-5); test cũ vẫn pass.

## Rủi ro & câu hỏi mở

- Mapbox cần access token và có giới hạn sử dụng miễn phí; cần token của người dùng cho môi trường dev/demo.
  (Phương án dự phòng nếu cần: MapLibre với cùng API — chỉ dùng khi người dùng đồng ý.)
- Vệt màu trên nền sáng kém nổi hơn trên nền tối: bảng màu trạng thái và độ dày/độ mờ của vệt cần thử trên bản đồ
  thật; plan đưa ra 1–2 phương án (có ảnh chụp) để người dùng chọn.
- Sắc độ xanh Tiffany cụ thể và kiểu bản đồ nền (style Mapbox có sẵn hay tự chỉnh) — chốt trong plan.
- Chọn khu vực và quy mô fixture (số xe, khung giờ) để vừa nhìn rõ vừa đủ "đông" — chốt trong plan.
- Định dạng S03-1 sẽ được Sprint 08 dùng làm định dạng API quỹ đạo: cần đủ tổng quát (nhiều fleet, thêm trạng thái
  sạc ở Sprint 05) mà không phải đổi phiên bản lớn.
- Công nghệ frontend (requirements Q5) chốt trong plan sprint này và được Sprint 09 dùng lại.
