# Hệ thống mô phỏng & đánh giá policy cho hãng gọi xe

*Bản tổng hợp ý tưởng thiết kế — agent-based, discrete-event, có thể nhúng policy và gắn mô hình hành vi tại các điểm ra quyết định.*

---

## 1. Mục tiêu

Xây dựng một simulator cho phép hãng gọi xe **đưa một policy mới vào môi trường mô phỏng**, chạy trên dữ liệu lịch sử hoặc synthetic, và **đo tác động nhân quả** của policy đó lên các chỉ số vận hành — trước khi thử trên khách hàng thật.

```
Historical / Synthetic Data → Simulator → Apply Policy → Simulate Counterfactual → Evaluate → Causal Effect
```

**Ví dụ policy cần đánh giá:**

> "Khi khách đã chờ 5 phút, hệ thống đề nghị ghép chuyến với một hành khách khác và cộng thêm 20.000đ."

Policy này khó thử trực tiếp trên toàn hệ thống vì ảnh hưởng đến trải nghiệm khách, doanh thu và tài xế.

**Đầu ra mong muốn** không phải "hôm đó tỷ lệ ghép tăng 10%", mà là:

> "Nếu áp dụng policy này **trong cùng điều kiện** nhu cầu, thời tiết, giao thông và nguồn cung, tỷ lệ ghép dự kiến tăng X% **do chính policy**, đồng thời thời gian chờ tăng Y phút và doanh thu thay đổi Z% (khoảng tin cậy 95%: …)."

---

## 2. Nguyên tắc thiết kế

Rút ra từ cách Uber, Lyft, DiDi, Grab và các simulator mã nguồn mở (MaaSSim, FleetPy, RidePy) làm:

| # | Nguyên tắc | Ý nghĩa |
|---|---|---|
| 1 | **Agent-based, discrete-event** | Mỗi khách và mỗi tài xế là một agent riêng, có trạng thái và ra quyết định riêng; đồng hồ mô phỏng nhảy từ sự kiện này sang sự kiện kế tiếp. |
| 2 | **Policy là plugin** | Policy không được viết cứng vào engine. Nó đăng ký vào các *hook* sự kiện; baseline và treatment chạy trên **cùng một engine**. |
| 3 | **Hành vi = model gắn vào điểm quyết định** | Mỗi lần agent phải quyết định (hủy? nhận ghép? đi đâu khi rảnh?), engine gọi một behavior model có thể thay thế. |
| 4 | **Luật hành vi chung, rút ngẫu nhiên riêng** | Không cố tái tạo "tài xế số 1234 thật". Mỗi agent có thuộc tính riêng rút từ phân phối, dùng chung mô hình học từ dữ liệu tổng hợp. Kiểm chứng bằng **phân bố**, không bằng từng cá nhân. |
| 5 | **Replay phần ngoại sinh, mô hình hóa phần sau can thiệp** | Nhu cầu, thời tiết, sự cố lấy từ lịch sử/kịch bản. Mọi thứ *sau quyết định của policy* (tài xế đi đâu, khách có hủy không) phải do mô hình sinh ra, vì dữ liệu lịch sử không còn đúng sau khi policy thay đổi cách ghép. |
| 6 | **Common Random Numbers (CRN)** | Baseline và policy chạy trên cùng kịch bản, cùng số ngẫu nhiên cho từng agent → so sánh theo cặp → ước lượng hiệu ứng nhân quả với khoảng tin cậy hẹp. |
| 7 | **Tách training khỏi simulator** | Behavior model được train ở pipeline riêng, simulator chỉ nạp checkpoint qua model registry (cách Uber làm để giảm RAM/CPU và dễ bảo trì). |
| 8 | **Đúng chiều quan trọng hơn đúng tuyệt đối** | Simulator thường phóng đại độ lớn hiệu ứng; tiêu chí chính là đúng chiều và giữ đúng thứ hạng giữa các phương án (DiDi, Grab cùng nhấn mạnh điều này). |

