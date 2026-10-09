# Backlog sau Sprint 12 — Shared ride V1

| | |
|---|---|
| Sprint | [sprint-12-shared-rides-v1.md](../sprint/sprint-12-shared-rides-v1.md) |
| Plan | [sprint-12-plan.md](../implementation-plan/sprint-12-plan.md) |
| Ngày kết thúc | 2026-10-09 |

## Trạng thái acceptance criteria

| AC | Kết quả (Đạt / Một phần / Không) | Bằng chứng / ghi chú |
|---|---|---|
| AC12-1 | Đạt | test_shared_config, test_shared_service; validation, weights, defaults, snapshot bất biến; Exclusive không vào cặp |
| AC12-2 | Đạt | test_shared_dispatch: bốn tuyến × xe, greedy cost/tie; 3/4/5 khách tranh xe, hai cặp không gán trùng, rejection không merge |
| AC12-3 | Đạt | test_shared_evaluate: cận riêng A/B, đúng 450 s, dwell/cam kết/chỗ; OSM một chiều và node motorbike-only thực; V1 loại điểm cuối xa |
| AC12-4 | Đạt | test_shared_lifecycle: deadline 600, exact boundary, no partner/driver, MATCHED traffic tới trễ, ONBOARD không timeout, clock giữ |
| AC12-5 | Đạt | Hủy trước/sau pickup, re-pair, hazard budget, partial km/dwell, stale arrival, shift end và cancel cùng timestamp pickup |
| AC12-6 | Đạt | test_shared_metrics/pricing/replay: cohort, quantile, predicted/actual, zero overlap; record_events false; sampler giữa event; JSON null |
| AC12-7 | Đạt | 75 web tests/typecheck/build và E2E 5 kiểm chứng: form 600/450, SQLite/worker thật, reload, sửa nguồn giữ run cũ; worker Hà Nội thực sự phục vụ Shared |
| AC12-8 | Đạt | test_shared_replay và loader; xuất trực tiếp/folder byte-identical; demo riêng engine thật, 0/1/2 onboard; ảnh 1280/1440 |
| AC12-9 | Đạt | Full suite 242 test, 235 pass/7 skip có điều kiện; web 75 pass; 0.1 quickstart/pooling serial/presets; SHA256 source gốc/absent/disabled; core không DB/web/RNG global |
| AC12-10 | Đạt | Full legacy 6 case ×5, shared/control 8 case ×5 xác định; A/B 5 case ×5/arm tuần tự luân phiên, lớn nhất +7,29% wall/+1,14% RSS, tất cả kết quả legacy giống nhau; số liệu và giới hạn bên dưới |
| AC12-11 | Đạt | test_shared_pricing/lifecycle/service, quote 70% trước booking/driver offer; minimum/surge/rounding; DONE payout một lần; không thu unserved; giữ giá re-pair/traffic/hủy |

## Mục còn mở

| Mã | Loại | Mức độ | Mô tả | Lý do chưa làm | Sprint dự kiến xử lý | Trạng thái |
|---|---|---|---|---|---|---|
| B12-1 | Ý tưởng | Cao | V2 tìm dọc tuyến: D_B nằm giữa hành trình A dù xa D_A; xét hai hướng | Giới hạn endpoint là D4 V1 đã duyệt; V2 cần plan riêng | 13 | Mở; [sprint đề xuất](../sprint/sprint-13-shared-rides-v2.md) |
| B12-2 | Chờ phụ thuộc | Cao | Profile/index/cutoff và quality/runtime khi 100k request/8k xe; routing Python/C++ | Quy mô GreenSM thuộc 04, greedy V1 không tối ưu toàn cục | 04 | Mở; theo dõi B03-3/B03-10 |
| B12-3 | Chờ phụ thuộc | Cao | Feasibility SOC/sạc và tương thích sản phẩm, giá động đầy đủ | Sprint 05/06 chưa hiện thực; V1 chỉ kiểm group/chỗ/router/ca | 05/06 | Mở |
| B12-4 | Chờ phụ thuộc | Cao | Replay/live vehicle API gắn run manager | API live/geometry/download thuộc 08/09 phần B; V1 dùng replay file riêng | 08/09 B | Mở |
| B12-5 | Chờ phụ thuộc | Thấp | Chạy lại kiểm router C++ và provenance/zone manifest Hà Nội đầy đủ | Môi trường Windows chưa build extension; data có graph nhưng thiếu manifest OSM | 04/11 | Mở; test thiếu phụ thuộc ghi rõ |
| B12-6 | Nợ kỹ thuật | Thấp | Default parallel Experiment/ví dụ pooling legacy dùng multiprocessing fork, không có trên Windows | Giữ API 0.1, không mở rộng pooling trong V1; chạy tham số serial sẵn có | 11 | Mở; ví dụ kiểm chứng bằng `02_pool_after_wait.py 1 1` |

