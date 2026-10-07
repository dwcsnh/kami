# 05 · Common Random Numbers (`kami/core/crn.py`)

## Mục tiêu

Baseline và treatment phải gặp **cùng một thế giới** và **cùng "số phận ngẫu nhiên"** của từng agent. Khi đó
`Δ = metric(treatment) − metric(baseline)` chỉ còn hiệu ứng của policy, gần như không có nhiễu (design doc §2.6,
§10.1).

## Thiết kế: số ngẫu nhiên đánh địa chỉ theo khoá

```python
crn = CRN(seed)
crn.u("pool_accept", rider_id, offer_no)   # đều (0,1), tất định theo (seed, stream, keys)
crn.exp("cancel_waiting", rider_id)        # Exp(1)
crn.normal("x", key)                       # N(0,1), Box–Muller
crn.choice_index(weights, "idle_move", driver_id, k)
```

Mỗi số được tính bằng `blake2b(seed | stream | keys)` rồi chuẩn hoá về (0,1), nên không phụ thuộc thứ tự gọi,
không phụ thuộc tiến trình và không phụ thuộc phiên bản Python.

**Vì sao không dùng một `random.Random` chung?** Nếu policy làm đổi thứ tự hoặc số lượng quyết định (ví dụ thêm
một lần hỏi ghép), mọi số rút sau đó sẽ lệch, và cặp baseline/treatment mất tính ghép cặp. Đánh địa chỉ theo khoá
cho đúng ngữ nghĩa "số ngẫu nhiên sinh sẵn cho từng agent, từng quyết định" của design doc, mà không cần biết trước
sẽ có bao nhiêu lần rút.

## Danh mục khoá trong engine

| Quyết định | Khoá | Ghi chú |
|---|---|---|
| Đặt xe | `("book", rider)` | |
| Hủy lúc chờ | `("cancel_waiting", rider)` → `exp` | Ngân sách hazard |
| Hủy khi đã có xe | `("cancel_matched", rider)` → `exp` | |
| Nhận ghép | `("pool_accept", rider, lần_đề_nghị_thứ_k)` | Pooling, ngoài phạm vi 0.2 |
| Tài xế nhận cuốc | `("driver_accept", driver, job, số_lần_job_bị_từ_chối)` | Cùng cặp tài xế–job thì cùng số |
| Nghỉ ca sớm | `("shift_stop", driver, số_chuyến_đã_chạy)` | |
| Đi đâu khi rảnh | `("idle_move", driver, k)`, `("idle_node", driver, k)` | |

Phần **ngoại sinh** (dòng request, thuộc tính cá nhân, ca làm, sự cố) được rút một lần khi dựng `Scenario`, bằng
`random.Random` có seed theo tên và seed kịch bản. Tất cả arm dùng chung object `Scenario` đó.

## Bằng chứng

- `tests/test_core.py::TestCRNPairing::test_noop_policy_is_identical_to_baseline`: một policy đặt timer nhưng không
  làm gì cho ra metric **giống hệt** baseline.
- `tests/test_evaluation.py::test_crn_narrows_ci`: trên 12 seed, CRN giảm độ lệch chuẩn của Δ hơn 2 lần. Đo thực
  tế: Δ`rider.booked` 14,6 → 3,1, Δ`completion_rate` 0,027 → 0,009 (Hungarian).
- Muốn tắt CRN để so sánh thì dùng `Experiment(..., crn=False)` hoặc `--no-crn`.

## Giữ CRN khi viết code mới

1. **Model không tự rút số ngẫu nhiên.** Model trả xác suất, hazard hoặc phân phối; engine quyết định bằng `u < p`.
2. Khi viết policy hoặc engine có quyết định ngẫu nhiên mới, dùng `sim.crn.u("<tên_quyết_định>", agent_id, …)`
   với khoá **ổn định giữa các arm** (id agent, id job, số thứ tự lần hỏi của *chính agent đó*). Không dùng thứ tự
   toàn cục làm khoá.
3. Không dùng `random`, `numpy.random` hay thời gian hệ thống bên trong một lần chạy.

> CRN không loại được mọi nhiễu. Một khi policy đổi một phép gán, các phép gán sau có thể khác theo dây chuyền
> (hiệu ứng cánh bướm của matching). CRN giữ cho phần nhiễu còn lại ở mức nhỏ nhất có thể.