---

## 3. Kiến trúc tổng thể

```
 ┌──────────────┐   ┌──────────────────┐
 │  DATA LAYER  │──▶│ SCENARIO BUILDER │  demand + supply + thời tiết + traffic + sự cố + seed
 └──────────────┘   └────────┬─────────┘
                             ▼
 ┌───────────────┐   ┌──────────────────────────────┐   ┌─────────────────┐
 │ POLICY PLUGINS│◀─▶│      SIMULATION ENGINE       │◀─▶│ BEHAVIOR MODELS │
 │ (hooks)       │   │ event queue · clock · agents │   │ (model registry)│
 └───────────────┘   └──────┬───────────────┬───────┘   └─────────────────┘
                            │               │
                     ┌──────▼──────┐  ┌─────▼──────────┐
                     │TRAFFIC LAYER│  │   EVENT LOG    │
                     │ ETA · sự cố │  └─────┬──────────┘
                     └─────────────┘        ▼
                                    ┌───────────────────┐
                                    │ EVALUATOR (CRN)   │ → causal effect ± CI
                                    └───────────────────┘
```

| Thành phần | Trách nhiệm |
|---|---|
| **Data layer** | Đơn hàng lịch sử, GPS tài xế, log hủy/nhận, thời tiết, lưới H3. |
| **Scenario builder** | Đóng gói một "thế giới" tất định theo seed: dòng nhu cầu, vị trí tài xế ban đầu, điều kiện giao thông, sự cố, và **toàn bộ số ngẫu nhiên** của từng agent. |
| **Simulation engine** | Hàng đợi sự kiện, đồng hồ, quản lý trạng thái agent, gọi handler, gọi policy hook và behavior model. |
| **Policy plugins** | Logic nghiệp vụ cần đánh giá (ghép chuyến, giá, dispatch, điều xe…). |
| **Behavior models** | Mô hình quyết định của khách và tài xế, nạp từ registry. |
| **Traffic layer** | Thời gian di chuyển theo ô H3 × khung giờ × thời tiết; áp dụng sự cố. |
| **Evaluator** | Chạy cặp baseline/treatment nhiều replication, tính metric, hiệu ứng và khoảng tin cậy. |

---

## 4. Simulation engine

### 4.1 Cơ chế thời gian

Dùng **mô hình lai**:

- **Event-driven** cho từng agent: khách đặt xe, hết kiên nhẫn, xe tới điểm đón, trả khách…
- **Sự kiện định kỳ `DISPATCH_TICK`** để gom đơn và ghép theo batch (Uber chờ vài giây để gom; DiDi dùng cửa sổ 2 giây; Lyft bước 10 giây).

Lõi engine rất nhỏ:

```python
def run(self):
    while self.q:
        t, _, kind, payload = heapq.heappop(self.q)
        self.t = t
        getattr(self, "on_" + kind.lower())(**payload)   # sự kiện → handler
```

### 4.2 Kỹ thuật bắt buộc

- **Tie-break tất định:** heap lưu `(time, seq, kind, payload)`; `seq` tăng dần để hai sự kiện cùng thời điểm luôn xử lý cùng thứ tự → cùng seed cho cùng kết quả.
- **Lazy invalidation:** sự kiện đã lên lịch (ví dụ "hết kiên nhẫn") không bị xóa khỏi heap khi trạng thái đổi; handler tự kiểm tra và bỏ qua nếu không còn hợp lệ.
- **Tách kế hoạch và thực tế** (cách FleetPy): kế hoạch của nền tảng (ETA hứa, lộ trình dự kiến) tách khỏi những gì thực sự xảy ra → đo được sai lệch ETA, mô phỏng được nền tảng thiếu thông tin.

### 4.3 Danh mục sự kiện

