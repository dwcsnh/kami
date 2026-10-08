# 07 · Policy plugin (`kami/policy/`)

## Interface (`policy/base.py`)

`Policy()` **chính là baseline**: mọi hook đều có hành vi mặc định (batch matching, cước tính theo đồng hồ,
không ghép, không điều xe). Policy mới chỉ ghi đè hook mình cần.

| Hook | Gọi khi | Trả về / mặc định |
|---|---|---|
| `on_start(sim)` / `on_end(sim)` | Trước sự kiện đầu tiên / sau sự kiện cuối | — |
| `price(sim, rider, quote) -> Quote` | Lúc báo giá, trước khi khách quyết định đặt | Giữ nguyên `quote` (đã có surge của zone nếu policy gọi `set_surge`) |
| `on_request(sim, rider)` | Khách vừa đặt (WAITING) | — |
| `on_timer(sim, rider, **payload)` | `POLICY_TIMER` tới hạn | — |
| `on_rider_cancel(sim, rider)` | Khách hủy | — |
| `on_dropoff(sim, rider, driver)` | Trả khách xong | — |
| `on_dispatch(sim, open_jobs, idle_drivers)` | Mỗi `DISPATCH_TICK` có job mở và có xe rảnh | Danh sách `(job, driver)` để gửi cuốc; mặc định `sim.default_dispatch(…, self.matching)`. Trả `None` nếu policy đã tự gọi `offer_trip`/`assign` |
| `on_driver_idle(sim, driver) -> node \| None` | Xe vừa rảnh | `None` = để tài xế tự quyết (IdleMoveModel) |
| `on_tick(sim, kind)` | `REPOSITION_TICK` / `PRICE_UPDATE` khai báo trong `tick_intervals` | — |

Thuộc tính:
- `name`: nhãn trong báo cáo;
- `tick_intervals = {"PRICE_UPDATE": 120, ...}`;
- `matching = MatchingParams(...)` (docs/engine/10);
- `batch_window`: ghi đè `SimConfig.batch_window`.

Policy **chỉ** tác động qua API của engine (bảng ở docs/engine/02). Mọi hook nhận `sim` để gọi các API đó.

## Policy dựng sẵn (`policy/library.py`)

| Lớp | Tên | Ý tưởng | Tham số chính |
|---|---|---|---|
| `Baseline` | `baseline` | Hiện trạng | `matching`, `batch_window` |
| `PoolAfterWait` | `pool_after_wait` | Design doc §7.2: chờ quá ngưỡng thì đề nghị ghép, cả hai khách đồng ý thì `merge_jobs` | `wait_threshold=300`, `surcharge=20000`, `max_o_km=1.5`, `max_d_km=2.0`, `include_matched=False`, `retry_every=None` |
| `SurgePricing` | `surge` | Surge theo zone: `1 + sensitivity·(ratio − threshold)`, với ratio = (request gần đây + job mở) / xe rảnh | `every=120`, `window_s=600`, `threshold=1.5`, `sensitivity=0.25`, `max_surge=2.0` |
| `HeatmapReposition` | `heatmap_reposition` | Theo chu kỳ, điều xe đang đứng ở zone thừa sang zone thiếu gần nhất | `every=300`, `window_s=900`, `max_moves=20`, `max_distance_m=3000` |
| `Composite(*policies)` | ghép tên | Kết hợp nhiều policy (ví dụ surge + reposition) | Xem dưới |

**Ngữ nghĩa của `Composite`:**
- `price` được nối chuỗi qua các policy thành viên;
- các hook sự kiện được gọi lần lượt cho mọi thành viên có ghi đè hook đó;
- `on_dispatch` lấy thành viên đầu tiên có ghi đè, nếu không có thì dùng matching mặc định;
- `on_driver_idle` lấy target khác `None` đầu tiên;
- `tick_intervals` được hợp lại.

