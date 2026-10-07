# 12 · Evaluation (`kami/evaluation/`)

## Thí nghiệm cặp với CRN (`experiment.py`)

```python
exp = Experiment(
    scenario_fn=lambda name, seed: builder.preset(name, seed=seed),   # tất định theo (name, seed)
    scenarios=["weekday_am_peak", "rain", "accident", "undersupply"],
    seeds=range(30),
    arms={"baseline": Baseline, "pool": lambda: PoolAfterWait()},     # factory không đối số
    behavior_fn=BehaviorSuite,       # factory, mỗi lần chạy một suite mới
    config=SimConfig(),
    crn=True,
)
res = exp.run(n_jobs=-1, progress=True)      # -1 = mọi CPU
```

- Với mỗi `(kịch bản s, seed k)`, `Scenario` được dựng **một lần** và dùng cho mọi arm. Các arm chạy với cùng
  `crn_seed = k`. `crn=False` cho arm thứ hai seed khác, để đo xem CRN loại được bao nhiêu nhiễu.
- **Song song:** `multiprocessing` với context `fork`. Tiến trình con thừa hưởng network (kể cả router C++ của
  FleetPy) thay vì pickle. Mỗi task là một cặp (s, k) và chạy hết các arm. Chỉ hỗ trợ Linux/macOS; Windows dùng
  `n_jobs=1`.
- Kết quả là `ExperimentResult.records`, danh sách `RunRecord(scenario, seed, arm, metrics, zones, wall_s, events)`.
  `to_csv()` ghi một dòng cho mỗi lần chạy. `keep_sims=True` giữ lại object `Simulation` (tốn RAM).

## Ước lượng hiệu ứng (`stats.py`)

`res.compare("baseline", "pool")` trả về một `Comparison`. Với mỗi metric:

| Trường `Effect` | Ý nghĩa |
|---|---|
| `baseline`, `treatment` | Trung bình theo arm trên các cặp mà cả hai giá trị đều xác định |
| `delta` | Trung bình Δ theo cặp |
| `ci_low`, `ci_high` | **Bootstrap phân tầng** 95%: lấy mẫu lại các replication *bên trong từng kịch bản* (theo design doc là "bootstrap theo ngày/kịch bản"), 2.000 lần |
| `t_low`, `t_high` | Khoảng t-Student của Δ (để đối chiếu) |
| `sd_delta` | Độ lệch chuẩn của Δ, dùng đo hiệu quả của CRN |
| `rel` | Δ / baseline |
| `significant` | CI không chứa 0 |
| `verdict` | `better` / `worse` / `≈` theo `DIRECTION` (docs/engine/11) |
| `by_scenario` | Δ trung bình theo từng kịch bản (kiểm tra độ bền qua kịch bản) |

Ngoài ra `Comparison` có:
- `zone_effects`: p90 thời gian chờ theo zone ở mỗi arm và thay đổi tương đối;
- `arm_means`: trung bình từng arm kể cả khi metric chỉ xác định ở một arm, ví dụ `pooled_travel_time_p90`.

`cmp.table([...])` in bảng văn bản.

## Quy tắc quyết định (`decision.py`), viết **trước** khi chạy

```python
rule = DecisionRule("pool → small A/B", [
    Condition("rider.cancel_rate", "delta_le", -0.01, significant=True, label="hủy giảm ≥1pp"),
    Condition("rider.pooled_travel_time_p90", "cross_delta_le", 8.0,
              baseline_metric="rider.travel_time_p90", label="p90 đến nơi của khách ghép +≤8'"),
    Condition("platform.contribution_margin", "delta_ge", 0.0, label="biên không giảm"),
    Condition("wait_p90", "zone_rel_le", 0.10, label="không khu nào p90 chờ +>10%"),
])
print(rule.evaluate(cmp))     # Verdict: PASS/FAIL và chi tiết từng điều kiện
```

| `kind` | Kiểm tra |
|---|---|
| `delta_le` / `delta_ge` | Δ trung bình ≤ / ≥ ngưỡng |
| `rel_le` / `rel_ge` | Δ tương đối |
| `ci_high_le` / `ci_low_ge` | Cả khoảng tin cậy nằm dưới / trên ngưỡng (bảo thủ) |
| `cross_delta_le` | `arm_means.treatment[metric] − arm_means.baseline[baseline_metric]` ≤ ngưỡng |
| `zone_rel_le` | Mọi zone: thay đổi tương đối của `metric` ≤ ngưỡng |

`significant=True` yêu cầu thêm CI không chứa 0. `pooling_rule_example()` là quy tắc mẫu ở design doc §10.5; các
ngưỡng là giá trị giữ chỗ, hãng cần tự chốt.

## Độ bền (`sensitivity.py`)

```python
variants = {"x0.5": lambda: BehaviorSuite(pool_accept=ProbabilityScaler(LogitPoolAccept(), 0.5)),
            "x1.0": BehaviorSuite,
            "x1.5": lambda: BehaviorSuite(pool_accept=ProbabilityScaler(LogitPoolAccept(), 1.5))}
sens = behavior_sensitivity(exp, variants, "baseline", "pool", n_jobs=-1)
sign_stable(sens, "rider.cancel_rate")     # {"deltas":…, "signs":…, "stable": True/False}

rows = policy_grid(exp, lambda wait_threshold, surcharge: PoolAfterWait(wait_threshold=wait_threshold,
                                                                         surcharge=surcharge),
                   {"wait_threshold": [180, 300, 420], "surcharge": [0, 10_000, 20_000, 30_000]})
```

Mapping sang 6 tiêu chí tin kết quả của design doc §10.4:

| Tiêu chí | Công cụ |
|---|---|
| 1. Ý nghĩa thống kê | `Effect.significant`, `Condition(significant=True)` |
| 2. Ý nghĩa thực tế | Ngưỡng trong `Condition` |
| 3. Bền qua kịch bản | `Effect.by_scenario`; `rule.evaluate(res.compare("baseline", "pool", scenario="rain"))` cho từng kịch bản |
| 4. Bền qua giả định hành vi | `behavior_sensitivity` + `sign_stable` |
| 5. Bền theo thời gian | Chưa có học day-to-day (docs/engine/17) |
| 6. Đúng chiều với A/B thật | Chạy lại A/B cũ thành arm, so chiều và thứ hạng |

## Báo cáo (`report.py`)

`report.write("out/report.md", cmp, title=..., verdict=verdict, notes=...)` tạo file Markdown gồm: thông tin thí
nghiệm, decision rule, bảng hiệu ứng (`DEFAULT_METRICS`), Δ theo kịch bản và 5 zone có p90 chờ tăng nhiều nhất.

## Ví dụ kết quả thật (`examples/02_pool_after_wait.py`, 4 kịch bản × 30 seed)

- Policy "ghép sau 5', +20k, kể cả khách đã có xe" chỉ chạm tới khoảng **0,1%** số chuyến (`pool_rate` ≈ 0,0012).
  Cùng bậc với prototype trong design doc (0,28%).
- Tỷ lệ hủy giảm 0,1 điểm %. CI không chứa 0 nhưng không đạt ngưỡng 1 điểm %, nên quy tắc trả về **FAIL**.
- Dấu của hiệu ứng giữ nguyên khi đổi giả định nhận ghép ×0,5 / ×1,5, nhưng độ lớn thay đổi nhiều. Điều này đúng
  với cảnh báo của design doc: mô hình nhận ghép là thứ quyết định kết quả.
