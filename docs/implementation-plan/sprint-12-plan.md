# Implementation plan — Sprint 12: Shared ride V1

| | |
|---|---|
| Sprint | [sprint-12-shared-rides-v1.md](../sprint/sprint-12-shared-rides-v1.md) |
| Backlog đầu vào | [sprint-03-backlog.md](../backlog/sprint-03-backlog.md) — backlog chính thức mới nhất; không đóng mục cũ trong sprint này |
| Trạng thái | Đã thực hiện (2026-10-09) |
| Ngày lập | 2026-10-09 |
| Cơ sở | [requirements §3.8](../requirements.md#38-ghép-chuyến--sr), [các phiên bản](../research/shared-rides-versions.md), chỉ đạo chỉ giữ Shared Only / Exclusive Only |
| Quyết định cước | Người dùng chốt ngày 2026-10-09: Shared = 70% cước đi riêng của từng khách; đây là duyệt quyết định cước, chưa phải duyệt toàn bộ plan |

## 1. Tóm tắt hướng tiếp cận

Triển khai **V1 trước**, nghiệm thu và viết backlog rồi mới lập plan V2. V1 chỉ tạo cặp khi hai khách WAITING,
có xe rảnh và một trong bốn tuyến khả thi. Shared Only không có cặp tiếp tục chờ tới hạn đón rồi hủy;
Exclusive Only đi riêng. Không có fallback hoặc timer 300 s trong V1.

Cước Shared = 0,7 × cước Exclusive trực tiếp của từng booking, báo trước khi booking quyết định và giữ nguyên
suốt lifecycle. Đây là quyết định đã được người dùng chốt; các lựa chọn triển khai khác vẫn cần duyệt plan.

Tạo module `kami/shared/` riêng cho cấu hình, evaluator và dispatch; engine sở hữu mọi thay đổi trạng thái.
Giữ đường chạy hiện tại khi shared tắt. Không gọi `merge_jobs`, `find_partner` hoặc `pool_accept` cho shared mới,
không mở policy plugin. Dùng Stop/Leg, router và cơ chế invalidation của engine hiện có.

Thực hiện từng phần có test: cấu hình → quote/cước 70% → evaluator → dispatch → timeout/hủy → metric → service/manager → replay
→ nghiệm thu. Manager chỉ được bật capability khi worker đã chạy V1 thật; map V1 dùng replay file,
chưa thêm API vehicle live hoặc artifact download. Đặt demo shared riêng, không thay fixture baseline cũ.

Backlog đã đọc: 01, 02, 03. Chưa có backlog 08/09/11 chính thức vì các sprint đó chưa kết thúc.

| Mục | Cách tiếp nhận |
|---|---|
| B02-6 (sản phẩm), B02-1 (location theo nhóm), EV chưa hiện thực | Không xử lý thay Sprint 05. V1 dùng nhóm xe/khả năng đi đường và capacity thực; không nhận cấu hình sản phẩm rồi giả kiểm tra. Demo dùng car; giới hạn được ghi ở UI/tài liệu |
| B02-3, B03-2, B03-3, B03-10 (quy mô/routing/benchmark) | Không đóng. Đo candidate/query, dùng dữ liệu nhỏ và oracle; không thay router hoặc wire format quy mô của Sprint 04 |
| B02-5 (dwell khi môi trường đổi) | Với nhánh shared, bảo đảm giữ giờ xuất phát chưa tới khi replan/retime; test mới. Không đổi nhánh legacy/baseline ngoài phạm vi để tránh thay kết quả cũ |
| B03-9 (E2E) | Bổ sung E2E shared manager/worker và kiểm replay V1; không coi đã đóng toàn bộ bản đồ live |
| Backlog cũ có sprint đích 12 | Chưa có mục nào; kiểm lại trước implement nếu các sprint khác đã kết thúc |

## 2. Quyết định kỹ thuật

Các interface/cost dưới đây là **đề xuất để duyệt**, không phải mô tả code đã có.

| Mã | Lựa chọn | Phương án đã cân nhắc và lý do |
|---|---|---|
| D1 | `SimConfig.shared_ride` và JSON `sim_config.shared_ride` riêng, vắng hoặc `enabled=false` giữ đường chạy cũ. V1 chỉ chấp nhận version 1 | Dùng `pooling` legacy sẽ kéo theo semantics/behavior/policy cũ; dùng cấu hình mới không mở lại API legacy |
| D2 | Lựa chọn request trong `RequestSpec.attrs.service_preference`: `shared_only` hoặc `exclusive_only`; lưu field rõ trên Rider cùng effective mode, pair_id, cancellation reason và deadline | Dùng `pooled` cho consent hoặc sửa lifecycle làm mất khác biệt giữa lựa chọn, cặp và overlap. Request có giá trị rõ được ưu tiên; thiếu thì lấy theo tỷ lệ đã resolve |
| D3 | Dispatch shared greedy trước, rồi matching Exclusive trên xe còn lại. Xếp phương án theo deadline sớm nhất của cặp, deadline còn lại, tổng giây từ lúc xét tới dropoff A/B, tổng mét xe, A/B ID chuẩn hóa, driver ID, thứ tự stops | Hungarian hiện tại giả định các job độc lập; đưa cặp chồng lấn vào sẽ gán trùng. Greedy minh bạch, có oracle bài nhỏ; ưu tiên shared có thể làm Exclusive chờ hơn nên phải báo metric riêng, chưa tuyên bố tối ưu toàn đội |
| D4 | V1 dùng index ô lưới theo radius cấu hình (mặc định 500 m) cho hai điểm đón và hai điểm đến, rồi kiểm khoảng cách thực. Chỉ cắt số xe theo `MatchingParams.candidates_per_job` hiện có, ghi số loại bỏ | Quét toàn bộ O(n²) dễ quá tải. Bộ lọc gần điểm cuối được research đề xuất cho V1; V2 sẽ thay bằng lọc dọc tuyến. Oracle tắt cắt xe trên bài nhỏ; không coi kết quả heuristic là tối ưu toàn cục |
| D5 | Evaluator thử P_A–P_B–D_A–D_B, P_A–P_B–D_B–D_A, P_B–P_A–D_A–D_B, P_B–P_A–D_B–D_A từ `current_loc(driver)`, dùng `traffic.estimate(..., group=driver.group)` tại giờ từng leg, thêm boarding/alighting | Evaluator legacy bắt đầu từ origin khách và giới hạn ratio+absolute không đáp ứng cận 450 s mới. Module mới trả stops, pickup/dropoff, direct baseline, extra ride và tổng cost, không sửa state |
| D6 | Baseline mỗi khách = boarding của chính khách + direct travel ở thời điểm pickup dự kiến, cùng nhóm xe. Giữ baseline lúc commit để đối chiếu actual; cận extra ride áp riêng từng khách, tính dwell người kia. Đòi overlap có độ dài >0 | Tính từ request time hoặc bỏ dwell có thể sai khi traffic đổi. Không cộng alighting của chính khách sau timestamp dropoff; predicted và actual tách rõ |
| D7 | Đánh giá/offer trước, commit sau khi tài xế nhận và eligibility vẫn hợp lệ. Commit nguyên tử thay hai job mở bằng một shared job và gán xe/plan ngay; driver từ chối giữ hai request/job cũ | Không merge trước rồi chờ xe. CRN shared driver acceptance dùng driver ID, cặp rider ID chuẩn hóa và số lần offer của chính cặp–xe; không dùng global job sequence. Mở rộng dữ liệu TripOffer nếu cần với default tương thích, không thêm policy hook |
| D8 | Timeout riêng tại `booked_t + max_pickup_wait_s`, ưu tiên sau ARRIVE_STOP và trước dispatch; token deadline không phụ thuộc rider.version/hazard token. Hủy behavior/deadline dùng chung hàm dọn shared state trong engine | Hazard có thể gài lại theo traffic nên không thay timer deadline. Khách tái chờ giữ booked_t, deadline và hazard waiting đã tích lũy; không rút lại ngân sách waiting cùng khóa |
| D9 | Chưa ai onboard: vô hiệu plan cũ, đóng cặp, giải phóng xe, người còn lại quay về queue shared với đồng hồ cũ. Đã có người onboard: bỏ stop khách hủy và chở người còn lại; không nhận request mới. Sau overlap không ghép nối tiếp | Code hủy cũ sẽ tự giữ job một người và có thể dispatch Shared Only riêng. Khi cặp bị hủy trước overlap, cho tái tìm đối tác nhưng ghi pair history; không coi planned pair là actual shared |
| D10 | **Cước đã chốt:** `shared_fare = 0,7 × exclusive_reference_fare` riêng cho mỗi booking; Exclusive giữ FareModel bình thường. Cước tham chiếu khóa khi quote, gồm surge/minimum/làm tròn hiện có; không tính lại theo tuyến shared. Booking/hazard/driver offer nhìn cước thực thu | Người dùng chọn phương án giảm 30% ngày 2026-10-09. Không chọn cùng giá hoặc markup 1,5 lần tuyến chung. Báo giá độc lập đối tác phù hợp lifecycle hiện có; không thêm acceptance lần hai hoặc slot pool_accept |
| D11 | Metric namespace `shared.*` riêng; event shared mới có pair_id/preferences/stops/prediction/reason. Accumulator độc lập log, cập nhật read-only khi quan sát state | Metric `rider.pool_*` legacy bị API lọc và trộn semantics cũ. Ghi overlap từ giao của các khoảng pickup–dropoff; không cần record_events để tính summary |
| D12 | API nhận cấu hình mới qua public_spec; resolved snapshot chứa đủ shared defaults và tỷ lệ, worker dùng snapshot. Không sửa schema DB nếu JSON/spec/metric/artifact hiện có đủ | Mở endpoint policy/pooling hoặc default mới cho run cũ gây mất tương thích. Health công bố `shared_ride_versions: [1]` sau khi engine/service xong; EV/live snapshot vẫn phản ánh thực tế |
| D13 | Replay bổ sung dữ liệu shared tùy chọn chỉ khi bật shared: cặp, participant, stops, preferences, predicted/actual overlap; loader cũ bỏ qua, loader mới thiếu trường vẫn đọc được | Không thay v1 wire format/quỹ đạo hoặc chuyển sang city-scale format của 04. Demo shared riêng với nguồn run thật; bổ sung bảng chi tiết cặp trên visualizer khi mở replay này |

Cấu hình đề xuất khi bật: `max_pickup_wait_s=600`, `max_shared_extra_ride_s=450`, `candidate_radius_m=500`,
`preference_weights={shared_only: 0, exclusive_only: 1}` nếu không khai báo; admin chọn tỷ lệ để phát sinh shared.
Demo riêng dùng 50%/50%, ghi rõ là giả định. Không thêm `pool_search_window_s` hoặc lựa chọn fallback.
Trọng số hữu hạn, không âm và tổng >0; normalize khi resolve. Radius >0, pickup wait >0, extra ride >=0.
API gửi `shared_fallback_exclusive` bị từ chối với lỗi có path, không đổi thành lựa chọn khác.

### Chi tiết cước và kế toán của D10

- Tính `exclusive_reference_fare` bằng FareModel hiện có cho origin–destination trực tiếp tại quote, cùng quy
  ước nhóm xe của quote. V1 không thêm sản phẩm/bảng giá của Sprint 05/06. Lưu cước này, giá Shared, tỷ lệ 0,7
  và lựa chọn vào quote/log; snapshot resolved lưu quy tắc cước đã dùng. Không cho UI tự đổi tỷ lệ 70% đã chốt.
- Áp minimum và làm tròn theo FareModel **trước** discount; sau đó nhân 0,7, lưu VND, không làm tròn lại về
  100đ hoặc áp minimum Exclusive lần hai. Cước FareModel hiện là bội 100đ nên phần Shared là số nguyên VND.
  Ví dụ minimum Exclusive 25.000đ → Shared 17.500đ; 60.000đ/40.000đ → 42.000đ/28.000đ.
- `Quote.fare` và `Rider.fare` chứa cước thực thu đã discount. `surcharge=0` cho shared mới, tránh dùng negative
  surcharge legacy làm driver payout dựa trên cước chưa giảm. Booking model nhận giá Shared ngay lần đầu;
  không ghi đè giá sau khi booking đã quyết định theo cước khác.
- Không thay giá khi re-pair, traffic đổi hoặc đối tác hủy; Shared Only quá hạn không phục vụ thì không thu
  cước chuyến. Payout/GMV chỉ ghi một lần trên booking DONE, kể cả ngoại lệ mất đối tác sau pickup.
- **Đề xuất giữ kế toán hiện có:** `driver_payout = fare_thực_thu × (1-take_rate)`; tổng cặp bằng tổng payout
  từng booking được phục vụ. Với take_rate mặc định 25%, hai cước Shared tổng 14 cho payout 10,5 và phần
  nền tảng 3,5 trước chi phí. Không thêm bonus/sàn payout/trợ giá hoặc bộ lọc kinh tế mới khi chưa được duyệt.
- Ghi cước tham chiếu, phần tiết kiệm, GMV/payout/phí theo cohort và ngoại lệ mất đối tác để đánh giá lợi ích;
  không tuyên bố tài xế/lợi nhuận luôn tăng. Sàn payout, chi phí thật và lọc kinh tế là hướng nghiên cứu tiếp,
  không phải một yêu cầu đã được xác nhận chỉ bằng quyết định giá khách 70%.

Chọn preference thiếu bằng `CRN(scenario.seed).u("service_preference", request_id)` ở bước build sau khi đã sinh
demand, giữ nguyên draws/lịch request cũ; `crn_seed` riêng vẫn chỉ dùng cho quyết định trong run.
Replay/đối chứng dùng cùng demand và preference đã sinh; không gọi RNG global.

Trong kịch bản bật shared, cả gán Exclusive lẫn gán cặp dùng evaluator mới và kiểm hạn đón trước offer/commit;
không đi qua `self.pooling.evaluate` của `assign()` hiện tại. Nhánh shared tắt giữ assign/evaluator legacy.
Với Exclusive, evaluator xử lý tuyến singleton pickup–dropoff, không áp cận extra ride shared.
Chỉ áp deadline cho request đã đặt; DECLINED không có deadline. Nếu t_stop cắt trước deadline hoặc chuyến kết thúc,
ghi request còn dở riêng thay vì giả timeout/DONE; default drain hiện có không tự kéo dài trong V1.

**Các điểm cần duyệt trong toàn bộ plan:** D3 ưu tiên shared, D4 giới hạn gần điểm cuối, D9 xử lý đối tác và
chi tiết kế toán D10. Công thức giá khách 70% của D10 đã chốt, không cần hỏi lại quyết định đó.
Fallback và quyết định giữ xe V3 để nghiên cứu riêng, không chặn plan V1.

## 3. Thay đổi theo module

| File/module | Thay đổi dự kiến |
|---|---|
| `kami/shared/__init__.py`, `config.py`, `evaluate.py`, `dispatch.py` (mới) | SharedRideConfig, SharedPlanEval, bốn tuyến, index ứng viên và chọn cặp; module không import DB/web/policy/pooling |
| `kami/core/agents.py`, `events.py`, `engine.py` | Field mới có default tương thích; deadline event; booking/dispatch/commit/cancel/shared accounting; giữ nhánh legacy khi tắt |
| `kami/behavior/protocols.py` (TripOffer) | Chỉ nếu cần thêm metadata shared cho driver offer, giữ default/constructor cũ; không thêm model hoặc slot pool_accept |
| `kami/shared/pricing.py` (mới), `kami/pricing.py` (giữ công thức FareModel) | Chuyển cước tham chiếu đi riêng thành 70%, dữ liệu quote và kiểm kế toán; không đổi baseline FareModel hoặc payout legacy |
| `kami/config/specs.py`, `build.py`, `__init__.py` | Parse/validate cấu hình, preference từng request hoặc tỷ lệ; build CRN stable, resolve defaults; export type mới cần thiết |
| `kami/scenario.py` | Giữ RequestSpec attrs và lựa chọn khi từ CSV; field/cột tùy chọn không làm đổi nguồn cũ |
| `kami/metrics.py`, `timeseries.py`, `eventlog.py` | Summary/shared cohorts, wait/detour quantiles, counters và payload sự kiện; không đổi metric legacy khi tắt |
| `kami/store/repository.py`, `runs.py` (nếu đường resolve/persist cần) | Resolve đầy đủ defaults trước tạo queued, ghi summary/timeseries/artifact mới qua interface hiện có; không thay run cũ |
| `kami/service/input.py`, `app.py`, `metrics.py`, `worker.py` | Validation mới, capability thật, metrics/comparison mới; vẫn chặn policy/pooling legacy; worker thật dùng snapshot |
| `kami/replay/export.py`, `schema.py`, `query.py` | Shared metadata tùy chọn và kiểm chứng mốc overlap; tắt shared xuất fixture cũ giống byte |
| `web/src/manager/types.ts`, `scenarioDraft.ts`, `ScenarioForm.tsx`, `metricFormat.ts`, `RunResults.tsx`, `MetricsPage.tsx` | Toggle V1, hai tỷ lệ, wait/extra phút và radius mét; field errors; metric theo lựa chọn và giải thích giả định EV/giá |
| `web/src/data/`, phần chi tiết trong `web/src/map/` và visualizer hiện có | Đọc metadata shared tùy chọn, hiển thị cặp/stops/overlap của replay; không tạo vehicle live hoặc sửa renderer city-scale |
| `scenarios/shared/v1-demo.json`, `web/public/fixtures/shared_v1_demo/` (mới) | Demo riêng từ engine; không ghi đè demo Hà Nội baseline |
| `tests/test_shared_*.py` (mới), test config/service/replay/isolation hiện có; web test/E2E | Test evaluator, invariants, deadline/hủy, snapshot/worker thật và UI |
| `benchmarks/shared/v1/` (mới), `benchmarks/results/` | Cases shared riêng và kết quả so baseline cùng môi trường; không trộn legacy pooling vào suite mới |
| `docs/engine/02`, `03`, `04`, `05`, `09`, `10`, `11`, `13`, `18`, `20`, `21`, `22` và README | Cập nhật file module tương ứng cùng code; thêm hướng dẫn shared riêng nếu nội dung dài |

Các đường dẫn module mới là dự kiến, có thể tách file nhỏ khi implement; thay interface/quyết định lớn cần duyệt
lại. Không sửa `draft/draft.md`, không cập nhật version package kami chỉ vì tên tính năng V1.

## 4. Kế hoạch theo hạng mục

| Hạng mục | Các bước, file và phụ thuộc |
|---|---|
| S12-1 | 1. Thêm config shared/type preference với default. 2. Validation hữu hạn/tỷ lệ/deadline, reject fallback. 3. Build preference qua CRN khi thiếu và giữ CSV attrs. 4. Resolve defaults trong snapshot, test queued → sửa nguồn → run không đổi. Files: shared/config, core/agents, config, scenario, store/service. Làm trước mọi dispatch |
| S12-2 | 1. Evaluator thuần thử bốn tuyến từ xe thật. 2. Tính dwell/direct baseline/overlap và deadline từng khách theo group. 3. Unreachable trả infeasible. 4. Oracle enumeration trên lưới và OSM fixture, ties ổn định. Files: shared/evaluate, tests/test_shared_evaluate. Dựa S12-1 |
| S12-3 | 1. Tách queue shared/exclusive. 2. Index/lọc cặp và xe rảnh đủ chỗ. 3. Offer dùng behavior driver hiện có/CRN riêng, rejection không merge. 4. Commit cặp/stops/driver nguyên tử. 5. Match Exclusive trên xe còn lại, giữ hạn đón shared-scenario. Files: shared/dispatch, core/engine, driver offer. Dựa S12-2 |
| S12-4 | 1. Deadline event riêng, pickup cùng timestamp ưu tiên. 2. Dùng chung cleanup behavior/timeout. 3. Pair dissolve trước pickup, survivor queue/deadline/hazard không reset. 4. Sau pickup reroute theo vị trí thật và version, giữ dwell chưa xong. 5. Test traffic/shift/late/stale events và hủy đúng lúc stop. Files: core/events/engine; tests/test_shared_lifecycle. Dựa S12-3 |
| S12-5 | 1. Events pair_created/dissolved, timeout, prediction và actual. 2. Accumulator độc lập log cho cohorts/overlap/km/vi phạm. 3. Metric snapshot không đổi state hoặc CRN, time-series và service comparison có đơn vị/hướng tốt xấu đúng. 4. Đối chiếu cước tham chiếu/tiết kiệm/GMV/payout/phí từ S12-9. Files: metrics/timeseries/eventlog/service metrics. Dựa S12-4/9 |
| S12-6 | 1. Library example/CLI JSON mới. 2. Public_spec/worker và health capability thật. 3. Form hai lựa chọn, phút↔giây, radius, mặc định khi bật và giữ hidden data khi sửa. 4. E2E DB/worker thật: tạo → chạy → kết quả → reload → sửa nguồn kiểm snapshot cũ. Files: config/service/manager. Dựa S12-5; đọc skill UI và web/AGENTS trước viết UI |
| S12-7 | 1. Export shared metadata và loader optional. 2. Demo deterministic riêng, chọn cặp xem hai khách/stops/overlap. 3. Đối chiếu các mốc request/match/pickup/dropoff/cancel với engine, ghi ảnh và hướng dẫn xuất/mở replay. Files: replay/web data/visualizer/demo. Dựa S12-4/5; không gắn fixture vào run live |
| S12-8 | 1. Full suite/compatibility/isolation. 2. Benchmark baseline trước/sau, shared mixed/timeout/cancel/road với đối chứng. 3. Ghi env/solver/candidate/query và limits. 4. Cập nhật engine docs cùng code, cuối sprint viết backlog và trạng thái. 5. Lập sprint V2 sau V1, tham chiếu B12-k liên quan. Không implement V2 trong lượt V1 |
| S12-9 | Sau S12-1, trước S12-3: 1. Wrapper cước thuần tính reference FareModel rồi Shared 70%. 2. Quote trước booking, lưu reference/discount vào Rider/log/snapshot. 3. Driver offer và DONE accounting dùng cước thực thu, không surcharge legacy. 4. Giữ giá khi re-pair/mất đối tác/traffic đổi. 5. Test minimum/surge/rounding, booking nhìn giá đúng, no-service/no-charge và payout một lần; UI giải thích cước 70%. Files: shared/pricing, core/engine/agents, config, metrics, manager |

## 5. Kiểm chứng acceptance criteria

| AC | Test/lệnh/bằng chứng dự kiến |
|---|---|
| AC12-1 | `tests/test_shared_config.py` và config/build/service tests: defaults 600/450/500, finite/negative/zero/normalize, preference override, reject fallback; edit scenario sau queued kiểm resolved snapshot không đổi |
| AC12-2 | `test_shared_dispatch`: oracle bốn orders × mọi xe trên bài nhỏ không cắt; tie stable; two/three requests; driver rejection giữ queue; hai cặp tranh một xe, một request tranh hai cặp; invariant job/driver/rider |
| AC12-3 | `test_shared_evaluate`: A đạt/B vượt và ngược lại, cận đúng 450, dwell người kia, car/bike capacity, đường một chiều/no-route, pickup dự kiến >600, latest pickup/dropoff chặt hơn; D_B giữa tuyến nhưng xa D_A vẫn bị V1 lọc đúng giới hạn |
| AC12-4 | `test_shared_lifecycle`: no driver/no partner hết 600, pair ở 570 nhưng xe tới >600 bị reject; pickup đúng 600 và >600; ONBOARD qua 600 vẫn chạy; hazard hủy sớm; stale timer sau pickup; booked_t/deadline giữ khi tái chờ |
| AC12-5 | `test_shared_lifecycle`: hủy ở WAITING/MATCHED, hủy người đón trước/sau, chưa ai onboard vs có người onboard; stop cleanup/current_loc/plan_version; traffic đổi trong boarding, cùng timestamp; không teleport/cộng trùng km và không reset hazard |
| AC12-6 | Đối chiếu tính độc lập từ log với accumulator cho cohorts, quantiles, overlapping intervals và violation; rerun record_events=false cùng summary. Pair không overlap hoặc overlap 0 phải actual=false; no-data xuất null, không 0 giả |
| AC12-7 | Web unit round-trip 10/7,5 phút↔600/450 s, hai tỷ lệ/validation/preserve hidden. E2E service+SQLite+worker thật qua manager, đọc DB/API kiểm snapshot/summary sau reload; không mock worker trong bằng chứng nghiệm thu |
| AC12-8 | `test_shared_replay` và web loader tests: exporter hai lần byte-identical, cặp/mốc/stops đúng, legacy thiếu metadata vẫn đọc; đối chiếu các thời điểm có 0/1/2 người onboard; kiểm trực quan demo ở 1280/1440 và lưu ảnh |
| AC12-9 | Full Python, web tests/typecheck/build; run quickstart/presets và `examples/02_pool_after_wait.py` để kiểm API 0.1; baseline record_events/log/metrics/fixture không đổi khi bỏ shared config hoặc enabled=false; isolation subprocess không nạp DB/web; seed/config duplicate log và replay |
| AC12-10 | Harness repeat 5 cùng máy, env/solver/router; baseline trước/sau và đối chứng shared riêng cùng demand, preference/seed. Báo served theo cohort, wait p50/p90/p95, extra ride, overlap, cancel/no-pair, km tổng/rỗng, GMV/payout, query/candidate, wall/event/s/RAM; backlog ghi từng AC và phần chờ V2 |
| AC12-11 | `tests/test_shared_pricing.py` (mới): 100.000→70.000, 25.000→17.500, 60.000/40.000→42.000/28.000, surge/minimum trước discount, VND chính xác. Spy booking/hazard/driver offer nhận cước Shared từ đầu; integration hủy/traffic/re-pair không đổi quote; DONE ghi một payout, unserved không thu cước; GMV=payout+phần nền tảng trước chi phí, record_events=false vẫn đúng. Snapshot và UI hiển thị quy tắc 70%; baseline tắt shared không thay giá |

Các lệnh dự kiến (file/case shared được tạo trong implementation):

```text
python -m unittest discover -s tests -t .
python examples/01_quickstart.py
python examples/02_pool_after_wait.py
python -m kami presets
python -m kami run --spec scenarios/shared/v1-demo.json --out out/shared-v1
python -m kami replay export --spec scenarios/shared/v1-demo.json --out out/shared-v1-replay
python -m kami bench --repeat 5 --out benchmarks/results/2026-10-09-shared-v1-before.json
python -m kami bench --repeat 5 --compare benchmarks/results/2026-10-09-shared-v1-before.json --out benchmarks/results/2026-10-09-shared-v1-after.json
python -m kami bench --suite benchmarks/shared/v1 --repeat 5 --out benchmarks/results/2026-10-09-shared-v1.json
```

Ngày của file kết quả thay theo ngày chạy thực tế. Trong `web/`: `npm test`, `npm run typecheck`,
`npm run build`, E2E manager mở rộng theo scripts hiện có.

Mốc backlog chính thức: [2026-10-08-sprint03.json](../../benchmarks/results/2026-10-08-sprint03.json)
(Linux/Python 3.10/router C++). Mốc Windows tham khảo:
[2026-10-09-sprint09-a-windows.json](../../benchmarks/results/2026-10-09-sprint09-a-windows.json),
baseline grid 1,419 s / 8.375 events, nots 1,150 s, surge 1,158 s.
Không so trực tiếp hai môi trường; đo baseline working tree trước sửa code V1 trên môi trường sẽ nghiệm thu,
báo riêng chênh lệch so backlog cũ và mọi case không chạy được. Không bỏ qua >10% vì nhiễu mà thiếu phép đo A/B.

Đối chứng vận hành tắt shared sẽ phục vụ riêng tất cả request trên cùng demand; báo rõ đây là arm đối chứng
cho Shared Only, không thay semantics trong arm V1. So sánh giảm km phải kèm số served và hủy từng cohort.

## 6. Mock & phần dự kiến chưa làm

Không dự kiến mock engine, driver acceptance, pairing hoặc worker. Demand synthetic, tỷ lệ demo và giới hạn
thời gian là giả định mô phỏng được ghi nhãn. UI metric lấy run thật, replay demo cũng từ run thật.

EV/SOC/sạc và tương thích sản phẩm đầy đủ vẫn chờ 05/06; không tạo SOC giả hoặc báo feasibility EV.
Không tạo fallback dưới cờ tắt hay dùng tên placeholder vì người dùng đang nghiên cứu.
Không làm V2/V3/V4, city-scale hoặc vehicle live trong V1. Nếu thiếu phụ thuộc thật buộc phải mock,
ghi `# MOCK(B12-k): ...`, xin duyệt thay đổi lớn nếu ảnh hưởng AC và ghi backlog; không đánh dấu AC đạt giả.

## 7. Rủi ro & phương án dự phòng

- Chi phí router: index, route cache phạm vi một tick và khóa group/traffic version; dùng số query để quyết định
  tối ưu. Cache không qua tick có traffic đổi khi chưa chứng minh hợp lệ. Không thay router Sprint 04.
- Greedy và shared-first ảnh hưởng service rate Exclusive: báo riêng hai cohort; đổi thứ tự ưu tiên là đổi D3,
  phải duyệt lại, không âm thầm tối ưu vì benchmark.
- Pair dissolution và partial leg phức tạp: triển khai/test trước nối UI; thời gian boarding còn lại phải giữ.
- Snapshot/spec mở rộng: thêm optional fields, giữ sparse serialization khi shared tắt; chạy fixture byte test.
- Code 08/09 A hiện có chưa hoàn tất sprint: chỉ mở rộng giao diện V1 đã duyệt trong sprint này; thiếu API
  live/replay downloads không chặn xuất/mở file replay, không tuyên bố nghiệm thu phần B.
- Nếu baseline full tests đang lỗi vì môi trường, ghi evidence trước implement và sửa điều kiện chạy hoặc nêu
  blocker; không chuyển lỗi hiện hữu thành trạng thái test pass. Không đánh dấu V1 Xong khi thiếu AC bắt buộc.

## 8. Lịch sử thay đổi

- 2026-10-09: lập plan V1 theo yêu cầu implement shared từng phiên bản; mở Sprint 12 riêng.
- 2026-10-09: người dùng thu hẹp còn Shared Only và Exclusive Only; fallback chờ nghiên cứu, bỏ timer 300 s
  khỏi phạm vi/config V1; giữ deadline 600 s và extra ride 450 s đã chốt trước đó.
- 2026-10-09: giá V1 dùng chung FareModel là đề xuất D10 cần duyệt; chưa sửa code hoặc chạy benchmark mới.
- 2026-10-09: người dùng yêu cầu nghiên cứu cước thực tế, ví dụ giảm 10→7 và phương án tổng cước 1,5 lần
  tuyến chung/chia tỷ lệ. Thêm tài liệu research pricing và chuyển D10 thành quyết định cần chốt;
  chưa cập nhật requirements/AC hoặc coi một công thức đã được duyệt.
- 2026-10-09: người dùng chốt mỗi khách Shared trả **70% cước đi riêng của họ**. Cập nhật SR-9, D10,
  S12-9/AC12-11, quote/rounding/kế toán và lịch sử; quyết định cước đã được duyệt, toàn bộ plan vẫn Chờ duyệt.

- 2026-10-09: người dùng duyệt toàn bộ plan trong hội thoại, yêu cầu implement V1; bắt đầu triển khai D1–D13.

- 2026-10-09: tách state mutation sang `core/shared_lifecycle.py`, thêm accumulator `shared/metrics.py`; không đổi D1–D13. CLI lưu `shared.json` để replay từ run folder giữ metadata; đây là chi tiết persist của S12-7.
- 2026-10-09: test OSM phát hiện fallback đường chim bay của router legacy trên đường cấm/no-route. Evaluator V1 kiểm reachability của graph theo group trước estimate; không đổi router/semantics 0.1.
- 2026-10-09: kiểm chứng Windows dùng CPython 3.12 với site-packages `.venv`; sửa đóng DB CLI/test và shutdown HTTP test để cleanup SQLite đúng. RSS benchmark dùng GetProcessMemoryInfo thay resource trên Windows. Dataset Hà Nội hiện có graph nhưng thiếu manifest OSM; test provenance ghi skip rõ, fixture Hồ Gươm được build/kiểm thật.

- 2026-10-09: benchmark snapshot tạm trước tích hợp V1 dùng đường dẫn data khác, làm đổi thuộc tính/vị trí xe trong fleetpy_demand legacy. Bổ sung bản engine nguyên trạng từ HEAD trước task, giữ source hash và chỉ thay harness RSS/output; đo lại repeat 5 với KAMI_DATA_ROOT tuyệt đối giống working tree. Không thay generator legacy. E2E bổ sung run Hà Nội worker thật đạt 4 actual pairs/8 Shared served.

- 2026-10-09: thu hẹp điều kiện thiếu manifest chỉ vào test provenance TestHanoiNetwork, giữ các test graph/demand/fixture legacy Hà Nội chạy trên dữ liệu đang có. Ví dụ pooling 0.1 trên Windows chạy bằng tham số sẵn có `1 1` (một seed, serial); default multiprocessing fork không được Windows hỗ trợ, không thêm API pooling/policy trong V1.

- 2026-10-09: nghiệm thu AC12-1…AC12-11; full Python 242 test/7 skip có lý do, web 75 test/typecheck/build và E2E 5 kiểm chứng pass. Baseline 6×5, shared/control 8×5 deterministic, A/B tối đa +7,29% wall/+1,14% RSS. Ghi [backlog 12](../backlog/sprint-12-backlog.md); lập đề xuất Sprint 13 V2, chưa duyệt/implement V2.

- 2026-10-09: sinh lại fixture Shared sau sửa sampler overlap, thêm test so từng byte với exporter hiện tại. Hồi quy cuối: Python 242 test/7 skip có lý do và E2E 5 kiểm chứng pass trên fixture cuối.

- 2026-10-10: người dùng yêu cầu trực tiếp bổ sung bộ lọc Xe share và hai lớp người đặt Shared/Exclusive trong visualizer. Mở rộng hiển thị S12-7: phân loại cặp đang phục vụ, cắt vệt tại biên cặp, marker BOOKED→pickup/cancel, công tắc độc lập và cuộn cột điều khiển. Không đổi engine, dữ liệu replay, quyết định ghép/cước hoặc AC của sprint đã nghiệm thu.
- 2026-10-10: kiểm chứng bổ sung đạt 85 web test, typecheck, production build và E2E 6 kiểm chứng trên service/worker thật. Browser kiểm riêng xe/vệt Shared, công tắc bàn phím, hai lớp khách theo booking thật, glyph S/E đã vẽ, tua qua pickup/cancel và cột lọc không bị playback che ở 1280/1440. Lưu ảnh `filters-shared-only-1440.png`, `filters-requests-1280.png`, `filters-requests-1440.png`; căn khung bản đồ chừa đủ chỗ cho bảng điều khiển.
- 2026-10-10: người dùng yêu cầu thấy trọn quy trình từ hai booking đến đón/trả từng khách. Bổ sung fixture `shared_v1_walkthrough` bằng ví dụ thư viện trên mạng Hà Nội: xe ở xa, hai pickup và hai dropoff khác nhau, chờ batch ghép thật. Chuyển demo mặc định sang fixture này, thêm Xem từ đầu/tua từng mốc/trạng thái/nhãn bốn điểm; giữ fixture cũ và không đổi engine/config/AC. Ví dụ ghi rõ giả định booking chắc chắn/không hủy để quan sát vòng đời.
- 2026-10-10: kiểm chứng quy trình đầy đủ đạt 87 web test, typecheck/production build, 5 test replay Python (gồm so từng byte fixture mới) và E2E 7 kiểm chứng. Browser thao tác nút phát/tua cho đủ booking→waiting→match→pickup 1/2→dropoff 1/2, kiểm marker chờ 1/2/2/1/0 và onboard 0/0/0/1/2/1/0; ảnh `walkthrough-matched-1440.png` chờ bảng xe cập nhật đúng thời gian. Các mốc/di chuyển đều từ engine thực tế; không chạy lại benchmark engine vì engine không đổi trong lượt bổ sung hiển thị này.