| Nhóm | Sự kiện |
|---|---|
| Khách | `REQUEST_CREATED`, `OFFER_SHOWN`, `OFFER_ACCEPTED/REJECTED`, `RIDER_CANCEL`, `PICKUP`, `DROPOFF` |
| Tài xế | `DRIVER_ONLINE/OFFLINE`, `TRIP_OFFERED`, `TRIP_ACCEPTED/REJECTED`, `ARRIVE_PICKUP`, `IDLE_MOVE`, `CHARGE_START/END` |
| Nền tảng | `DISPATCH_TICK`, `REPOSITION_TICK`, `PRICE_UPDATE` |
| Policy | `POLICY_TIMER` (ví dụ: `WAIT_THRESHOLD_REACHED`) |
| Môi trường | `INCIDENT_START/END`, `WEATHER_CHANGE`, `TRAFFIC_UPDATE` |

---

## 5. Agents

| Agent | Trạng thái | Thuộc tính cá nhân (rút từ phân phối) |
|---|---|---|
| **Rider** | `WAITING → MATCHED → ONBOARD → DONE \| CANCELLED` | mức kiên nhẫn, giá trị thời gian, độ nhạy giá, mức sẵn lòng ghép |
| **Driver** | `OFFLINE ↔ IDLE → EN_ROUTE → ON_TRIP → IDLE`, `CHARGING` | khu quen chạy, ngưỡng nhận cuốc, mức pin (nếu xe điện), ca làm |
| **Platform** | (không có state machine riêng) | giữ hàng đợi đơn mở, danh sách xe rảnh, gọi policy |

**Mức độ cá nhân hóa** — chọn theo nhu cầu:

1. Mỗi agent là object riêng, hành vi giống nhau.
2. **Thuộc tính khác nhau rút từ phân phối học từ dữ liệu** ← mức mặc định, đủ cho đa số policy.
3. Tham số lấy từ lịch sử từng người dùng (ẩn danh) — khi policy nhắm vào phân khúc.
4. Có trí nhớ và học qua nhiều ngày (như MaaSSim) — khi cần thấy cân bằng dài hạn.

---

## 6. Điểm ra quyết định & behavior models

Mỗi điểm quyết định có một **interface cố định**; có thể thay model mà không đổi engine:

```python
class RiderCancelModel(Protocol):
    def hazard(self, rider, waited_min, eta_shown, ctx) -> float: ...

class PoolAcceptModel(Protocol):
    def p_accept(self, rider, offer, ctx) -> float: ...
```

Quyết định được lấy bằng `rider.u_xxx < p` với `u_xxx` là số ngẫu nhiên **riêng của agent cho riêng quyết định đó**, sinh sẵn trong kịch bản → đảm bảo CRN.

### 6.1 Phía khách

| Điểm quyết định | Dạng model | Dữ liệu học | Tham khảo |
|---|---|---|---|
| Có đặt xe không khi thấy giá/ETA | Logit / độ co giãn giá | Phiên mở app, biến động giá | Cohen et al. (Uber, NBER) |
| Hủy khi đang chờ | Survival / hazard theo thời gian đã chờ, ETA báo, giờ, thời tiết | Log đặt – hủy | TR-B 2020 về hủy chuyến; Liu et al. về "sunk waiting time" |
| Nhận đề nghị ghép | Logit theo phụ phí/giảm giá, độ vòng, thời gian đã chờ | **Không có sẵn cho trường hợp phụ phí** → khảo sát SP / A/B nhỏ + sensitivity | Alonso-González et al.; nhóm ExMAS/MaaSSim |
| Hủy sau khi đã có xe | Hazard theo ETA còn lại | Log | — |

### 6.2 Phía tài xế

