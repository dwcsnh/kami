# Các phiên bản phát triển shared ride trong kami

| | |
|---|---|
| Ngày cập nhật | 2026-10-09 |
| Trạng thái | Đã yêu cầu bắt đầu theo phiên bản; plan V1 Chờ duyệt, chưa viết code |
| Cơ sở | [Research lịch sử](shared-rides.md) và chỉ đạo mới nhất trong hội thoại ngày 2026-10-09 |
| Phạm vi hiện hành | **Shared Only / Exclusive Only**; hai booking, mỗi booking một người; đón/trả tại địa chỉ riêng |
| Tạm hoãn | Shared Fallback Exclusive: người dùng nghiên cứu thêm, chưa triển khai |
| Bản đầu | [Sprint 12](../sprint/sprint-12-shared-rides-v1.md), [implementation plan V1](../implementation-plan/sprint-12-plan.md) |

Các số V1–V4 là phiên bản tính năng shared, không phải số release kami hoặc số sprint.
Đi từng bản: duyệt plan → implement → kiểm chứng → backlog → lập plan bản tiếp theo theo [AGENTS.md](../../AGENTS.md).
Yêu cầu bắt đầu implement không thay cho việc duyệt plan cụ thể.

## 1. Hai lựa chọn hiện tại

| Lựa chọn | Quy tắc |
|---|---|
| **Shared Only** | Chỉ gán xe khi có cặp thực sự khả thi. Không có cặp thì tiếp tục tìm trong hạn đón; quá hạn khách hủy, không chuyển Exclusive |
| **Exclusive Only** | Matching đi riêng từ đầu; không tham gia cặp ở bất kỳ bản nào |

Không có lựa chọn thứ ba, timer fallback hoặc hành vi tự chuyển dịch vụ trong bản hiện tại.
`service_preference` giữ lựa chọn ban đầu; lifecycle WAITING/MATCHED/ONBOARD/DONE/CANCELLED độc lập với mode,
planned pair và overlap thực tế. Tỷ lệ lựa chọn theo kịch bản hoặc giá trị từng request đều cấu hình được.

Mỗi cặp đúng hai booking, mỗi booking một người; không nhận khách thứ ba. Đề xuất mỗi booking chỉ có một
đối tác thực sự; được tìm lại sau khi cặp bị hủy trước overlap nhưng giữ mọi đồng hồ. Không ghép nối tiếp A–B rồi A–C
sau khi đã có overlap; chi tiết D9 của plan V1 cần duyệt.

## 2. Giới hạn từ V1

| Tham số | Mặc định demo | Quy tắc |
|---|---:|---|
| `max_pickup_wait_s` | 600 s — 10 phút | Tổng từ đặt tới pickup, không chỉ tới matching; dùng cho hai lựa chọn trong kịch bản bật shared |
| `max_shared_extra_ride_s` | 450 s — 7,5 phút | Phần tăng trên xe tối đa riêng cho từng khách, gồm vòng/dừng phục vụ người kia |
| `candidate_radius_m` | 500 m | V1 lọc gần điểm đón/điểm cuối; các bản sau lọc quanh tuyến; không phải bảo đảm khả thi |
| `latest_pickup/latest_dropoff` | Theo cam kết đã có | Cận chặt hơn phải giữ, không nới khi đổi plan |

600/450 giây đã được người dùng chọn trước đó cho demo, chưa hiệu chỉnh bằng dữ liệu Hà Nội.
Mốc **300 s** trong bản nghiên cứu cũ là cửa sổ fallback; **không có hiệu lực trong V1 hai lựa chọn**.
Admin chỉnh độc lập từng tham số, UI phút và engine giây/mét; snapshot lưu giá trị đã resolve.
Shared tắt không làm đổi default hoặc kết quả baseline/API 0.1.

- Shared Only WAITING không có cặp tới `booked_t + max_pickup_wait_s`: CANCELLED, `no_shared_match_timeout`.
- WAITING/MATCHED chưa được đón tới hạn chung: hủy với lý do phù hợp, dọn stop/job/liên kết. Với Shared Only
  đã MATCHED chưa pickup, lý do `pickup_wait_timeout`; không đổi booked_t hoặc kéo deadline.
- Pickup tại đúng deadline được xử lý trước timeout; khách ONBOARD không bị hủy vì hạn đón.
- Behavior có thể hủy sớm; đối tác hủy không đặt lại thời gian của người còn lại.
- Cặp tìm thấy ở 9:30 nhưng xe phải mất hai phút tới đón bị reject vì deadline, dù chưa hết thời gian tìm.
- Timestamp pickup hiện ghi lúc xe tới điểm đón. Baseline trực tiếp phải cùng quy ước: boarding của chính khách
  cộng direct travel; dừng đón/trả người kia tính vào phần tăng. Không dùng trung bình để che một khách vượt cận.
- Traffic thay đổi có thể làm actual vượt predicted; log/metric tách hai giá trị, không quảng bá cận như cam kết thực tế luôn đạt.

