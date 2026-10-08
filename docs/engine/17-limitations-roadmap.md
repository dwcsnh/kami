# 17 · Giới hạn & lộ trình

> **Lộ trình hiện hành đã chuyển sang [docs/sprint/](../sprint/README.md)** (kami 0.2, theo
> [requirements.md](../requirements.md)). File này giữ lại bức tranh giới hạn của kami 0.1 và ghi sprint nào xử lý
> từng giới hạn.

## Trạng thái so với lộ trình của design doc §13

| Giai đoạn | Nội dung | Trạng thái trong kami 0.1 |
|---|---|---|
| 0. Prototype | Engine tối giản, policy plugin, CRN, synthetic | ✅ Có, và mở rộng thành engine đầy đủ |
| 1. MVP | Zone, ETA theo giờ, behavior logit, bộ metric đầy đủ (p90, độ vòng, km rỗng, theo khu) | ✅ Zone vuông/FleetPy/H3 (tuỳ chọn), metric đủ theo §10.2 |
| 2. Data-driven | Replay đơn lịch sử, survival model hủy, ma trận chuyển, model registry | 🟡 Đã có công cụ (replay CSV/FleetPy, `fit_*`, registry); **chưa có dữ liệu thật của hãng** |
| 3. Môi trường | Thời tiết, sự cố, thư viện kịch bản | ✅ Mức 1 và 2 của traffic layer; 8 preset |
| 4. Quy mô & tối ưu | Song song, grid search tham số policy, dashboard | 🟡 Có song song (`n_jobs`) và `policy_grid`; **chưa có dashboard** (chỉ có report Markdown) |
| 5. Vòng phản hồi | Đối chiếu A/B thật, day-to-day learning, RL | ❌ Chưa làm |

## Giới hạn mô hình hiện tại

1. **Behavior model mặc định là giả định.** Độ lớn hiệu ứng chưa có ý nghĩa thực tế cho tới khi fit bằng dữ liệu
   của hãng. Đặc biệt mô hình nhận ghép có phụ phí chưa có dữ liệu (design doc §14.1).
2. **Traffic:**
   - ~~hệ số giờ và thời tiết áp chung cho cả thành phố, chưa theo zone × giờ~~ — Sprint 02: tắc đường zone × giờ ×
     loại đường × nhóm xe (docs/engine/08); profile mặc định là **giả định**, chưa hiệu chỉnh bằng GPS;
   - chặng đã xuất phát được tính lại khi thời tiết, sự cố hoặc chu kỳ tắc đường đổi (từ Sprint 02); travel time
     của một chặng không tích phân theo thời gian trong chặng;
   - chưa có hạn chế rẽ và thời gian chờ đèn ở nút giao;
   - chưa có hiệu ứng ngược (xe rỗng làm tắc thêm), cần mức 3 (SUMO).
3. **Pooling** *(ngoài phạm vi 0.2 — sản phẩm hiện chỉ matching 1 tài xế – 1 khách; requirements §5)*:
   - chỉ ghép do policy kích hoạt và chỉ tính cặp (khách + khách hoặc khách + plan có sẵn), chưa có ghép batch tối
     ưu toàn cục;
   - `plan_pair` coi điểm xuất phát là điểm đón của khách thứ nhất;
   - ràng buộc vòng chỉ kiểm tra trên ETA ước lượng.
4. **Tài xế:**
   - mô hình cung lao động đơn giản (`ScheduledShift`, `IncomeTargetShift`);
   - chưa có học qua nhiều ngày (mức 4 của §5);
   - chưa có sạc xe điện.
5. **Khách:**
   - không đặt lại sau khi hủy hoặc không đặt;
   - chưa mô hình hoá việc chọn giữa nhiều sản phẩm (xe riêng hay ghép ngay từ đầu).
6. **Kinh tế:**
   - `contribution_margin` hiện bằng revenue, chưa có sổ chi phí khuyến khích (Quest/Boost, trợ giá) hay chi phí
     vận hành;
   - phí hủy chưa được mô hình hoá.
