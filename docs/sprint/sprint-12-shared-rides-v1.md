# Sprint 12 — Shared ride V1: ghép hai khách còn chờ

| | |
|---|---|
| Trạng thái | Xong |
| Yêu cầu | SR-1…SR-7, SR-8 (V1), SR-9, NFR-1, NFR-2, NFR-4, NFR-5, PERF-3 |
| Phụ thuộc | 01, 02, 03 đã Xong; tích hợp với phần A đã hiện thực của 08/09, không yêu cầu hoặc tuyên bố 08/09 đã Xong |
| Backlog đầu vào | [sprint-03-backlog.md](../backlog/sprint-03-backlog.md) — backlog chính thức mới nhất; không có backlog 11 vì Sprint 11 chưa kết thúc |
| Implementation plan | [sprint-12-plan.md](../implementation-plan/sprint-12-plan.md) — Đã thực hiện (2026-10-09) |

Sprint mới theo yêu cầu triển khai shared từng phiên bản ngày 2026-10-09; không đổi phạm vi/AC của các sprint
đang mở. Chi tiết V1 dưới đây đã được người dùng duyệt cùng plan ngày 2026-10-09.

## Mục tiêu

Chạy và quan sát được shared V1 từ library/CLI và manager: hai khách còn chờ được cùng xe nếu khả thi,
Shared Only không chủ động đi riêng, Exclusive Only không bị ghép.

## Phạm vi

- Hai lựa chọn Shared Only / Exclusive Only; tỷ lệ theo kịch bản hoặc lựa chọn riêng của request.
- Ghép đúng hai booking một người, cả hai WAITING; xe rảnh đủ hai chỗ, có tuyến đón/trả khả thi và overlap.
- V1 lọc điểm đón/điểm đến gần nhau, mặc định bán kính demo 500 m; đây là giới hạn của V1.
- Hạn đón tổng mặc định 600 s và phần tăng trên xe tối đa 450 s từng người; admin thay độc lập.
- Hủy do behavior, hủy vì timeout, mất đối tác trước/sau pickup; log, metric, snapshot và replay.
- Form manager cho cấu hình V1, kết quả thật từ service và demo replay sinh từ thuật toán thật.
- Cước Shared bằng 70% cước đi riêng từng booking, đã được người dùng chốt ngày 2026-10-09; báo trước khi đặt và giữ giá đã nhận.

## Ngoài phạm vi

Fallback, timer tìm ghép 300 s, báo giá fallback; V2 tìm theo tuyến; V3 gán xe sớm/ghép MATCHED;
V4 nhận request mới khi ONBOARD; ghép nối tiếp hoặc hơn hai booking; điểm đi bộ; ILP;
policy mới; hiện thực EV/sạc, sản phẩm và dynamic pricing của 05/06; API bản đồ live của 08/09 B;
tối ưu quy mô 100k request/8k xe thuộc 04.

## Hạng mục công việc

| Mã | Việc cần làm |
|---|---|
| S12-1 | Cấu hình shared, lựa chọn request, validation và snapshot tương thích |
| S12-2 | Đánh giá tuyến cặp từ xe thật, hạn đón/độ vòng/cam kết từng khách |
| S12-3 | Dispatch cặp WAITING cùng matching Exclusive; không dùng trùng khách/xe |
| S12-4 | Timeout, hủy và vòng đời mất đối tác nhất quán |
| S12-5 | Log và metric theo lựa chọn, cặp, overlap, dự đoán/vi phạm thực tế |
| S12-6 | Chạy V1 qua library/CLI/service; cấu hình và kết quả trên manager |
| S12-7 | Replay V1 và cách quan sát cặp/stop/overlap từ dữ liệu thật |
| S12-8 | Hồi quy, đối chứng, benchmark và tài liệu engine; kết thúc bằng backlog |
| S12-9 | Cước Shared 70%, báo giá, payout và metric tài chính nhất quán |

## Acceptance criteria