Config hữu hạn, wait >0, extra >=0, radius >0; tỷ lệ không âm và tổng >0. Không thêm giới hạn nghiệp vụ tùy ý
cản thí nghiệm. Lựa chọn chưa hỗ trợ bị từ chối rõ, không âm thầm đổi chế độ.

## 3. Lộ trình từng phiên bản

| Bản | Phạm vi | Trạng thái được nhận đối tác mới | Tìm ứng viên | Trạng thái kế hoạch |
|---|---|---|---|---|
| **V1** | Ghép hai khách còn chờ; hai lựa chọn; deadline/hủy; service/UI/metric/replay | Cả hai WAITING | Gần điểm đón và điểm cuối; route thật từ xe rảnh | Sprint 12, plan Chờ duyệt |
| **V2** | Điểm trả B có thể nằm giữa hành trình A | Cả hai WAITING | Quanh tuyến, xét hai hướng A/B | Lập plan sau nghiệm thu V1 |
| **V3** | Nhận đối tác trước pickup khi xe đang tới đón | WAITING hoặc MATCHED, còn shared | Phần tuyến còn lại từ vị trí xe hiện tại | Lập plan sau V2; giữ xe cần review riêng |
| **V4 tùy chọn** | Nhận request mới khi đã có khách onboard | Thêm ONBOARD nếu còn đủ điều kiện | Phần tuyến còn lại và thời gian đã đi | Bản cuối, mặc định tắt; chỉ triển khai khi được yêu cầu |

V1–V3 vẫn có thể đón B sau khi A đã lên xe nếu B **đã nằm trong cặp/plan từ trước**. Chỉ nhận một request B
mới sau khi A ONBOARD mới thuộc V4. Lộ trình chính V1 → V2 → V3; fallback không phải điều kiện hoàn thành.

## 4. V1 — Ghép hai khách còn chờ

Shared Only chỉ dispatch sau khi đã có cặp và xe thực sự khả thi. Exclusive đi riêng.
V1 tạm yêu cầu hai điểm cuối gần nhau; trường hợp điểm trả giữa tuyến nhưng xa điểm cuối chuyển V2.

1. Queue theo hai lựa chọn, tạo deadline đón từ lúc đặt; không tạo timer fallback.
2. Tìm cặp WAITING và xe rảnh đủ chỗ, lọc vị trí/khả năng đi đường theo nhóm xe.
3. Từ vị trí xe thật, thử P_A–P_B–D_A–D_B, P_A–P_B–D_B–D_A, P_B–P_A–D_A–D_B, P_B–P_A–D_B–D_A.
4. Cộng dwell, kiểm deadline/extra ride/cam kết riêng A/B; require overlap thực sự.
5. Chọn greedy theo deadline/cost/ID ổn định; tài xế nhận trước commit, không gán trùng request/xe.
6. Không nhận đối tác mới vào xe đã gán trong V1. Không có cặp khi quá hạn thì khách hủy.

Khi đối tác hủy trước khi ai onboard, giải cặp/xe và cho người còn lại tìm lại, giữ booked_t/deadline/hazard.
Khi đã có người onboard, tiếp tục chở tới destination, không bỏ giữa đường hoặc tự tăng giá; log mất đối tác.
Planned pair không đồng nghĩa actual share: có thể không overlap vì người kia hủy.

**Người dùng đã chốt ngày 2026-10-09:** mỗi khách Shared trả 70% cước đi riêng của chính booking đó.
Báo giá trước khi đặt và giữ giá khi traffic đổi/tìm lại đối tác/đối tác hủy. Không chọn tổng tuyến chung ×1,5.
[Nghiên cứu cước](shared-rides-pricing.md) giữ các phương án khác để tham khảo; D10/S12-9/AC12-11 của plan
đã cập nhật theo quyết định 70%. Toàn bộ plan vẫn Chờ duyệt; fallback tạm hoãn.

Tiêu chí V1 được chuyển thành **AC12-1…AC12-10** ở sprint, với test/lệnh cụ thể trong plan.
Không dùng tiêu chí ba lựa chọn của bản research lịch sử để nghiệm thu.

## 5. V2 — Ghép dọc hành trình

Bỏ giới hạn điểm cuối gần nhau; hai khách vẫn WAITING. B có thể được đón và trả ở giữa tuyến A.
Dựng tuyến tham chiếu, lọc khoảng cách pickup/dropoff B tới tuyến, xét cả B vào A và A vào B,
rồi evaluator V1 kiểm bốn tuyến thật từ xe cụ thể và cam kết từng khách.

Gần hình học không bảo đảm đi được vì đường một chiều/quay đầu. Đây là heuristic có thể bỏ lỡ cặp;
so oracle bài nhỏ, ghi candidate/query và chất lượng. Chỉ dựng path khi cần lọc/ghi phương án.

Kiểm chứng: D_B giữa tuyến và xa D_A được nhận; gần tuyến nhưng route thật vượt hạn bị loại; cả hai hướng
đều được xét; test V1, CRN, benchmark và replay vẫn đúng. Phạm vi/AC chính thức lập khi bắt đầu V2.