| Điểm quyết định | Dạng model | Dữ liệu học | Tham khảo |
|---|---|---|---|
| Nhận/từ chối cuốc | Logit theo thời gian đón, cước, điểm đến | Log gửi – nhận cuốc | Ashkrof et al. (TR-C 2022, 2024) |
| Đi đâu khi rảnh | **Cây ngẫu nhiên + ma trận chuyển giữa ô H3** theo giờ (cách Uber); nâng cao: IRL | GPS | Uber blog; Equilibrium IRL |
| Online/offline, giờ làm | Mô hình cung lao động; hoặc theo ca nếu tài xế là nhân viên | Log ca làm | Chen & Sheldon; Hall et al. |
| Đi sạc (xe điện) | Ngưỡng SOC + chọn trạm | Log sạc | FleetPy charging module |

> **Cần xác nhận:** mô hình lao động thực tế của hãng (tài xế nhân viên hay đối tác tự do, hay cả hai). Điều này quyết định tài xế có quyền từ chối cuốc hay không, và mức độ cần mô hình hóa hành vi phía tài xế.

### 6.3 Model đơn giản trước, phức tạp sau

Bắt đầu bằng logit/ngưỡng có thể giải thích được, kiểm chứng baseline, rồi mới thay bằng ML. Hướng dùng LLM làm agent (GTA, LLM driver agents) hữu ích để thử phản ứng với policy chưa có dữ liệu, nhưng khó hiệu chỉnh — chỉ nên dùng để khám phá.

---

## 7. Policy plugin

### 7.1 Interface

```python
class Policy:
    name = "baseline"
    def on_request(self, sim, rider): ...
    def on_timer(self, sim, rider): ...
    def on_dispatch(self, sim, open_jobs, idle_drivers): ...   # ghi đè matching
    def price(self, sim, rider, offer): ...                      # ghi đè giá
    def on_driver_idle(self, sim, driver): ...                   # repositioning
```

Policy chỉ được tác động qua API của engine (`sim.schedule`, `sim.offer`, `sim.assign`…), không sửa trực tiếp trạng thái agent.

### 7.2 Ví dụ: ghép chuyến sau 5 phút, +20.000đ

```python
class PoolAfterWait(Policy):
    def on_request(self, sim, r):
        sim.schedule(sim.t + 5, "POLICY_TIMER", r=r)

    def on_timer(self, sim, r):
        if r.state != "WAITING": return
        partner = sim.pooling.find_partner(r, max_o_km=1.5, max_d_km=2.0)
        if partner and sim.behavior.pool_accept(r, 20_000) \
                   and sim.behavior.pool_accept(partner, 20_000):
            sim.merge_jobs(r, partner, surcharge=20_000)
```

### 7.3 Danh mục policy nên hỗ trợ

| Nhóm | Policy |
|---|---|
| Matching / dispatch | Độ dài cửa sổ batch; hold control (giữ đơn chờ cặp tốt hơn); gửi đơn cho nhiều tài xế; bán kính đón tối đa; lọc theo điểm đến tài xế |
| Giá cho khách | Surge/giá cao điểm; upfront pricing; Wait & Save; trợ giá khi thiếu xe |
| Thu nhập tài xế | Phí đón xa, phí chờ; thưởng Quest/Boost; tỷ lệ chiết khấu |
| Điều phối cung | Repositioning/heatmap; dynamic fleet sizing; lịch sạc |
| Ghép chuyến | Độ vòng tối đa; mức giảm giá/phụ phí; **thời điểm đề nghị ghép** |
| Hủy & độ tin cậy | Phí hủy, thời gian ân hạn; ngưỡng tỷ lệ nhận cuốc |
| Phương pháp thí nghiệm | So sánh thiết kế A/B: chia theo người dùng vs switchback theo thời gian |

---

## 8. Traffic layer, thời tiết & sự cố

