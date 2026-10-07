# 14 · Training pipeline & model registry

Design doc §2 nguyên tắc 7: **behavior model được train ở pipeline riêng; simulator chỉ nạp checkpoint.** Uber làm
vậy để giảm RAM/CPU và dễ bảo trì.

```
dữ liệu lịch sử ──▶ kami.training (hoặc pipeline riêng của hãng) ──▶ ModelRegistry (JSON) ──▶ BehaviorSuite ──▶ Simulation
```

## Model registry (`kami/behavior/registry.py`)

Checkpoint lưu tại `<root>/<slot>/<version>.json`:

```json
{
  "slot": "pool_accept",
  "version": "v2",
  "class": "kami.behavior.models.LogitPoolAccept",
  "params": {"asc": -0.8, "b_wait": 0.12, "b_price": 0.6, "b_detour": 0.1},
  "meta": {"trained_on": "SP survey 2026-09", "n": 1240}
}
```

```python
reg = ModelRegistry("models/")
reg.save("pool_accept", LogitPoolAccept(asc=-0.8), "v2", meta={...})
reg.versions("pool_accept")               # ["v1", "v2"] (sắp theo tên)
reg.load("pool_accept")                   # bản mới nhất; hoặc reg.load("pool_accept", "v1")
suite = reg.suite({"pool_accept": "v2", "cancel_wait": "latest"})   # slot không liệt kê thì dùng mặc định
```

- Các slot hợp lệ: `booking`, `cancel_wait`, `cancel_matched`, `pool_accept`, `driver_accept`, `idle_move`,
  `driver_shift`. Slot `pool_accept` (ví dụ ở trên) thuộc pooling — ngoài phạm vi 0.2, giữ cho tương thích.
- `class` có thể là bất kỳ lớp nào import được, kể cả model của hãng, miễn là khởi tạo được bằng
  `cls(**params)` và theo đúng protocol.
- CLI: `--registry <thư_mục>` nạp bản mới nhất của mọi slot có trong thư mục.

## Hàm fit có sẵn (`kami/training/fit.py`)

Viết bằng thư viện chuẩn, đủ cho MVP. Pipeline thật có thể thay bằng thư viện chuyên dụng, miễn là ghi ra
checkpoint đúng định dạng.

| Hàm | Đầu vào | Đầu ra | Gắn vào model |
|---|---|---|---|
| `fit_weibull_cancel(records)` | `(phút_chờ, đã_hủy?)`, có right-censoring (khách được ghép trước khi hủy) | `{"shape", "scale_min", "loglik"}` (MLE: λ có dạng đóng theo k, k quét lưới) | `WeibullCancel(shape=…)`; `scale_min` dùng làm trung vị `patience_min` trong `ScenarioBuilder.rider_attrs` |
| `fit_logit(X, y, names)` | Ma trận đặc trưng, nhãn 0/1 | `{"asc", name1, …}` (Newton–Raphson + ridge nhỏ) | Đổi dấu theo model, ví dụ `LogitPoolAccept(b_wait=b1, b_price=-b2, b_detour=-b3)` |
| `fit_transition_matrix(moves)` | `(giờ, zone_đi, zone_đến)` của các đoạn GPS khi xe rảnh | `{giờ: {zone: {"stay" \| zone_đến: xác_suất}}}` | `TransitionMatrixIdleMove(matrix)` |

Có test kiểm tra các hàm fit khôi phục đúng tham số trên dữ liệu sinh ra: Weibull k=1,4, λ=8; logit 3 hệ số.

## Quy trình đề xuất (design doc §13 giai đoạn 2)

1. **Hủy chuyến:** từ log đặt–hủy, mỗi đơn tạo bản ghi `(thời_gian_chờ_tới_khi_hủy_hoặc_có_xe, đã_hủy)`, rồi
   chạy `fit_weibull_cancel`. Fit riêng theo giờ hoặc thời tiết nếu đủ dữ liệu.
2. **Tài xế nhận cuốc:** từ log gửi–nhận cuốc, `X = [eta_đón_phút, thu_nhập/100k]`, rồi chạy `fit_logit`.
3. **Xe rảnh đi đâu:** từ GPS khi rảnh, gán zone đầu và cuối của mỗi đoạn, rồi chạy `fit_transition_matrix`.
4. **Nhận ghép có phụ phí:** chưa có dữ liệu lịch sử (design doc §14.1). Cần khảo sát stated-preference hoặc một
   A/B nhỏ; trong lúc chờ, dùng `ProbabilityScaler` để làm sensitivity.
5. Lưu từng model bằng `reg.save(...)` kèm `meta` (nguồn, khoảng thời gian, số mẫu, độ khớp).
6. **Kiểm chứng:** baseline dùng suite mới phải tái tạo được phân bố lịch sử (docs/engine/09, "Hiệu chỉnh baseline").

`examples/04_train_and_register.py` minh hoạ toàn bộ vòng: dùng log của một lần chạy làm "dữ liệu lịch sử", fit,
lưu vào registry, rồi nạp lại.