7. **Thí nghiệm:** chưa mô phỏng interference giữa nhóm A/B trong cùng thị trường (switchback, chia theo vùng),
   tức tiêu chí 5 ở §14.
8. **Hiệu năng:**
   - mạng lưới synthetic chạy khoảng 1.000 request trong dưới 1 giây;
   - mạng đường thật nên dùng router C++ (router Python chậm khoảng 12–15 lần);
   - quy mô hàng trăm nghìn chuyến/ngày cần profile lại phần matching và hazard, và cân nhắc Numba/Cython như §12
     gợi ý.

## Giới hạn → sprint kami 0.2

| Giới hạn (mục ở trên) | Sprint xử lý |
|---|---|
| 2. Traffic chung toàn thành phố, chưa theo zone × giờ | [Sprint 02](../sprint/sprint-02-hanoi-network-traffic.md) — xong (giả định, chưa hiệu chỉnh GPS) |
| 4. Chưa có sạc xe điện | [Sprint 05](../sprint/sprint-05-fleet-ev-charging.md) |
| 5. Khách không đặt lại; chưa chọn sản phẩm | [Sprint 05](../sprint/sprint-05-fleet-ev-charging.md) (sản phẩm), [Sprint 06](../sprint/sprint-06-dynamic-pricing.md) (re-request) |
| 6. Chưa có sổ chi phí khuyến khích, phí hủy | [Sprint 07](../sprint/sprint-07-policy-v2-groups.md) |
| 8. Hiệu năng quy mô hàng trăm nghìn chuyến/ngày | [Sprint 04](../sprint/sprint-04-scale-performance.md) |
| Chưa có dashboard / animation quỹ đạo | [Sprint 03](../sprint/sprint-03-map-visualizer.md) (bản đồ vận hành, phát lại), [Sprint 09](../sprint/sprint-09-ui-simulation-manager.md) (simulation manager, visualizer live) |
| 1. Behavior model chưa fit bằng dữ liệu thật; 3. pooling / ghép batch tối ưu; 4. day-to-day; 7. interference A/B | Chưa xếp sprint (ngoài phạm vi 0.2, xem requirements §5) |

## Việc nên làm tiếp (danh sách gốc của kami 0.1)

1. **Nạp dữ liệu thật:** chuyển đơn lịch sử sang `from_csv`, fit 3 model (hủy, nhận cuốc, đi đâu khi rảnh) và hiệu
   chỉnh baseline theo `by_hour`/`by_zone` (§11).
2. **Chốt mô hình lao động của tài xế** (§6.2): nhân viên dùng `BehaviorSuite.employed_drivers()`; đối tác tự do
   cần fit `LogitDriverAccept` và một shift model thật.
3. **Khảo sát SP hoặc A/B nhỏ cho phụ phí ghép**, rồi thay `LogitPoolAccept` mặc định *(chỉ khi shared ride vào
   phạm vi)*.
4. **Ma trận ETA theo zone × giờ × thời tiết** từ GPS: từ Sprint 02 chỉ cần file `zone,hour,factor`
   (`traffic.congestion.kind = "file"`, docs/engine/08).
5. **Dashboard** so sánh baseline và treatment (đọc `ExperimentResult.to_csv` và event log); animation quỹ đạo bằng
   deck.gl `TripsLayer`.
6. **Ghép batch tối ưu:** tận dụng thuật toán Alonso-Mora của FleetPy (cần tách khỏi `FleetControlBase`) hoặc một
   ILP nhỏ.
7. **Day-to-day:** chạy chuỗi ngày, cập nhật `attrs` của tài xế (thu nhập kỳ vọng) và của khách (trải nghiệm),
   kiểm tra cân bằng dài hạn (§10.4 tiêu chí 5).
8. **Mô phỏng thiết kế thí nghiệm thật:** policy switchback theo khung thời gian và chia theo vùng, để chọn thiết kế
   A/B (§14.5).
