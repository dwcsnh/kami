# Sprint 06 — Dynamic pricing & phản ứng của khách

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | PRICE-1, PRICE-2, PRICE-3, PRICE-4 |
| Phụ thuộc | Sprint 05 (sản phẩm theo loại xe) |
| Backlog đầu vào | [sprint-05-backlog.md](../backlog/sprint-05-backlog.md) |
| Implementation plan | [sprint-06-plan.md](../implementation-plan/sprint-06-plan.md) (chưa có) |

## Mục tiêu

Có **chiến lược pricing dạng plugin**, gồm các chiến lược tham khảo từ FleetPy, tạo ra **offer** (giá, ETA, sản
phẩm) cho khách; khách **đặt hoặc hủy** dựa trên giá qua behavior model có độ co giãn theo giá, đi qua CRN.

## Phạm vi

- Bảng giá theo sản phẩm.
- Interface chiến lược pricing và các chiến lược tham chiếu.
- Offer gửi cho khách và cơ chế khách chọn/không chọn.
- Behavior model đặt/hủy nhạy với giá.
- Metric doanh thu và chuyển đổi.

## Ngoài phạm vi

- Khách chọn giữa nhiều hãng (thị trường cạnh tranh).
- Fit độ co giãn bằng dữ liệu thật (dùng giá trị giả định có ghi rõ, công cụ fit có sẵn trong `kami.training`).

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S06-1 | Bảng giá theo sản phẩm (`FareModel` theo bike/từng loại car): giá mở cửa, theo km, theo phút, giá tối thiểu, take rate; cấu hình qua spec và lưu DB |
| S06-2 | Interface `PricingStrategy` (một loại policy plugin): nhận trạng thái thị trường (cung/cầu theo zone, giờ, sản phẩm) và trả hệ số/giá cho offer; tương thích với hook `price()` hiện có |
| S06-3 | Hiện thực lại theo ý tưởng FleetPy: `TimeBasedDP` (hệ số giá theo khung giờ) và `UtilizationBasedDP` (hệ số giá theo tỷ lệ sử dụng fleet); chuyển `SurgePricing` hiện có sang interface mới. Ghi rõ điểm giống/khác FleetPy trong tài liệu |
| S06-4 | Offer: khi khách tạo request, engine sinh offer cho sản phẩm khách yêu cầu (tuỳ chọn: nhiều sản phẩm) gồm giá, ETA đón, ETA đến; offer có thời hạn |
| S06-5 | Behavior model đặt chuyến nhạy giá: xác suất đặt phụ thuộc giá (so với giá tham chiếu/ngân sách của khách), ETA, sản phẩm; thuộc tính cá nhân (độ nhạy giá) rút từ phân phối trong kịch bản |
| S06-6 | Behavior model hủy nhạy giá: hazard hủy khi chờ có thể phụ thuộc giá đã trả; giá thay đổi sau khi đặt (nếu policy cho phép) ảnh hưởng xác suất hủy |
| S06-7 | (Tuỳ chọn) Khách không đặt có thể yêu cầu lại sau một khoảng thời gian (re-request), tham số hoá và tắt được |
| S06-8 | Metric: tỷ lệ chuyển đổi offer → đặt, doanh thu, giá trung bình, hệ số surge trung bình theo zone/giờ, thu nhập tài xế, metric theo sản phẩm |
| S06-10 | Visualizer: lớp nhiệt (heatmap) theo zone cho hệ số surge/giá, cầu và cung rảnh; KPI doanh thu và giá trung bình trong bảng metric |
| S06-9 | Tài liệu: cập nhật `10-matching-pooling-pricing.md`, `06-behavior.md`, `11-metrics.md`, `16-fleetpy-integration.md` |

## Acceptance criteria

- [ ] AC06-1 Mỗi sản phẩm có bảng giá riêng; đổi bảng giá qua spec thay đổi giá trong event log tương ứng.
- [ ] AC06-2 Ba chiến lược (`TimeBasedDP`, `UtilizationBasedDP`, `SurgePricing`) chạy được qua spec, tham số khai báo được.
- [ ] AC06-3 Với `UtilizationBasedDP`, khi tỷ lệ sử dụng fleet tăng, hệ số giá không giảm (có test với kịch bản dựng sẵn).
- [ ] AC06-4 Tăng giá (giữ nguyên mọi thứ khác, cùng seed) làm tỷ lệ đặt giảm hoặc giữ nguyên, không bao giờ tăng
      — kiểm tra trên nhiều seed bằng `Experiment`.
- [ ] AC06-5 Event log ghi đủ offer (giá, ETA, sản phẩm, chiến lược đã dùng) và quyết định của khách.
- [ ] AC06-6 Khách bị cùng một rút ngẫu nhiên CRN ở hai arm có giá khác nhau (so sánh ghép cặp hợp lệ).
- [ ] AC06-7 Không bật chiến lược pricing nào thì kết quả giống hệt Sprint 05 (cùng seed).
- [ ] AC06-9 Visualizer hiển thị lớp nhiệt hệ số surge theo zone khớp hệ số ghi trong event log tại cùng thời điểm.
- [ ] AC06-8 Benchmark không thoái lui quá ngưỡng chung.

## Rủi ro & câu hỏi mở

- Độ co giãn theo giá là giả định: kết luận chỉ có ý nghĩa về **chiều**, chưa về độ lớn (nguyên tắc 8 của design doc).
- Cần chốt khách có được chọn giữa nhiều sản phẩm trong một offer hay không (ảnh hưởng S06-4/S06-5).