Không có hạng mục V1 chức năng được chuyển sang backlog. Không implement V2/V3/V4,
fallback, bonus/sàn payout hoặc nghiên cứu lợi nhuận thay người dùng.
Backlog đầu vào chính thức là Sprint 03; không có mục cũ được chỉ định xử lý ở 12.
Các mục B03-* giữ sprint dự kiến cũ, không đánh dấu đã xử lý thay các sprint đó.

## Mock đang dùng

| Thành phần | Mock gì | Thay bằng gì, khi nào |
|---|---|---|
| Engine/evaluator/driver acceptance/service worker/SQLite/replay | Không có mock trong kiểm chứng tích hợp | Dùng triển khai và worker thật |
| Demand/grid/model và CSV demo Hà Nội | Input minh họa, tham số mô phỏng; không phải dữ liệu vận hành GreenSM đã hiệu chỉnh | Hiệu chỉnh khi có dữ liệu và sprint liên quan; không quảng bá kết quả demo thành hiệu quả thực tế |

## Số liệu mốc

Môi trường: CPython 3.12.1, Windows 11 build 26200, AMD64 Family 25 Model 80
Stepping 0 (AuthenticAMD), 12 logical CPU; cùng executable `.runtime/sprint08/venv`
và site-packages `.venv` (NumPy/SciPy/pyarrow). Solver Hungarian, router Python;
C++ không được build. Hash nguồn nghiệm thu nằm trong validation JSON.

Bản gốc dựng nguyên trạng từ HEAD `57f1a531c0c040e3e3353d3ba112b3dcd48a2df3`
(tại đầu task không có thay đổi code kami), chỉ dùng harness RSS/output mới cho
cả hai arm. Cùng KAMI_DATA_ROOT tuyệt đối, cùng CSV path: generator legacy dùng
chuỗi đường dẫn trong seed thuộc tính/vị trí xe. Các lượt thử với checkout/data
path khác không được dùng làm mốc. Không đổi generator để ép kết quả đối chứng.

### Baseline đầy đủ, repeat 5

[Before](../../benchmarks/results/2026-10-09-shared-v1-before.json),
[after](../../benchmarks/results/2026-10-09-shared-v1-after.json).
Tất cả events và metric kiểm kết quả giống nhau, cả hai arm đều deterministic.
Các lượt đầy đủ chạy khác thời điểm có dao động CPU; ghi nguyên số đo, không xóa
case chậm. Các case cần xác minh được chạy A/B bên dưới trước nghiệm thu.