| Mức | Cách làm | Khi nào dùng |
|---|---|---|
| **1. ETA phụ thuộc thời gian** | Ma trận thời gian di chuyển giữa ô H3 × khung giờ × thời tiết, học từ GPS của hãng | Mặc định |
| **2. Sự cố là sự kiện ngoại sinh** | `INCIDENT_START(cells, factor, duration)` tăng thời gian đi qua vùng ảnh hưởng; tài xế tính lại đường; khách trong vùng có xác suất hủy cao hơn | Đánh giá policy khi có tai nạn, ngập, cấm đường |
| **3. Đồng mô phỏng vi mô** | Ghép với SUMO/MATSim (FleetPy đã có coupling với SUMO) | Khi cần thấy hiệu ứng ngược: xe công nghệ chạy rỗng làm tắc thêm |

**Điểm mấu chốt:** tai nạn và thời tiết là một phần của **kịch bản**, nên với CRN cả baseline và policy gặp đúng cùng một sự cố → đo được "policy hoạt động thế nào khi có tai nạn" mà không lẫn nhiễu.

**Nguồn dữ liệu giao thông:**

- **Ưu tiên GPS của chính hãng:** tốc độ trung bình theo ô H3 × giờ × thời tiết; sự cố cũ hiện ra dưới dạng tốc độ sụt bất thường cục bộ. Miễn phí, không vướng điều khoản.
- Google Routes API (`TRAFFIC_ON_POLYLINE`, Route Matrix): chỉ là API hỏi theo tuyến, không có feed đẩy; điều khoản hạn chế lưu trữ lâu dài → chỉ dùng lấy mẫu kiểm chứng.
- Waze for Cities Data Feed: có cảnh báo tai nạn, tắc, đóng đường; chỉ cho đối tác của chương trình.
- TomTom / HERE: có API luồng giao thông và sự cố — cần kiểm tra độ phủ và điều khoản.

---

## 9. Dữ liệu & kịch bản

**Một kịch bản** = dòng nhu cầu + vị trí/ca tài xế + điều kiện giao thông + thời tiết + sự cố + seed.

| Nguồn | Ưu | Nhược |
|---|---|---|
| **Replay lịch sử** | Sát thực tế nhất (DiDi replay nhiều ngày đơn hàng thật) | Chỉ đúng phần ngoại sinh; mọi thứ sau can thiệp phải mô hình hóa |
| **Synthetic** | Tạo được tình huống chưa từng xảy ra (mưa lớn + sự kiện) | Phải hiệu chỉnh phân phối |

Thư viện kịch bản tối thiểu: ngày thường / cuối tuần; cao điểm sáng / tối; mưa; tai nạn ở trục chính; thiếu xe / thừa xe.

---

## 10. Đánh giá policy

### 10.1 Thiết kế thí nghiệm trong simulator

1. Với mỗi kịch bản `s` và mỗi seed `k`: chạy `baseline(s,k)` và `policy(s,k)` với **cùng** số ngẫu nhiên.
2. Hiệu ứng mỗi cặp: `Δ = metric(policy) − metric(baseline)`.
3. Báo cáo trung bình Δ ± khoảng tin cậy 95% (bootstrap theo ngày/kịch bản).

**Bằng chứng từ prototype (`mini_marketplace_sim.py`, 30 replication, ~3 giây):** CRN thu hẹp khoảng tin cậy của tỷ lệ hoàn thành khoảng **13 lần** (±0,08 so với ±1,05 khi không dùng CRN). Không có CRN, một hiệu ứng nhỏ chìm hoàn toàn trong nhiễu.

### 10.2 Bộ metric

Mỗi policy được chấm bằng: **một metric chính** + **các guardrail** không được xấu quá ngưỡng + **metric chẩn đoán**.

