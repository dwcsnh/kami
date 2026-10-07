# Sprint 01 — Nền tảng cấu hình, lưu trữ & benchmark

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | NFR-1, NFR-4, NFR-5, PERF-3; nền cho FLEET-3, POL-3, RUN-4 |
| Phụ thuộc | — |
| Backlog đầu vào | Không có (sprint đầu tiên) |
| Implementation plan | [sprint-01-plan.md](../implementation-plan/sprint-01-plan.md) (chưa có) |

## Mục tiêu

Mọi thứ người dùng sẽ cấu hình qua UI (kịch bản, fleet, loại xe, policy, lần chạy) phải biểu diễn được dưới dạng
**cấu hình khai báo** (dữ liệu, không phải code Python), lưu được vào DB, và dựng lại được thành object của engine.
Đồng thời dựng **bộ đo hiệu năng** để mọi sprint sau có mốc so sánh.

## Phạm vi

- Schema cấu hình khai báo cho: kịch bản, lần chạy, fleet, loại xe, trạm sạc, policy, policy group. Ở sprint này
  các schema của fleet/loại xe/trạm sạc/policy chỉ cần đủ trường tối thiểu; Sprint 04 và 06 sẽ mở rộng.
- Dựng engine từ cấu hình: từ một file/bản ghi cấu hình chạy được một lần mô phỏng mà không cần viết Python.
- Lớp lưu trữ (DB) cho các thực thể trên, kèm migration.
- Lưu kết quả một lần chạy: snapshot cấu hình, metric tổng hợp, metric theo thời gian, tham chiếu tới event log.
- Benchmark harness.

## Ngoài phạm vi

- API HTTP, giao diện (Sprint 07, 08).
- Nội dung chi tiết của loại xe, sạc, pricing, policy group (Sprint 04–06).

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S01-1 | Định nghĩa schema cấu hình khai báo có số phiên bản (`schema_version`) cho: `ScenarioSpec` (mạng, zone, khung giờ, demand, thời tiết, sự cố, seed), `RunSpec` (kịch bản + fleet + policy group + seed), `FleetSpec`, `VehicleTypeSpec`, `ChargingStationSpec`, `PolicySpec` (tên plugin + tham số), `PolicyGroupSpec`. Có kiểm tra hợp lệ với thông báo lỗi chỉ rõ trường sai |
| S01-2 | Bộ dựng từ cấu hình: `RunSpec` → `Scenario`, `Simulation`, `Policy`, `BehaviorSuite`. Các preset và policy dựng sẵn của 0.1 đều biểu diễn được bằng cấu hình |
| S01-3 | CLI chạy từ file cấu hình (ví dụ `python -m kami run --spec run.json`), giữ nguyên các lệnh CLI cũ |
| S01-4 | Lớp lưu trữ: mô hình dữ liệu cho `vehicle_type`, `fleet` (+ thành phần xe), `charging_station`, `policy` (+ phiên bản), `policy_group` (+ thành viên), `scenario`, `run`, `run_metric_summary`, `run_metric_timeseries`, `run_artifact`. Có migration tạo DB từ rỗng |
| S01-5 | Lớp repository tách biệt: lõi engine **không** import thư viện DB (NFR-5); có thể chạy engine thuần thư viện như 0.1 |
| S01-6 | Bộ thu metric theo thời gian: chụp nhanh metric chính theo chu kỳ thời gian mô phỏng (cấu hình được, ví dụ 5 phút) để phục vụ live metric (Sprint 09) và trang metric (Sprint 08) |
| S01-7 | Lưu một lần chạy: snapshot đầy đủ cấu hình đã dùng (NFR-4), metric tổng hợp, chuỗi thời gian metric, đường dẫn event log, phiên bản kami |
| S01-8 | Benchmark harness: một lệnh chạy bộ kịch bản benchmark cố định (tối thiểu: lưới synthetic; mạng FleetPy `example_network`), ghi wall-clock, số sự kiện/giây, RAM đỉnh ra file JSON |
| S01-9 | Tài liệu: thêm `docs/engine/18-config-persistence.md` mô tả schema, bộ dựng, lưu trữ, benchmark |

## Acceptance criteria

- [ ] AC01-1 Một `RunSpec` JSON chạy qua CLI cho **metric giống hệt** lần chạy tương đương viết bằng API Python 0.1
      (cùng kịch bản, policy, seed) — NFR-1.
- [ ] AC01-2 Mọi preset (`python -m kami presets`) và mọi policy trong `POLICIES` có cấu hình tương ứng và chạy được.
- [ ] AC01-3 Cấu hình sai (thiếu trường, sai kiểu, tham số policy không tồn tại) bị từ chối với thông báo chỉ rõ trường.
- [ ] AC01-4 Round-trip: lưu spec vào DB rồi đọc lại cho object bằng nhau với mọi loại thực thể.
- [ ] AC01-5 Migration tạo được DB từ rỗng; chạy lại migration trên DB đã có không lỗi.
- [ ] AC01-6 Sau một lần chạy, DB có bản ghi `run` với snapshot cấu hình, metric tổng hợp, chuỗi thời gian metric và
      đường dẫn event log đọc được.
- [ ] AC01-7 `import kami` và chạy `examples/01_quickstart.py` không cần cài thư viện DB.
- [ ] AC01-8 Lệnh benchmark chạy xong và xuất JSON; kết quả lần đầu được ghi vào `docs/backlog/sprint-01-backlog.md`
      làm mốc.
- [ ] AC01-9 Toàn bộ test cũ pass; có test mới cho schema, bộ dựng, repository.

## Rủi ro & câu hỏi mở

- Chọn DB (SQLite cho dev, PostgreSQL cho triển khai?) và thư viện ORM/migration: quyết định trong implementation
  plan (requirements Q5).
- Event log của 1 ngày quy mô GreenSM có thể rất lớn (hàng chục triệu dòng): cần chốt định dạng lưu (Parquet/file)
  thay vì nhét vào DB.
