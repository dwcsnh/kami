# Sprint 13 — Shared ride V2: tìm đối tác dọc hành trình

| | |
|---|---|
| Trạng thái | Chưa bắt đầu — đề xuất sau V1, chưa duyệt phạm vi/plan |
| Yêu cầu | SR-8 (V2), SR-1…SR-7, SR-9, NFR-1, NFR-2, NFR-5, PERF-3 |
| Phụ thuộc | 12 |
| Backlog đầu vào | [sprint-12-backlog.md](../backlog/sprint-12-backlog.md) — B12-1; theo dõi B12-2/B12-5 |
| Implementation plan | Chưa lập; phải được người dùng duyệt trước code |

## Mục tiêu

Cho phép điểm trả của B nằm giữa hành trình A, kể cả khi xa điểm trả A; giữ hai
booking WAITING, hai lựa chọn dịch vụ và các đồng hồ/giá đã nghiệm thu ở V1.

## Phạm vi đề xuất

- Tìm ứng viên quanh tuyến theo hai hướng A/B, thay giới hạn gần hai điểm cuối V1.
- Kiểm tuyến từ xe thật, hạn đón và extra ride riêng từng khách; giải thích các
  giới hạn của heuristic và đo chất lượng so với bài nhỏ không cắt ứng viên.
- Metric, replay và form thể hiện tham số tìm ứng viên V2 đã được chốt.
- Đối chứng V1/V2 cùng demand, preference, seed, served và các giới hạn dịch vụ.

## Ngoài phạm vi

Ghép MATCHED hoặc nhận request mới khi ONBOARD (V3/V4); fallback; hơn hai
booking; EV/sạc; policy mới; nghiệm thu quy mô GreenSM thay Sprint 04.

## Hạng mục công việc

| Mã | Việc cần làm |
|---|---|
| S13-1 | Chốt cấu hình tìm dọc tuyến và snapshot version V2 tương thích V1 |
| S13-2 | Tìm ứng viên theo hai hướng; giữ feasibility và invariants V1 |
| S13-3 | Quan sát V2 qua metric, manager và replay thật |
| S13-4 | Hồi quy V1/0.1, đối chứng chất lượng/hiệu năng và backlog |

## Acceptance criteria đề xuất, chờ duyệt

- [ ] **AC13-1:** trường hợp D_B giữa tuyến A nhưng xa D_A được tìm nếu khả thi; hai hướng đều được xét.
- [ ] **AC13-2:** không vượt hạn đón/extra ride riêng A/B tại lúc gán; không gán trùng hoặc nhận đối tác mới cho khách đã MATCHED/ONBOARD.
- [ ] **AC13-3:** deadline/hazard/giá Shared 70% và cleanup V1 giữ nguyên; Shared Only/Exclusive Only không đổi semantics.
- [ ] **AC13-4:** snapshot version V1 vẫn chạy; form/metric/replay V2 lấy dữ liệu engine và worker thật.
- [ ] **AC13-5:** có oracle bài nhỏ, đối chứng V1/V2 cùng demand/seed, báo served/cancel/km/candidate/query/wall/RAM; full Python/web checks và backlog.

## Rủi ro & câu hỏi mở

- Khoảng cách tới tuyến, vị trí tuyến dùng để lọc và cutoff cần chốt trong plan;
  chưa coi radius V1 tự động đủ làm cấu hình V2.
- Greedy/cắt ứng viên có thể bỏ cặp tốt; cần công bố tập tìm kiếm và đo sai lệch.
- Cần người dùng duyệt phạm vi/AC đề xuất và implementation plan V2. Sprint này
  được lập theo S12-8; chưa có code hoặc quyết định kỹ thuật V2 được duyệt.
