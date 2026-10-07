# 06 · Behavior models (`kami/behavior/`)

## Nguyên tắc

- Mỗi điểm quyết định có **interface cố định** (`protocols.py`). Thay model không cần sửa engine (design doc §6).
- Model là **hàm thuần**: nhận (agent, tình huống, `Context`) và trả **xác suất / hazard / phân phối**. Engine
  biến kết quả thành quyết định bằng số CRN riêng của agent (docs/engine/05).
- Tham số nằm trong dataclass `params`, để lưu và nạp được qua `ModelRegistry` (docs/engine/14).
- Theo design doc §6.3: dùng model logit/ngưỡng dễ giải thích trước, ML sau. **Giá trị mặc định là giả định**, chỉ
  đủ để baseline trông hợp lý trên dữ liệu synthetic.

## `Context`

`Context(t, hour, weather, zone, incident_cancel_multiplier, extra)` do `sim.context(node)` tạo ra. Trong đó
`incident_cancel_multiplier` lấy từ sự cố đang phủ zone của node (mặc định 1,0).

## Bảy slot của `BehaviorSuite`

| Slot | Protocol | Engine gọi khi | Model mặc định |
|---|---|---|---|
| `booking` | `BookingModel.p_book(rider, quote, ctx)` | Khách thấy báo giá | `LogitBooking` |
| `cancel_wait` | `RiderCancelModel.hazard(rider, waited_min, eta_shown, ctx)` (/phút) | Pha chờ chưa có xe | `WeibullCancel` |
| `cancel_matched` | như trên | Pha đã có xe | `OverrunCancel` |
| `pool_accept` | `PoolAcceptModel.p_accept(rider, offer, ctx)` | `sim.behavior.pool_accept` | `LogitPoolAccept` |
| `driver_accept` | `DriverAcceptModel.p_accept(driver, TripOffer, ctx)` | `sim.offer_trip` | `LogitDriverAccept` |
| `idle_move` | `IdleMoveModel.distribution(driver, ctx, zones)` → `[(zone hoặc None, trọng số)]` | Xe rảnh `idle_decision_s` giây | `HomeBiasIdleMove` |
| `driver_shift` | `DriverShiftModel.p_stop(driver, ctx)` | Mỗi lần xe trở lại rảnh | `ScheduledShift` (luôn 0) |

> **Phạm vi hiện tại (kami 0.2):** sản phẩm chỉ matching **1 tài xế – 1 khách**, chưa có ghép chuyến
> (shared ride). Slot `pool_accept` (`LogitPoolAccept`) và thuộc tính `pool_willingness` là của kami 0.1, được giữ để tương thích (NFR-2) nhưng **tạm thời không
> dùng** trong kịch bản, policy group, UI và benchmark của 0.2 — xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại).

```python
suite = BehaviorSuite()                                  # mặc định
suite = BehaviorSuite.employed_drivers()                 # tài xế là nhân viên: AlwaysAccept
suite = BehaviorSuite().replace(pool_accept=MyModel())   # thay một slot
```

## Công thức model mặc định

`σ(x) = 1 / (1 + e^-x)`. Tiền tính bằng VND, thời gian bằng phút.

**`LogitBooking`**: `p = σ(asc − b_surge·sens·(surge−1) − b_eta·eta − b_surcharge·sens·surcharge/10k)`.
Mặc định `asc=3`, `b_surge=2`, `b_eta=0,15`, `b_surcharge=0,3`. Với ETA 5 phút và không surge, p ≈ 0,90.

**`WeibullCancel`** (pha chờ):
`h(w) = (k/λ)(w/λ)^(k−1) · e^{b_eta·(eta − eta_ref)} · m_weather · m_incident`,
với `λ = rider.attrs["patience_min"]`. Mặc định `k=1,2`, `b_eta=0,05`, `eta_ref=5`, mưa ×1,15, mưa to ×1,3.
Chọn `k<1` nếu muốn mô phỏng hiệu ứng "đã chờ lâu thì chờ tiếp" (sunk waiting time).

**`OverrunCancel`** (pha đã có xe):
`h = base · e^{b_overrun·max(0, −eta_còn_lại)} · m_weather · m_incident`.
Hazard thấp khi tài xế đúng hẹn và tăng nhanh khi trễ so với lời hứa. Mặc định `base=0,008/phút`,
`b_overrun=0,25`.

**`LogitPoolAccept`**:
`p = σ(asc + b_wait·đã_chờ − b_price·sens·surcharge/10k − b_detour·độ_vòng + pool_willingness)`.
Mặc định `asc=−1`, `b_wait=0,15`, `b_price=0,5`, `b_detour=0,1`. Sau 5 phút chờ, vòng 4 phút:
+20k → p≈0,16; 0đ → 0,34; −20k → 0,59.
**Chưa có dữ liệu cho trường hợp phụ phí** (design doc §14.1), nên bắt buộc chạy sensitivity (docs/engine/12).

**`LogitDriverAccept`**:
`p = σ(asc − b_pickup·eta_đón + b_fare·thu_nhập/100k + accept_bias)`.
Mặc định `asc=3`, `b_pickup=0,25`, `b_fare=1`. Đón 5 phút, thu nhập 60k → p≈0,91.

**`HomeBiasIdleMove`**: đứng yên với xác suất `p_stay=0,6`; phần còn lại chia cho việc về `home_zone`
(trọng số `w_home=0,25`) và các zone lân cận chia đều.

**`TransitionMatrixIdleMove(matrix)`**: ma trận chuyển giữa các zone theo giờ (cách Uber làm), học từ GPS bằng
`fit_transition_matrix`. Ô không có dữ liệu thì dùng `fallback`.

**`IncomeTargetShift`**: sau khi đạt mục tiêu thu nhập (`attrs["income_target"]`, mặc định 800k), mỗi lần rảnh có
xác suất 0,3 nghỉ ca. Đây là mô hình cung lao động đơn giản.

## Wrapper cho sensitivity

```python
ProbabilityScaler(LogitPoolAccept(), 1.5)   # khách nhận ghép nhiều hơn 50% (cắt ở 1)
HazardScaler(WeibullCancel(), 1.3)          # khách thiếu kiên nhẫn hơn 30%
```

## Viết model mới

```python
from dataclasses import dataclass
from kami.behavior.models import Model, sigmoid

@dataclass
class MyPoolParams:
    asc: float = -0.5
    b_price: float = 0.8

class MyPoolAccept(Model):
    def __init__(self, params=None, **kw):
        self.params = params or MyPoolParams(**kw)

    def p_accept(self, rider, offer, ctx):
        return sigmoid(self.params.asc - self.params.b_price * offer.surcharge / 10_000)

suite = BehaviorSuite(pool_accept=MyPoolAccept(asc=-0.3))
```

Điều kiện: không tự rút số ngẫu nhiên, không đổi trạng thái agent, có `params` (dataclass) hoặc `to_dict()` nếu
muốn lưu vào registry. Một model ML (ví dụ GBM) chỉ cần bọc lại để trả xác suất theo đúng interface.