| Nhóm | Metric |
|---|---|
| Khách | Thời gian chờ (trung bình, **p90/p95**); tỷ lệ hoàn thành; tỷ lệ không tìm được xe; tỷ lệ khách hủy; sai lệch ETA; giá thực trả; độ vòng & tỷ lệ nhận ghép |
| Tài xế | Tỷ lệ sử dụng; thu nhập/giờ online; thời gian rảnh giữa cuốc; km chạy rỗng; tỷ lệ từ chối/hủy |
| Nền tảng | Số chuyến; GMV; doanh thu nền tảng; biên đóng góp; hiệu quả chi khuyến khích |
| Vận hành | Chuyến/xe/giờ; khách/xe-km; số xe cần cho cùng mức dịch vụ; sạc (xe điện) |
| Công bằng & ngoại ứng | Chênh lệch theo khu và khung giờ; phân bố thu nhập tài xế; tổng xe-km trên đường |

### 10.3 Ghép metric với policy (ví dụ)

| Policy | Metric chính | Guardrail | Chẩn đoán |
|---|---|---|---|
| Cửa sổ batch | Thời gian chờ trung bình | p95 chờ, tỷ lệ hủy | ETA đón, km rỗng |
| Surge | Biên đóng góp / số chuyến | Tỷ lệ không có xe, giá TB, công bằng theo khu | Co giãn cầu, phản ứng cung |
| Repositioning | Tỷ lệ hoàn thành ở khu thiếu xe | Km rỗng, thu nhập tài xế | Phân bố xe trống theo ô H3 |
| **Ghép sau 5 phút +20k** | **Tỷ lệ hủy / tỷ lệ hoàn thành** | **Độ vòng, thời gian đến nơi, khách ghép hủy, giá TB** | **Tỷ lệ nhận ghép, xe được giải phóng** |

### 10.4 Tiêu chí để tin kết quả

1. **Có ý nghĩa thống kê:** CI 95% không chứa 0.
2. **Có ý nghĩa thực tế:** vượt ngưỡng tối thiểu đặt trước.
3. **Bền vững qua kịch bản:** cao điểm, thấp điểm, mưa, tai nạn, thiếu/thừa xe.
4. **Bền vững qua giả định hành vi:** kết luận không đảo chiều khi tham số behavior thay đổi trong vùng hợp lý.
5. **Bền vững theo thời gian:** xét cân bằng dài hạn khi người dùng thích nghi (tăng cước có thể kéo thêm tài xế và đưa thu nhập/giờ về mức cũ).
6. **Đúng chiều khi kiểm chứng** với A/B thật đã có.

### 10.5 Quy tắc quyết định mẫu (viết **trước** khi chạy)

> Đề xuất A/B nhỏ cho policy ghép chuyến nếu, trên ≥ 30 replication × các kịch bản cao điểm / mưa / tai nạn:
> - Tỷ lệ hủy giảm ≥ 1 điểm % (CI 95% không chứa 0), **và**
> - Thời gian đến nơi của khách được ghép tăng ≤ 8 phút ở p90, **và**
> - Biên đóng góp không giảm, **và**
> - Không khu nào có thời gian chờ p90 tăng quá 10%, **và**
> - Kết luận giữ nguyên khi tỷ lệ nhận ghép giả định dao động ±50%.

*(Các ngưỡng cụ thể do hãng chốt theo mục tiêu kinh doanh.)*

---

## 11. Kiểm chứng & hiệu chỉnh

- **Baseline phải tái tạo lịch sử:** thời gian chờ, tỷ lệ hủy, số chuyến theo giờ và theo khu.
- **So phân bố, không so cá nhân:** bản đồ xe trống theo ô H3 trong mô phỏng vs thực tế (cách Uber kiểm chứng mô hình di chuyển tài xế).
- **Directional consistency:** mỗi khi có A/B thật, chạy lại trong simulator và so chiều + thứ hạng.
- **Sensitivity analysis bắt buộc** cho các tham số không có dữ liệu (đặc biệt: phản ứng với phụ phí ghép).