## 6. V3 — Ghép khi xe đang tới đón

Cho nhận B mới trước khi A pickup. Shared Only vẫn chưa được chủ động xuất phát một mình.
Đề xuất xe có thể tới đón trước khi tìm được đối tác và giữ chờ có hạn **chưa được duyệt**; cần plan riêng,
bao gồm chi phí giữ xe, dwell và tình huống xe tới sớm không có cặp.

Có thể chọn phạm vi hẹp hơn: chỉ tìm lại đối tác của cặp cũ bị hủy trước pickup. Không mặc định yêu cầu hiện tại
đã chấp thuận phương án giữ xe. Dùng current_loc/partial leg/plan_version, không teleport hoặc mất km đã đi;
booked_t/deadline và cam kết cũ giữ nguyên.

Kiểm chứng: B tới khi A MATCHED có thể ghép nếu shared/cam kết cho phép; Exclusive hoặc A ONBOARD không
được nhận B mới; xe tới sớm không cho Shared Only đi riêng; event cũ không đón/trả hai lần;
đo cặp mới trước pickup, thời gian giữ xe và hồi quy V1/V2. Không có fallback trong V3 hiện hành.

## 7. V4 — Nhận khách mới khi ONBOARD, tùy chọn cuối

Chỉ mở khi V1–V3 ổn định và có yêu cầu riêng. Eligible có thể là Shared Only bị mất đối tác trước overlap;
không thêm kiểu dịch vụ “đi một mình nhưng vẫn tìm ghép” và không ghép nối tiếp sau overlap.

Từ vị trí hiện tại thử P_B–D_A–D_B và P_B–D_B–D_A. Extra ride A tính **toàn bộ** thời gian đã ngồi cộng phần
còn lại so baseline đã giữ, không chỉ phần chèn mới. Exclusive luôn không eligible.

Kiểm chứng: cận cả hai khách, giữ hành trình A khi B hủy; tắt V4 khớp V3, bật cùng config/seed tái lập;
đo lợi ích tăng thêm/chi phí, không gộp cặp đã lên plan trước pickup vào metric nhận request mới ONBOARD.

## 8. Tích hợp và review sau mỗi bản

Mỗi bản chạy được và quan sát được qua library/CLI/service/manager; cấu hình/snapshot/metric không dồn tới V4.
API bản đồ live chưa sẵn sàng thì dùng replay file ghi nhãn rõ, không trình bày fixture như run live.
Shared schema/UI có phạm vi riêng được duyệt, không ngầm thêm vào Sprint 09.

Review cùng demand/seed: served/cancel/wait p50/p90/p95 theo hai lựa chọn; planned pair và actual overlap;
extra ride predicted/actual, deadline violations; km tổng/rỗng, GMV/payout; candidate/query, wall/event/s/RAM.
Giảm km khi phục vụ ít khách hơn không tự được coi là cải thiện. Oracle bài nhỏ trước mạng đường thật;
full suite và benchmark khi nghiệm thu, backlog bắt buộc kể cả trống.

## 9. Các điểm cần duyệt

- **V1:** cước khách 70% đã chốt. Giới hạn gần điểm cuối, dispatch shared trước Exclusive, quy tắc đối tác
  và chi tiết kế toán nằm ở D3/D4/D9/D10 của plan Chờ duyệt. Duyệt toàn bộ plan là bước trước implement.
- **V2/V3:** plan riêng sau bản trước; phương án gán xe sớm/giữ xe V3 chưa chốt.
- **Fallback:** chờ người dùng nghiên cứu thêm; không có trong schema, UI hoặc implementation hiện tại.
- **V4:** optional, chưa được yêu cầu triển khai chỉ bởi lộ trình này.

## 10. Lịch sử thay đổi

- 2026-10-09: nghiên cứu ban đầu đề xuất ba lựa chọn, V1–V3 chính và V4 ONBOARD tùy chọn.
- 2026-10-09: người dùng xác nhận Shared Only quá hạn thì khách hủy; mỗi booking một người, mỗi cặp hai booking.
- 2026-10-09: bộ thời gian demo ban đầu 60/300/180 được thay bằng 300/600/450 giây theo người dùng.
- 2026-10-09: người dùng yêu cầu bắt đầu implement từng phiên bản; chuyển V1 sang requirements/Sprint 12 và plan Chờ duyệt.
- 2026-10-09: người dùng thu hẹp còn **Shared Only / Exclusive Only**, nghiên cứu thêm fallback. Mốc 300 giây
  chỉ dành cho fallback bị loại khỏi phạm vi hiện tại; giữ 600/450 giây. Viết lại lộ trình theo chỉ đạo này;
  research gốc được giữ làm lịch sử với thông báo nội dung đã được thay thế.
- 2026-10-09: người dùng chọn Shared trả 70% cước đi riêng từng khách; cập nhật plan và yêu cầu/AC cước,
  không dùng markup tổng tuyến ×1,5, chưa coi quyết định giá là duyệt toàn bộ plan.