> **Phạm vi hiện tại (kami 0.2):** sản phẩm chỉ matching **1 tài xế – 1 khách**, chưa có ghép chuyến
> (shared ride). `PoolAfterWait` là của kami 0.1, được giữ để tương thích (NFR-2) nhưng **tạm thời không
> dùng** trong kịch bản, policy group, UI và benchmark của 0.2 — xem [requirements §5](../requirements.md#5-ngoài-phạm-vi-hiện-tại).

**Về `PoolAfterWait`:** đúng như code mẫu trong design doc, policy chỉ hành động với khách **còn WAITING**
(chưa có xe) khi timer tới hạn. Nếu nguồn cung đủ, rất ít khách còn chờ sau 5 phút, nên tỷ lệ ghép thấp. Prototype
trong design doc cũng cho kết quả tương tự (0,28%). `include_matched=True` cho phép ghép với khách đã có xe đang
tới (chèn vào plan của tài xế). Đây là một biến thể policy khác và nên được đánh giá như một arm riêng.

## Viết policy mới (ví dụ: hold control)

```python
from kami.policy import Policy

class HoldForBetterPair(Policy):
    """Không ghép đơn mới vào xe ở xa ngay; chờ tối đa hold_s để có xe gần hơn."""
    name = "hold_control"

    def __init__(self, hold_s=30, near_eta=240, **kw):
        super().__init__(**kw)
        self.hold_s, self.near_eta = hold_s, near_eta

    def on_dispatch(self, sim, open_jobs, idle_drivers):
        pairs = sim.default_dispatch(open_jobs, idle_drivers, self.matching)
        keep = []
        for job, drv in pairs:
            eta, _ = sim.traffic.estimate(sim.current_loc(drv), sim.job_first_pickup(job), sim.t)
            if eta <= self.near_eta or sim.t - job.created_t >= self.hold_s:
                keep.append((job, drv))
        return keep
```

Chạy như mọi arm khác:

```python
Experiment(..., arms={"baseline": Baseline, "hold": lambda: HoldForBetterPair(hold_s=30)})
```

**Checklist cho policy mới:**
- Không sửa trạng thái agent trực tiếp; chỉ gọi API.
- Không dùng `random`. Nếu policy có yếu tố ngẫu nhiên, dùng `sim.crn.u("<tên>", id_ổn_định)` (docs/engine/05).
- Policy phải tạo được bằng một factory không đối số, tức `lambda: MyPolicy(...)`, vì mỗi lần chạy cần một instance
  mới (policy có thể giữ trạng thái riêng).
- Đăng ký vào `POLICIES` trong `policy/library.py` nếu muốn dùng qua CLI.

## Danh mục policy của design doc §7.3 và cách làm trong kami

| Nhóm | Có sẵn | Cách làm phần chưa có |
|---|---|---|
| Matching / dispatch | Độ dài batch (`batch_window`), bán kính đón (`max_pickup_eta`), ưu tiên khách chờ lâu (`wait_weight`), Hungarian/greedy | Hold control: ví dụ ở trên. Gửi đơn cho nhiều tài xế: override `on_dispatch` và gọi `offer_trip` nhiều lần |
| Giá cho khách | `SurgePricing`, `price()` cho upfront pricing / trợ giá | Wait & Save: `price()` giảm giá kèm `on_request` hẹn timer |
| Thu nhập tài xế | `FareModel.take_rate`, `surcharge_to_driver` | Quest/Boost: `on_dropoff` cộng thưởng, cần thêm sổ chi phí khuyến khích (docs/engine/17) |
| Điều phối cung | `HeatmapReposition`, `on_driver_idle` | Dynamic fleet sizing: dùng `ScheduledShift` hoặc thêm ca vào kịch bản |
| Ghép chuyến *(ngoài phạm vi 0.2)* | `PoolAfterWait` (ngưỡng chờ, phụ phí, bán kính), `PoolingParams` (độ vòng) — giữ cho tương thích | — |
| Hủy & độ tin cậy | Hook `on_rider_cancel` | Phí hủy: thêm biến giá vào model hủy |
| Phương pháp thí nghiệm | — | Switchback: policy đổi hành vi theo khung `sim.t`, so với chia theo user (docs/engine/17) |