**Prototype đã cho thấy điều này:** với mô hình chấp nhận giả định, đổi phụ phí ghép từ +20.000đ → 0đ → −20.000đ làm tỷ lệ ghép tăng từ 0,28% → 0,86% → 1,67%. Con số synthetic không có ý nghĩa thực tế, nhưng cho thấy mô hình nhận ghép là thứ quyết định kết quả và cần đầu tư dữ liệu nhiều nhất.

---

## 12. Công nghệ & build vs reuse

| Lựa chọn | Ưu | Nhược |
|---|---|---|
| **Tự viết engine** (Python `heapq`, ~vài trăm dòng lõi) | Kiểm soát hoàn toàn interface policy/behavior, CRN | Phải tự làm routing, pooling |
| **FleetPy** (TU Munich) | Có ride-hailing (xe 1 chỗ) + ride-pooling, nhiều mô hình khách, repositioning, charging, network dynamics theo thời gian, coupling SUMO | Không có tài xế tự quyết — xe làm theo lệnh nhà vận hành |
| **MaaSSim** (TU Delft) | Hành vi hai phía mạnh nhất, decision function cắm được, học day-to-day, có ExMAS cho ghép | Tốc độ mạng cố định, không mô phỏng tắc |
| **RidePy** | Nhanh (Cython/C++), modular | Tập trung vào đội xe, ít hành vi người dùng |

**Đề xuất:** tự viết engine mỏng với interface policy/behavior/CRN như mục 4–7, tái sử dụng thuật toán từ FleetPy (pooling, repositioning) và ý tưởng decision function từ MaaSSim.

**Stack gợi ý:** Python cho engine và policy; H3 cho không gian; OSRM hoặc ma trận ETA tự học; `scipy.optimize.linear_sum_assignment` cho matching; Ray/multiprocessing chạy song song replication; Parquet cho event log; dashboard so sánh baseline vs treatment. Khi quy mô lên hàng trăm nghìn chuyến/ngày: chuyển phần nóng (routing, matching) sang Cython/C++/Numba.

---

## 13. Lộ trình

| Giai đoạn | Nội dung | Đầu ra |
|---|---|---|
| **0. Prototype** *(đã có)* | Engine tối giản, policy plugin, CRN, synthetic data | `mini_marketplace_sim.py` |
| **1. MVP** | Lưới H3 một quận/thành phố; ETA theo giờ; behavior logit đơn giản; bộ metric đầy đủ (p90, độ vòng, km rỗng, theo khu) | Báo cáo baseline vs policy ghép chuyến |
| **2. Data-driven** | Replay đơn lịch sử; survival model hủy chuyến; ma trận chuyển H3 cho tài xế rảnh; model registry | Baseline khớp lịch sử |
| **3. Môi trường** | Thời tiết, sự cố, thư viện kịch bản | Đánh giá policy theo kịch bản |
| **4. Quy mô & tối ưu** | Song song hóa, grid search tham số policy (ngưỡng chờ 3/5/7 phút, phụ phí 0–30k), dashboard | Điểm vận hành tối ưu |
| **5. Vòng phản hồi** | Đối chiếu với A/B thật, hiệu chỉnh lại model; mở rộng day-to-day learning, RL | Simulator được tin dùng trong quy trình ra quyết định |

---

## 14. Rủi ro & câu hỏi mở

1. **Không có dữ liệu cho phản ứng với phụ phí ghép** — gần như mọi nghiên cứu giả định ghép thì được giảm giá. Cần khảo sát stated-preference hoặc A/B nhỏ; trước đó dựa vào sensitivity analysis.
2. **Mô hình lao động của tài xế** chưa được xác nhận → ảnh hưởng mức độ mô hình hóa phía tài xế.
3. **Simulator phóng đại hiệu ứng** do chấm điểm và lấy mẫu kết quả từ cùng một mô hình, bỏ qua nhiễu thực tế → chỉ tin chiều và thứ hạng.
4. **Hiệu ứng dài hạn:** một ngày mô phỏng không thấy được khách bỏ hãng hay tài xế thích nghi.
5. **Interference trong A/B thật:** khi chuyển sang thử thật, cần thiết kế switchback/chia theo vùng; simulator dùng để chọn thiết kế.
6. **Dữ liệu cá nhân:** chỉ dùng dữ liệu ẩn danh và tổng hợp cho behavior model.