- [x] **AC12-1:** chỉ hai lựa chọn; Exclusive không xuất hiện trong cặp; cấu hình hữu hạn, tỷ lệ hợp lệ, mặc định deadline 600 s và extra ride 450 s; snapshot run cũ không đổi khi sửa kịch bản.
- [x] **AC12-2:** hai khách cùng một xe, bốn thứ tự đón/trả được xét; chọn tuyến tốt nhất theo cost đã công bố trong tập ứng viên. Không có người thứ ba, không vượt chỗ; request/xe không bị gán hai lần.
- [x] **AC12-3:** loại tuyến vi phạm deadline hoặc cận extra ride của riêng A/B, gồm dwell và đường xe tới đón; loại tuyến không đi được theo nhóm xe. V1 giữ giới hạn gần điểm cuối rõ ràng.
- [x] **AC12-4:** Shared Only không có cặp hết hạn thành CANCELLED với đúng lý do; MATCHED chưa đón hết hạn được dọn; pickup đúng hạn được chấp nhận, ONBOARD không bị timeout đón; không đặt lại booked_t/deadline.
- [x] **AC12-5:** hủy trước khi ai onboard giải cặp và đưa người còn lại tìm ghép với thời gian cũ; hủy sau một pickup giữ chuyến người onboard, không tăng giá; event cũ không đón/trả hai lần và accounting quãng đường không bị cộng trùng.
- [x] **AC12-6:** planned pair và actual overlap phân biệt; số đếm served/cancel/wait/detour theo lựa chọn đối chiếu được với log; metric vẫn đúng khi tắt record_events; vi phạm thực tế ghi riêng dự đoán.
- [x] **AC12-7:** tạo/sửa kịch bản, đổi phút/giây, chạy worker thật và đọc metric từ DB qua manager; snapshot bất biến. Không yêu cầu nhập JSON để bật/cấu hình V1; không đưa legacy policy/pooling vào API.
- [x] **AC12-8:** replay sinh từ V1 thật cho thấy cặp, hai khách và chuỗi stops/overlap; số liệu tại các mốc khớp engine; replay cũ vẫn đọc được, không đổi nhãn fixture thành run live.
- [x] **AC12-9:** cùng config/seed cho cùng log/metric/replay; shared tắt giữ log/metric/fixture baseline và API/CLI/ví dụ 0.1. Full Python và web checks pass; lõi không import DB/web.
- [x] **AC12-10:** có đối chứng cùng demand/seed và số liệu wall-clock, event/s, RAM, candidate/route query; benchmark baseline không thoái lui >10% nếu không có lý do. Backlog bắt buộc, ghi rõ giới hạn V1 và việc chuyển V2.
- [x] **AC12-11:** cước Shared đúng 70% cước đi riêng của từng booking; booking/behavior nhìn giá này từ đầu; không tăng giá do vòng/traffic/mất đối tác, không áp minimum Exclusive lần nữa. GMV/payout/phí đối chiếu được, không tính discount hoặc payout hai lần; không thu cước phục vụ từ khách chưa được phục vụ.

## Rủi ro & câu hỏi mở

- **Đã chốt cước:** Shared trả 70% cước đi riêng từng khách. Plan mô tả giữ công thức payout FareModel hiện có trên cước thực thu; không tuyên bố sàn thu nhập hoặc lợi nhuận đã được bảo đảm.
- **Đã duyệt cùng plan ngày 2026-10-09:** giới hạn V1 gần điểm cuối, một đối tác thực sự mỗi booking, ưu tiên dispatch tại plan D3.
- Hiệu năng tìm cặp có thể tăng nhanh theo demand; phải công bố heuristic/cắt ứng viên và đo chất lượng.
- EV/sản phẩm chưa hiện thực: chỉ kiểm chỗ/router/ca thật, không quảng bá pin hoặc tương thích sản phẩm đã được kiểm.
- Chưa chốt phương án giữ xe V3; không chặn V1 và không ngầm được duyệt cùng V1.

Kết quả nghiệm thu và giới hạn môi trường: [backlog Sprint 12](../backlog/sprint-12-backlog.md).
