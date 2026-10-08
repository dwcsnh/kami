# Lộ trình sprint kami 0.2

Các sprint hiện thực [requirements.md](../requirements.md). File sprint chỉ mô tả **cần làm gì và thế nào là
xong** (phạm vi, hạng mục, acceptance criteria). **Cách làm** nằm trong implementation plan tương ứng ở
[`../implementation-plan/`](../implementation-plan/README.md). Quy trình đầy đủ ở [AGENTS.md](../../AGENTS.md).

## Danh sách sprint

| Sprint | Tên | Yêu cầu chính | Phụ thuộc | Trạng thái |
|---|---|---|---|---|
| [01](sprint-01-foundation.md) | Nền tảng cấu hình, lưu trữ & benchmark | NFR-1, NFR-4, NFR-5, PERF-3, nền cho FLEET-3/RUN-4 | — | Xong |
| [02](sprint-02-hanoi-network-traffic.md) | Bản đồ Hà Nội & giao thông giờ cao điểm | MAP-1…MAP-5 | 01 | Xong |
| [03](sprint-03-map-visualizer.md) | Bản đồ vận hành (fleet operation visualizer) trên web | UI-1 (phát lại), MAP-2 (hiển thị) | 02 | Xong |
| [04](sprint-04-scale-performance.md) | Hiệu năng quy mô GreenSM | PERF-1, PERF-2, PERF-3, UI-1 (quy mô thành phố) | 01, 02, 03 | Đang lập plan |
| [05](sprint-05-fleet-ev-charging.md) | Loại xe, fleet & sạc xe điện | EV-1…EV-4, FLEET-1, FLEET-2, FLEET-4 | 01, 02, 03 | Chưa bắt đầu |
| [06](sprint-06-dynamic-pricing.md) | Dynamic pricing & phản ứng của khách | PRICE-1…PRICE-4 | 05 | Chưa bắt đầu |
| [08](sprint-08-backend-run-manager.md) | Backend service & quản lý lần chạy | RUN-1…RUN-4, FLEET-3 (API) | 01, 05, 06 | Chưa bắt đầu |
| [09](sprint-09-ui-simulation-manager.md) | Giao diện Simulation manager & visualizer live | UI-1 (live), UI-2, UI-3, UI-5, FLEET-3, PERF-4 | 03, 08 | Chưa bắt đầu |
| [11](sprint-11-integration-acceptance.md) | Tích hợp & nghiệm thu end-to-end | Toàn bộ | 01–09 | Chưa bắt đầu |

```
01 ─▶ 02 ─▶ 03 ─┬─▶ 04 ───────────────────────┐
                └─▶ 05 ─▶ 06 ─▶ 08 ─▶ 09 ─────┴─▶ 11
01 (schema/DB) dùng xuyên suốt; 03 (visualizer) được 04, 05, 06 bổ sung lớp hiển thị và 09 chuyển sang live
```

Sprint 07 (Policy plugin v2 & policy group) và Sprint 10 (Policy agent) **đã bị xoá** vì policy nằm ngoài phạm vi
hiện tại ([requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại)). Số thứ tự các sprint còn lại giữ nguyên để
không làm lệch mã `SNN-k`, `ACNN-k`, `BNN-k` đã tham chiếu.

Visualizer (03) được làm sớm, ngay sau khi có bản đồ Hà Nội, để mọi sprint tính năng sau đó **nhìn thấy được kết quả
trên bản đồ**: sprint nào thêm trạng thái/dữ liệu mới thì bổ sung lớp hiển thị tương ứng (04: quy mô 8k xe; 05: sạc,
SOC, trạm sạc; 06: surge/giá; 09: live, lọc theo fleet, khách chờ). Ở 03 visualizer chỉ phát lại từ file fixture;
từ 09 đọc stream/API của backend (08).

Thứ tự có thể đổi khi người dùng yêu cầu, nhưng phải giữ đúng phụ thuộc. Ví dụ 04 có thể làm song song với 05 vì
cả hai chỉ cần 01–03.

## Ma trận yêu cầu → sprint

| Yêu cầu | Sprint |
|---|---|
| PERF-1, PERF-2 | 04 (đạt), 11 (nghiệm thu lại với đầy đủ tính năng) |
| PERF-3 | 01 (harness), 04 (bộ benchmark quy mô), mọi sprint sau (không thoái lui) |
| PERF-4 | 09 (đo khi có live), 11 (nghiệm thu lại) |
| MAP-1, MAP-3, MAP-4, MAP-5 | 02 |
| MAP-2 | 02 (lộ trình + quỹ đạo), 03 (hiển thị) |
| EV-1…EV-4 | 05 |
| FLEET-1, FLEET-2, FLEET-4 | 05 |
| FLEET-3 | 01 (schema), 08 (API), 09 (UI) |
| PRICE-1…PRICE-4 | 06 |
| RUN-1…RUN-4 | 08 (RUN-4 schema từ 01), UI ở 09 |
| UI-1 | 03 (bản đồ + metric, phát lại fixture), 04 (quy mô thành phố), 05–06 (lớp sạc, surge), 09 (live, tích hợp) |
| UI-2, UI-3, UI-5 | 09 |
| NFR-1, NFR-2, NFR-4, NFR-5 | 01 (nền), kiểm tra lại ở mọi sprint, nghiệm thu ở 11 |

## Định nghĩa "xong" chung (áp cho mọi sprint)

Một sprint chỉ được coi là xong khi, ngoài acceptance criteria riêng:

1. Toàn bộ test cũ và mới pass: `python -m unittest discover -s tests -t .`
2. Benchmark của PERF-3 (từ Sprint 01) không thoái lui quá **10%** so với kết quả ghi ở backlog sprint trước, trừ
   khi sprint chủ động thêm tính toán và đã ghi lý do.
3. Tài liệu module trong [`docs/engine/`](../engine/README.md) được cập nhật cho phần đã đổi (hoặc thêm file mới).
4. File backlog [`docs/backlog/sprint-NN-backlog.md`](../backlog/README.md) đã được viết (kể cả khi trống).
5. Trạng thái trong bảng trên và trong file sprint được cập nhật.

## Mẫu file sprint

```markdown
# Sprint NN — <Tên>

| | |
|---|---|
| Trạng thái | Chưa bắt đầu / Đang lập plan / Đã duyệt plan / Đang làm / Xong |
| Yêu cầu | <mã trong requirements.md> |
| Phụ thuộc | <sprint> |
| Backlog đầu vào | [sprint-(NN-1)-backlog.md](../backlog/sprint-(NN-1)-backlog.md) |
| Implementation plan | [sprint-NN-plan.md](../implementation-plan/sprint-NN-plan.md) |

## Mục tiêu
## Phạm vi
## Ngoài phạm vi
## Hạng mục công việc      (mã SNN-k, mô tả việc cần làm, không mô tả cách làm)
## Acceptance criteria     (checklist kiểm chứng được, mã ACNN-k)
## Rủi ro & câu hỏi mở
```