---

## 15. Tài liệu tham khảo

**Công nghiệp**
- Uber — [Gaining Insights in a Simulated Marketplace with Machine Learning](https://www.uber.com/se/en/blog/simulated-marketplace/)
- Uber — [Marketplace: Matching](https://www.uber.com/us/en/marketplace/matching/) · [Rider price and driver fare](https://www.uber.com/us/en/marketplace/pricing)
- Lyft — [Experimentation in a Ridesharing Marketplace](https://eng.lyft.com/experimentation-in-a-ridesharing-marketplace-b39db027a66e) · [Simulating a ridesharing marketplace](https://eng.lyft.com/https-medium-com-adamgreenhall-simulating-a-ridesharing-marketplace-36007a8a31f2)
- Lyft & Chicago Booth — [Non-Exclusive Notifications for Ride-Hailing at Lyft II](https://arxiv.org/html/2603.21531)
- Grab — [DispatchGym](https://engineering.grab.com/techblog_-dispatchgym)
- DiDi — [KDD Cup 2020 RL Track](https://github.com/dingyuan-shi/KDDCup-2020-RL-Track-Champion-Code) · [ProfiLLM dispatching simulator](https://arxiv.org/pdf/2606.18803)

**Simulator mã nguồn mở**
- [MaaSSim](https://github.com/RafalKucharskiPK/MaaSSim) · [paper PLOS One](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0269682)
- [FleetPy](https://github.com/TUM-VT/FleetPy) · [paper](https://arxiv.org/pdf/2207.14246)
- [RidePy](https://arxiv.org/pdf/2312.02104)
- [HRSim](https://arxiv.org/pdf/2505.17758)
- [HKU ride-sourcing simulation platform](https://www.sciencedirect.com/science/article/pii/S2772424724000246)
- [BEAM – Rethinking Pooled Ride-Hailing](https://www.mdpi.com/2624-6511/9/4/62)
- [SimMobility On-Demand](https://narslab.org/papers/nahmias-biran-traditional-automated-mobility/)

**Hành vi khách & tài xế**
- [Customer behavioural modelling of order cancellation (TR-B 2020)](https://ideas.repec.org/a/eee/transb/v132y2020icp358-378.html)
- [Passenger waiting behavior with sunk waiting time](https://doi.org/10.2139/ssrn.4285203)
- [Determinants of the willingness to share rides](https://link.springer.com/article/10.1007/s11116-020-10110-2)
- [Using Big Data to Estimate Consumer Surplus: The Case of Uber](https://www.nber.org/system/files/working_papers/w22627/w22627.pdf)
- [Ride acceptance behaviour of ride-sourcing drivers](https://www.sciencedirect.com/science/article/pii/S0968090X22002121)
- [Dynamic Pricing in a Labor Market (Chen & Sheldon)](https://www.anderson.ucla.edu/faculty/keith.chen/papers/SurgeAndFlexibleWork_WorkingPaper.pdf)
- [Ride-Sharing Markets Re-Equilibrate (NBER)](https://www.nber.org/system/files/working_papers/w30883/w30883.pdf)
- [Data-Driven Simulation of Ride-Hailing using Imitation and RL](https://arxiv.org/pdf/2104.02661)

**Giao thông**
- [Google Routes API – traffic on polylines](https://developers.google.com/maps/documentation/routes/traffic_on_polylines)
- [Waze Data Feed specifications](https://support.google.com/waze/partners/answer/13458165?hl=en)
- [MOSS – GPU microscopic traffic simulation](https://arxiv.org/html/2405.12520v1)