| Case | Before median (s) | After median (s) | Δ | Events | After event/s | Before/after RSS (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| grid_am_peak_baseline | 1.085 | 1.177 | +8.5% | 8375 | 7114 | 79.8/79.9 |
| grid_am_peak_baseline_nots | 1.056 | 1.190 | +12.7% | 8375 | 7040 | 79.6/79.9 |
| grid_am_peak_surge | 1.097 | 1.228 | +11.9% | 8456 | 6888 | 79.6/79.8 |
| grid_pm_peak_x5 | 2.956 | 3.341 | +13.0% | 26170 | 7834 | 104.1/105.3 |
| hanoi_am_peak_small | 156.407 | 136.770 | -12.6% | 7493 | 55 | 195.4/195.3 |
| road_example_400 | 10.040 | 10.253 | +2.1% | 3894 | 380 | 89.8/90.1 |

### A/B xác minh hiệu năng

[A/B JSON](../../benchmarks/results/2026-10-09-shared-v1-ab.json): năm lượt mỗi
arm/case, luân phiên AB/BA, từng child process tuần tự sau khi full test/E2E đã
kết thúc; không chạy benchmark khác song song. Cùng đường dẫn data tuyệt đối.
Events/metric mỗi lượt giống nhau. Mọi case dưới ngưỡng 10% cả wall và RAM.

| Case | Before median (s) | After median (s) | Δ wall | Δ RSS |
|---|---:|---:|---:|---:|
| grid_am_peak_baseline | 1.060 | 1.137 | +7.29% | +0.27% |
| grid_am_peak_baseline_nots | 1.070 | 1.097 | +2.52% | +0.20% |
| grid_am_peak_surge | 1.060 | 1.061 | +0.10% | +0.41% |
| grid_pm_peak_x5 | 3.039 | 3.078 | +1.28% | +1.13% |
| road_example_400 | 10.302 | 9.933 | -3.59% | +0.07% |

Không suy luận V1 làm router Hà Nội nhanh hơn từ chênh lệch hai lượt đầy đủ.
Mốc Sprint 03 (Linux/Python 3.10/C++) và Windows Sprint 09 tham khảo khác môi
trường; không lấy tỷ lệ của chúng để đánh giá thoái lui V1. B12-2/B12-5 giữ việc
nghiệm thu C++/quy mô thành phố ở sprint tương ứng.

### Shared và đối chứng, repeat 5

[Full JSON](../../benchmarks/results/2026-10-09-shared-v1.json) chứa đầy đủ hai
cohort (requests/booked/served/cancelled/unfinished, wait p50/p90/p95), extra ride
actual/predicted, violation, timeout/no-pair, overlap, reference/GMV/payout/phí,
query/candidate/cutoff, wall/min/max/event/s/RSS. Tám case deterministic.

Control tắt shared phục vụ riêng mọi request cùng demand/preference/seed; cohort
control được gắn nhãn ngoài engine bằng cùng CRN demand. Control không phải
fallback trong V1. S/E dưới đây là lựa chọn Shared Only/Exclusive Only ban đầu.

| Case | Served S/E | Cancel S/E | Unfinished S/E | Actual pairs | Km tổng/rỗng | Wall (s) | Event/s | RSS (MiB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cancel-exclusive-control | 4/0 | 113/0 | 2/0 | — | 22.90/16.10 | 0.596 | 1244 | 73.8 |
| cancel-shared | 1/0 | 139/0 | 0/0 | 0 | 7.01/5.41 | 0.295 | 2722 | 26.2 |
| mixed-exclusive-control | 22/23 | 35/29 | 3/1 | — | 103.80/21.00 | 0.636 | 1062 | 73.7 |
| mixed-shared | 12/34 | 48/22 | 0/0 | 6 | 101.53/31.63 | 0.660 | 1158 | 74.3 |
| road-exclusive-control | 9/10 | 0/0 | 0/0 | — | 38.75/1.92 | 0.619 | 521 | 135.9 |
| road-shared | 8/10 | 1/0 | 0/0 | 4 | 32.91/5.87 | 0.667 | 506 | 136.6 |
| timeout-exclusive-control | 45/0 | 64/0 | 4/0 | — | 103.80/21.00 | 0.626 | 1078 | 73.8 |
| timeout-shared | 0/0 | 144/0 | 0/0 | 0 | 16.48/16.48 | 0.069 | 9469 | 25.9 |

Mixed V1 phục vụ Shared 12 thay vì 22 ở control, Exclusive 34 thay vì 23; tổng
46 thay vì 45. Giảm km 103,80→101,53 không có nghĩa service rate mọi cohort tốt
hơn. Road Shared phục vụ 8+10, control 9+10; km 32,91 so với 38,75. Timeout/cancel
ít km và nhanh hơn chủ yếu vì ít served; không coi đó là tối ưu thuật toán hoặc
lợi nhuận được bảo đảm. Bộ lọc điểm cuối/cutoff/greedy là giới hạn V1 đã duyệt.

E2E worker Hà Nội thật: planned=actual=4, Shared booked=9/served=8/cancelled=1,
Exclusive served=10; overlap 17,9724 phút. Shared reference 249.600, GMV 174.720,
payout 131.040, phí nền tảng 43.680 và tiết kiệm cước 74.880 VND. Đây là demand
minh họa; không phải kết quả vận hành GreenSM đã hiệu chỉnh.

## Bằng chứng và giới hạn môi trường

[Validation JSON](../../benchmarks/results/2026-10-09-shared-v1-validation.json),
[SHA256 tương thích](../../benchmarks/results/2026-10-09-shared-v1-compatibility.json),
[engine guide](../engine/23-shared-rides-v1.md),
[ảnh worker phục vụ Shared](../engine/img/shared-v1/results-shared-served-1440.png).

Full Python: 242 test, 235 pass/7 skip; web 75 pass, typecheck và production build
pass, E2E 5 kiểm chứng với service/SQLite/worker thật. 0.1 quickstart, presets và
pooling (một seed, serial trên Windows) chạy; ví dụ Shared phục vụ hai khách.

Bảy skip gồm sáu test cần C++ (kể cả fixture replay Hà Nội gốc đã sinh với C++) và
một test provenance cần manifest OSM Hà Nội. Graph/demand/congestion Hà Nội vẫn
được kiểm; Hồ Gươm fixture build thật từ PBF, test one-way/group/no-route thật.
Demo/worker/benchmark Shared Hà Nội dùng graph hiện có, backend Python. Không
tạo manifest giả hoặc sửa fixture legacy để làm test pass.

Không có code V2/V3/V4, fallback, city-scale/live geometry hoặc EV/SOC mock.
Sprint tiếp theo cho tính năng shared là [13 — V2 đề xuất](../sprint/sprint-13-shared-rides-v2.md),
nhận B12-1, theo dõi B12-2/B12-5; phải duyệt phạm vi/AC và plan trước code.
