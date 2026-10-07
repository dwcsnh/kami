# Lộ trình sprint kami 0.2

Các sprint hiện thực [requirements.md](../requirements.md). File sprint chỉ mô tả **cần làm gì và thế nào là
xong** (phạm vi, hạng mục, acceptance criteria). **Cách làm** nằm trong implementation plan tương ứng ở
[`../implementation-plan/`](../implementation-plan/README.md). Quy trình đầy đủ ở [AGENTS.md](../../AGENTS.md).

## Danh sách sprint

| Sprint | Tên | Yêu cầu chính | Phụ thuộc | Trạng thái |
|---|---|---|---|---|
| [01](sprint-01-foundation.md) | Nền tảng cấu hình, lưu trữ & benchmark | NFR-1, NFR-4, NFR-5, PERF-3, nền cho FLEET-3/POL-3/RUN-4 | — | Chưa bắt đầu |
| [02](sprint-02-hanoi-network-traffic.md) | Bản đồ Hà Nội & giao thông giờ cao điểm | MAP-1…MAP-5 | 01 | Chưa bắt đầu |
| [03](sprint-03-scale-performance.md) | Hiệu năng quy mô GreenSM | PERF-1, PERF-2, PERF-3 | 01, 02 | Chưa bắt đầu |
| [04](sprint-04-fleet-ev-charging.md) | Loại xe, fleet & sạc xe điện | EV-1…EV-5, FLEET-1, FLEET-2, FLEET-4 | 01, 02 | Chưa bắt đầu |
| [05](sprint-05-dynamic-pricing.md) | Dynamic pricing & phản ứng của khách | PRICE-1…PRICE-4 | 04 | Chưa bắt đầu |
| [06](sprint-06-policy-v2-groups.md) | Policy plugin v2 & policy group | POL-1, POL-2, POL-3, POL-5, NFR-3 | 01, 04, 05 | Chưa bắt đầu |
| [07](sprint-07-backend-run-manager.md) | Backend service & quản lý lần chạy | RUN-1…RUN-4, FLEET-3 (API), POL-3 (API) | 01, 06 | Chưa bắt đầu |
| [08](sprint-08-ui-simulation-manager.md) | Giao diện Simulation manager | UI-2, UI-3, UI-4, UI-5, FLEET-3, POL-4, POL-5 | 07 | Chưa bắt đầu |
| [09](sprint-09-visualizer-live-metrics.md) | Simulation visualizer & live metric | UI-1, MAP-2, PERF-4 | 02, 07, 08 | Chưa bắt đầu |
| [10](sprint-10-policy-agent.md) | Policy agent | POL-6, NFR-3 | 06, 08 | Chưa bắt đầu |
| [11](sprint-11-integration-acceptance.md) | Tích hợp & nghiệm thu end-to-end | Toàn bộ | 01–10 | Chưa bắt đầu |

```
01 ─┬─▶ 02 ─┬─▶ 03 ───────────────────────────────┐
    │       └─▶ 04 ─▶ 05 ─▶ 06 ─▶ 07 ─▶ 08 ─┬─▶ 10 ├─▶ 11
    │                              │        └─▶ 09 ┘
    └──────────────────────────────┘ (schema/DB dùng xuyên suốt)
```

Thứ tự có thể đổi khi người dùng yêu cầu, nhưng phải giữ đúng phụ thuộc. Ví dụ 03 có thể làm song song với 04 vì
cả hai chỉ cần 02.

## Ma trận yêu cầu → sprint

| Yêu cầu | Sprint |
|---|---|
| PERF-1, PERF-2 | 03 (đạt), 11 (nghiệm thu lại với đầy đủ tính năng) |
| PERF-3 | 01 (harness), 03 (bộ benchmark quy mô), mọi sprint sau (không thoái lui) |
| PERF-4 | 09 |
| MAP-1, MAP-3, MAP-4, MAP-5 | 02 |
| MAP-2 | 02 (lộ trình + quỹ đạo), 09 (hiển thị) |
| EV-1…EV-5 | 04 (EV-5: hook ở 04, đóng gói thành policy plugin ở 06) |
| FLEET-1, FLEET-2, FLEET-4 | 04 |
| FLEET-3 | 01 (schema), 07 (API), 08 (UI) |
| PRICE-1…PRICE-4 | 05 |
| POL-1, POL-2, POL-3 | 06 (POL-3 schema từ 01, API ở 07) |
| POL-4, POL-5 | 08 (POL-5 cơ chế ở 06) |
| POL-6 | 10 |
| RUN-1…RUN-4 | 07 (RUN-4 schema từ 01), UI ở 08 |
| UI-1 | 09 |
| UI-2…UI-5 | 08 |
| NFR-1…NFR-5 | 01 (nền), kiểm tra lại ở mọi sprint, nghiệm thu ở 11 |

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
