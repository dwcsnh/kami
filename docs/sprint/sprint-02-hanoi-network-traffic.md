# Sprint 02 — Bản đồ Hà Nội & giao thông giờ cao điểm

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | MAP-1, MAP-2, MAP-3, MAP-4, MAP-5 |
| Phụ thuộc | Sprint 01 |
| Backlog đầu vào | [sprint-01-backlog.md](../backlog/sprint-01-backlog.md) |
| Implementation plan | [sprint-02-plan.md](../implementation-plan/sprint-02-plan.md) (chưa có) |

## Mục tiêu

Chạy mô phỏng trên **mạng đường thật của Hà Nội**, xe đi theo lộ trình thật, và thời gian di chuyển phản ánh **tắc
đường giờ cao điểm theo khu vực**. Cách làm tham khảo FleetPy: mạng ở định dạng `data/networks/<name>/base`, router
C++, travel time động theo mốc thời gian (`network_dynamics_file`).

## Phạm vi

- Pipeline tạo mạng Hà Nội từ OSM sang định dạng mạng FleetPy (tái tạo được bằng một lệnh).
- Zone cho Hà Nội.
- Mô hình tắc đường theo zone × giờ (thay cho hệ số giờ chung toàn thành phố hiện nay).
- Lộ trình và quỹ đạo xe theo thời gian.
- Phân biệt xe máy và ô tô trên mạng đường.

## Ngoài phạm vi

- Tối ưu hiệu năng ở quy mô 100k request (Sprint 03); sprint này chỉ cần chạy được ở quy mô vừa.
- Đồng mô phỏng SUMO, hiệu ứng xe của hãng làm tắc thêm (traffic mức 3).
- Hiển thị bản đồ (Sprint 09).

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S02-1 | Pipeline OSM → mạng FleetPy cho Hà Nội: phạm vi (ít nhất các quận nội thành + vùng ven có nhu cầu), lọc loại đường, liên thông mạnh, toạ độ, `crs.info`. Lưu phiên bản dữ liệu OSM đã dùng |
| S02-2 | Kiểm tra router C++ của FleetPy chạy được trên mạng Hà Nội; ghi kích thước mạng (node, cạnh) và thời gian truy vấn trung bình |
| S02-3 | Hệ thống zone Hà Nội: theo ranh giới hành chính (quận/phường) và/hoặc H3; ánh xạ node → zone; dùng được cho metric theo khu, surge, vùng sự cố |
| S02-4 | Mô hình tắc đường zone × giờ: hệ số tốc độ theo (zone hoặc loại đường) × khung giờ, có profile mặc định cho giờ cao điểm sáng/chiều của Hà Nội; cấu hình được qua `ScenarioSpec` |
| S02-5 | Cập nhật travel time theo mốc thời gian (cơ chế giống `network_dynamics_file` của FleetPy) và tính lại các chặng đang chạy khi tắc đường thay đổi đáng kể |
| S02-6 | Lộ trình thật: mỗi chặng của xe lưu chuỗi node và thời điểm đi qua; xuất được quỹ đạo dạng (lon, lat, t) của từng xe cho visualizer |
| S02-7 | Phân biệt nhóm xe trên mạng: hệ số tốc độ riêng cho xe máy và ô tô, và cấm cạnh theo nhóm xe nếu dữ liệu OSM có (ví dụ đường cấm xe máy) |
| S02-8 | Preset kịch bản Hà Nội: một ngày thường, giờ cao điểm sáng, mưa giờ cao điểm, sự cố trên trục chính; demand synthetic phân bố theo zone và giờ |
| S02-9 | Tài liệu: cập nhật `docs/engine/08-network-traffic.md`, `09-scenario.md`, `16-fleetpy-integration.md` |

## Acceptance criteria

- [ ] AC02-1 Một lệnh tạo lại mạng Hà Nội từ dữ liệu OSM đã ghi phiên bản; kết quả đọc được bằng `FleetPyNetwork`.
- [ ] AC02-2 ≥ 95% node của mạng nằm trong thành phần liên thông mạnh dùng được (`location_nodes`).
- [ ] AC02-3 Mỗi node thuộc đúng một zone; số zone và phạm vi được ghi trong tài liệu.
- [ ] AC02-4 Với cùng một cặp OD nội thành, thời gian di chuyển lúc 8h và 18h lớn hơn rõ rệt lúc 23h (theo profile
      cấu hình); có test kiểm tra chiều của hiệu ứng.
- [ ] AC02-5 Hai zone khác nhau trong cùng một giờ có thể có hệ số tắc khác nhau (không còn hệ số chung toàn thành phố).
- [ ] AC02-6 Quỹ đạo của một xe bất kỳ là chuỗi điểm nằm trên cạnh của mạng, thời gian tăng dần, khớp với các sự kiện
      `PICKUP`/`DROPOFF` trong event log.
- [ ] AC02-7 Cùng OD, xe máy và ô tô có thời gian khác nhau theo hệ số cấu hình; cạnh cấm theo nhóm xe không xuất hiện
      trong lộ trình của nhóm đó.
- [ ] AC02-8 Preset Hà Nội chạy được qua CLI với ≥ 10.000 request và ≥ 1.000 xe (chưa yêu cầu thời gian).
- [ ] AC02-9 Các kịch bản trên lưới synthetic và `example_network` của 0.1 cho kết quả không đổi (tương thích ngược).

## Rủi ro & câu hỏi mở

- Chưa có dữ liệu GPS thật để hiệu chỉnh tắc đường: profile mặc định là giả định, cần ghi rõ trong tài liệu.
- Mạng Hà Nội đầy đủ có thể quá lớn: có thể cần rút gọn (bỏ đường nội bộ nhỏ). Quyết định phạm vi trong plan.
- Dữ liệu cấm đường theo phương tiện trên OSM Hà Nội có thể thiếu.
