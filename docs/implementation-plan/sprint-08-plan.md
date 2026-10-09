# Implementation plan — Sprint 08: Backend service & quản lý lần chạy

| | |
|---|---|
| Sprint | [sprint-08-backend-run-manager.md](../sprint/sprint-08-backend-run-manager.md) |
| Backlog đầu vào | [sprint-06-backlog.md](../backlog/sprint-06-backlog.md) — chưa tồn tại; sẽ đọc và bổ sung khi Sprint 06 kết thúc. Từ [sprint-01-backlog.md](../backlog/sprint-01-backlog.md): xem lại **B01-4** (SQLite/PostgreSQL). Không có mục khác ở backlog 02–03 được giao cho 08 |
| Trạng thái | Đã duyệt (2026-10-08) |

## 1. Tóm tắt hướng tiếp cận

Người dùng yêu cầu ngày 2026-10-08 làm trước những phần có thể triển khai song song với Sprint 04.
Plan chia thực hiện thành hai giai đoạn; không thay đổi phạm vi hoặc acceptance criteria của sprint.

- **Giai đoạn A — đề xuất làm ngay sau khi duyệt:** service HTTP độc lập; CRUD loại xe, fleet, trạm sạc và mẫu
  kịch bản theo schema đang có; tạo snapshot run; worker tiến trình riêng chạy engine hiện tại; giới hạn một run;
  huỷ, phục hồi, tiến độ và metric live qua SSE; đọc và so sánh metric tổng hợp/chuỗi thời gian.
- **Giai đoạn B — chờ phụ thuộc:** tích hợp mô hình fleet/EV của 05, matching/pricing hoàn chỉnh của 06;
  tích hợp event log streaming và replay đã được chốt/hiện thực ở 04; snapshot vị trí xe và API quỹ đạo theo thời gian.
  Đọc backlog 06 và cập nhật chi tiết plan trước khi làm; thay đổi interface/quyết định lớn phải duyệt lại.

**Duyệt plan này chỉ cho phép bắt đầu giai đoạn A sớm khi 05–06 chưa xong.** Phụ thuộc 01/05/06 của sprint vẫn giữ
nguyên; không đánh dấu sprint Xong hoặc coi AC về tính năng còn thiếu là đạt. Giai đoạn A dùng simulation thật,
không giả lập tác dụng của pin/sạc, pricing mới hoặc metric phân rã chưa có.

Cơ sở khảo sát: checkout tại commit 002c62c; Sprint 04 có plan Chờ duyệt; Sprint 08 chưa có plan trước tài liệu này.
Không sửa các thay đổi đang có ở .gitignore, web/.gitignore và web/scripts/build-tokens.mjs.

## 2. Quyết định kỹ thuật

| Mã | Lựa chọn đề xuất | Phương án đã cân nhắc và lý do |
|---|---|---|
| D1 | FastAPI + Uvicorn, module mới kami/service; extra service và service-test; giữ core dependencies rỗng | Flask hoặc HTTP tự viết: cần thêm công sức cho contract/validation. FastAPI phù hợp hướng đề xuất của requirements Q5. Chọn phiên bản dependency và kiểm tra Python 3.9/3.10 khi implement; không nâng yêu cầu Python của core |
| D2 | Giữ SQLite/WAL, mỗi request/worker tự mở connection trong đúng thread/process sử dụng; SQL chỉ nằm trong kami/store | PostgreSQL chưa cần cho service nội bộ, một run; B01-4 được xem lại và tiếp tục ghi rõ giới hạn SQLite. Không thêm ORM hoặc sửa migration đã áp |
| D3 | API /api/v1; create trả 201, start bất đồng bộ trả 202; missing/deleted trả 404; xung đột tên/trạng thái/tham chiếu trả 409; cấu hình sai trả 422 với errors chứa path/message | Không đưa thông báo exception thô thành contract; dùng Spec.from_dict và SpecError hiện có, không xây bộ validation thứ hai |
| D4 | Mẫu kịch bản API lưu RunSpec đầy đủ, gồm fleet và outputs; bổ sung bảng service_scenario liên kết scenario.id để giữ mẫu RunSpec, lưu cùng ScenarioSpec trong một transaction | Bảng scenario hiện chỉ chứa ScenarioSpec ngoại sinh, không có fleet/outputs. Không sửa ScenarioSpec, RunSpec hoặc builder của sprint khác; giữ Repository.save_scenario và CLI 0.1 hoạt động |
| D5 | API mới không nhận policy_group, plugin hoặc cấu hình pooling; baseline do RunSpec mặc định cung cấp nội bộ. Matching/pricing mới chờ schema 06 | Không biến lớp tương thích policy 0.1 thành API sản phẩm. RunSpec qua API vẫn dùng được qua CLI sau khi đã giải tham chiếu |
| D6 | Snapshot bất biến tại tạo run queued: resolve toàn bộ ref, lưu source/provenance; start dùng snapshot, không resolve lại | Resolve lúc start có thể chạy cấu hình khác sau khi người dùng sửa fleet/kịch bản. API không dùng ref đến thực thể đã xoá mềm, kể cả ref số nguyên |
| D7 | Một supervisor API và một worker simulation dùng multiprocessing spawn; dùng khoá service theo đường dẫn DB để từ chối instance API thứ hai; claim run bằng transaction và cập nhật có điều kiện | Không chạy simulation trên event loop/thread HTTP; không Celery/Redis. Không chỉ dùng biến Python để bảo đảm một run. queued là trạng thái đã tạo, không tự động xếp hàng chạy |
| D8 | Worker gọi build_run(snapshot).simulation().run(), ghi kết quả qua Repository; adapter mới, không gọi execute vì execute tự tạo run mới | Không sửa kami/store/runs.py đang do 04 thay đổi. Adapter giữ cùng luồng tính metric và format artifact hiện tại; tích hợp streaming ở B sau khi contract 04 ổn định |
| D9 | Tiến độ đọc từ sim.t qua EventLog.subscribe, chuyển IPC có giới hạn; metric live lấy các dòng hoàn chỉnh đã có trong sim.timeseries.rows, không thay sampler | Không thêm event, không sửa vòng lặp engine, không gọi lại metrics() toàn bộ ở mỗi event. Nhịp phát theo wall-clock cấu hình, chỉ gửi dữ liệu có thật; im lặng khi đang load/không có mẫu mới không đồng nghĩa treo |
| D10 | Huỷ: dừng và join worker trước khi nhả slot; timeout mục tiêu 3 giây, force terminate khi cần. Mọi cập nhật terminal dùng điều kiện trạng thái/ownership | Tránh race worker hoàn tất đúng lúc huỷ, ghi succeeded đè cancelled hoặc chạy hai worker. Run terminal không start lại; tạo run mới để chạy lại |
| D11 | Phục hồi có ownership: khoá service, worker giữ khoá thực thi và watchdog IPC để thoát nếu supervisor mất; chỉ nhả slot/đánh dấu failed sau khi biết worker cũ đã dừng | Không chỉ đổi DB running thành failed rồi lập tức chạy worker mới trong khi tiến trình mồ côi còn chạy. Dùng failed + mã interrupted (schema hiện có không có trạng thái interrupted) |
| D12 | SSE cho progress, metric và terminal; queue giới hạn, client chậm nhận thông báo resync rồi đọc DB; không để client làm chặn engine | WebSocket chưa cần vì client chỉ nhận. SSE giai đoạn A chưa có payload vị trí/quỹ đạo; không tự định nghĩa replay thay cho 04 |
| D13 | NaN/Infinity ra JSON null; so sánh theo DIRECTION, metric thiếu/null không có verdict; cảnh báo khác seed, cấu hình kịch bản hoặc môi trường nếu đã có metadata | Không tự tính lại metric engine; giữ kết quả lưu DB, bỏ metric pooling khỏi báo cáo API 0.2. Không tuyên bố kiểm định nhân quả từ so sánh hai run đơn |
| D14 | CLI service tách riêng: python -m kami.service --db ... --artifacts ... --host 127.0.0.1 --port 8000; một API worker, không reload khi chạy run | Tránh sửa kami/cli.py và docs/engine/15-cli.md cùng lúc với 04. Ở A thêm tài liệu 21-service-api.md và liên kết từ engine/README; cập nhật 15-cli ở B khi phối hợp với 04 |

Tài liệu tham khảo cho D1/D7: [FastAPI — server workers](https://fastapi.tiangolo.com/deployment/server-workers/).
Một Uvicorn worker là lựa chọn triển khai của kami; worker simulation là tiến trình riêng do supervisor quản lý.

**Đã được người dùng chốt khi duyệt ngày 2026-10-08:** đồng ý làm giai đoạn A trước phụ thuộc 05–06; dùng FastAPI/Uvicorn + SQLite;
SSE; huỷ mục tiêu 3 giây; để snapshot xe/replay v2 và tích hợp EV/pricing sang B. Các chi tiết contract ở trên
thuộc nội dung duyệt, không cần hỏi lại từng lựa chọn nếu duyệt toàn bộ plan.

## 3. Thay đổi theo module

| Module/file | Nội dung giai đoạn A | Ranh giới với Sprint 04 |
|---|---|---|
| kami/service/{__init__,__main__,app,entities,runs,metrics,supervisor,worker,stream}.py (mới) | App factory, routes, supervisor/IPC, worker, SSE, JSON | Chỉ gọi API engine/config/eventlog hiện có; import service không khởi động process |
| kami/store/service.py (mới) | ServiceRepository dùng Repository hiện có, mẫu kịch bản, lifecycle/ownership, transaction, kiểm tra thực thể active | Không sửa runs.py; không truy cập SQL trong service HTTP |
| kami/store/migrations/NNNN_service.sql (mới) | Bảng service_scenario và metadata claim/progress/ownership cần cho service | Chọn số tiếp theo tại lúc implement; không sửa migration cũ; phối hợp nếu 04 cũng thêm migration |
| pyproject.toml | Extra service/service-test; package-data cho SQL migration để wheel chạy được | Không sửa core dependencies hoặc requires-python |
| tests/test_service_{entities,runs,stream,metrics}.py (mới) | Integration HTTP, worker thật, lifecycle/crash/concurrency | Test dùng file DB tạm và synthetic nhỏ, không phụ thuộc fixture 8k xe |
| tests/test_isolation.py | Cho phép import web/DB trong đúng service boundary; thêm kiểm tra core không import service/web/DB | Không bỏ kiểm tra NFR-5; service là lớp ngoài tương tự store/replay |
| docs/engine/21-service-api.md (mới), 18-config-persistence.md, engine/README.md | Endpoint/schema, trạng thái, vận hành, giới hạn giai đoạn A, boundary mới | Nếu file chung đã đổi trong nhánh 04 thì merge có chủ đích, không ghi đè |
| docs/implementation-plan/sprint-08-plan.md | Tiến độ, thay đổi chi tiết và phần B sau khi đọc backlog 06 | Không sửa plan 04 |

Giai đoạn A không sửa engine.py, matching.py, config/*, eventlog.py, trajectory.py, replay/*, store/runs.py,
web/*, fixture hoặc benchmark harness. Khi cần thay interface ở các module này, dừng phần phụ thuộc và cập nhật
plan để thống nhất với người làm 04.

## 4. Kế hoạch theo hạng mục

Thứ tự A: nền HTTP/store → S08-1/2 → S08-3/4 → S08-5 → S08-6/7/8 → S08-10; kiểm chứng sau từng phần.
S08-9 và các phần phụ thuộc của S08-1/6/7/10 thuộc B.

| Hạng mục | Các bước, module và điều kiện hoàn thành |
|---|---|
| S08-1 | A: thêm app factory và routes GET/POST/PUT/DELETE cho vehicle-types, fleets, charging-stations, scenarios; dùng spec hiện tại và ServiceRepository. Mẫu scenario giữ RunSpec không policy, resolve kiểm tra active refs; sửa theo id giữ danh tính, trùng tên trả 409. B: dùng schema fleet/EV và matching/pricing của 05–06 sau khi đọc backlog; không phát minh trường trước |
| S08-2 | A: soft-delete qua Repository; API đọc/list/resolve loại bản xoá mềm. Run giữ snapshot độc lập; run đã queued vẫn chạy được sau sửa/xoá nguồn. Loại xe bị fleet active dùng tiếp tục bị chặn. Kiểm tra create/edit/delete và name reuse không làm snapshot cũ đổi |
| S08-3 | A: POST /runs nhận mẫu kịch bản hoặc RunSpec hiện tại; resolve và kiểm dependency output trước tạo queued; GET /runs và /runs/{id}; POST /runs/{id}/start và /cancel. Tiến độ gồm phase, simulation_time, scenario_end/stop_time, fraction kẹp [0,1], ETA null khi chưa ước lượng được; chỉ terminal thành công mới biểu diễn hoàn tất thực thi |
| S08-4 | A: supervisor spawn worker từ snapshot; transaction claim từ queued sang running; từ chối start khi bận với 409. Không giữ transaction trong khi simulation chạy. Worker build/run và publish IPC; lỗi build/worker exit/spawn fail đều nhả tài nguyên, ghi failed; test hai start đồng thời |
| S08-5 | A: graceful shutdown dừng worker; worker watchdog phát hiện mất supervisor. Startup chỉ recover run do service sở hữu, không đổi trạng thái run CLI khác; bảo đảm worker cũ không còn chạy trước nhận start mới. Test kill supervisor thật và khởi động lại, ngoài test DB stale |
| S08-6 | A: GET /runs/{id}/stream SSE progress/metric/terminal, nhịp wall-clock cấu hình; lấy dòng sampler thật, IPC bounded, lưu chuỗi thời gian đầy đủ lúc kết thúc. Test client chậm/ngắt kết nối và không làm đổi metric. B: snapshot vị trí/trạng thái xe cùng quy tắc replay 04, tần suất/chunk/version tương thích visualizer; chưa chốt wire format trong A |
| S08-7 | A: adapter worker ghi metric summary, timeseries, event log theo outputs hiện tại và metadata artifact; NaN lưu theo Repository. Thành công chỉ được ghi sau persist; cancelled/failed không được trả kết quả chưa hoàn chỉnh như kết quả thành công. B: streaming 04 và metric zone/giờ/fleet/loại xe/sản phẩm với phân loại do 05–06 cung cấp; chưa bổ sung phép tính metric của sprint khác |
| S08-8 | A: GET /runs/{id}/metrics, /timeseries và GET /runs/compare?ids=...; so sánh candidate trừ baseline đầu danh sách, DIRECTION cho verdict, null cho số không xác định và percent delta khi baseline = 0. Cảnh báo khác scenario/seed/CRN và môi trường nếu có. Không trả metric pooling trong báo cáo 0.2 |
| S08-9 | B: API manifest/chunk/quỹ đạo giới hạn khoảng thời gian dùng exporter/query chính thức sau 04; validate replay và so query Python. A chỉ liệt kê metadata artifact đã có, không công bố endpoint quỹ đạo tạm rồi đổi contract |
| S08-10 | A: tài liệu 21-service-api.md, engine/README và ranh giới isolation ở 18; ví dụ synthetic có fleet và seed, lệnh chạy service riêng. B: cập nhật 15-cli và định dạng stream/quỹ đạo chính thức phối hợp với 04; ghi backlog đầy đủ khi kết thúc sprint |

## 5. Kiểm chứng acceptance criteria

| AC | Cách kiểm chứng | Mức nghiệm thu sau A |
|---|---|---|
| AC08-1 | HTTP round-trip bốn nhóm entity, sai kiểu/trường/ref trả errors theo path; duplicate 409, deleted 404, thiếu resource 404; kiểm snapshot sau update/delete | Một phần: schema hiện tại; matching/pricing/EV hoàn chỉnh chờ B |
| AC08-2 | HTTP tạo vehicle type → fleet → scenario template → run queued → start → succeeded; đọc snapshot chứng minh fleet được chọn thật | Chứng minh trên engine hiện tại; nghiệm thu lại với 05–06 ở B |
| AC08-3 | Barrier gửi hai start đồng thời từ hai client: một claim thành công, một 409; quan sát worker active tối đa một. Thử instance service thứ hai dùng cùng DB bị từ chối | Có thể kiểm chứng ở A |
| AC08-4 | Worker thật chạy case đủ dài; chờ running rồi huỷ, đo ≤ 3 giây trên máy test, assert process đã exit/join và trạng thái cancelled; kiểm race cancel/finish và huỷ queued | Có thể kiểm chứng ở A |
| AC08-5 | SSE nhận progress và ít nhất một metric row trước terminal trên run đủ dài; cấu hình nhịp; client ngắt/chậm không chặn run; row live bằng row cuối lưu DB | Phần progress/metric kiểm ở A; snapshot xe S08-6 chờ B |
| AC08-6 | So summary/timeseries DB với cùng snapshot chạy trực tiếp; null tương ứng NaN. Test persist failure không được succeeded | Có thể kiểm chứng summary/timeseries ở A; phân rã S08-7 chờ B |
| AC08-7 | Snapshot resolved ghi file, chạy CLI run --spec với cùng môi trường, so metric và số event; so thêm service có/không client SSE; loại trừ wall time khỏi so sánh | Có thể kiểm chứng ở A, lặp lại sau tích hợp B |
| AC08-8 | Kill supervisor trong integration subprocess, restart service, assert worker cũ dừng, run cũ failed/error_code interrupted; start run mới không tạo overlap; không recover run CLI không thuộc service | Có thể kiểm chứng ở A |
| AC08-9 | TestClient/httpx và subprocess worker thật với DB/artifact tạm: tạo dữ liệu → chạy run nhỏ → đọc metric; lỗi validation, run fail, conflict, cancel, restart có test riêng | Tích hợp engine hiện tại ở A, mở rộng EV/pricing/replay ở B |

Lệnh sau khi implement A:

- python -m unittest discover -s tests -t . — toàn bộ test cũ/mới; test service yêu cầu extra service-test trong môi trường nghiệm thu.
- python examples/01_quickstart.py — tương thích thư viện và ví dụ.
- python -m kami presets — tương thích CLI.
- python -m kami bench --repeat 5 --out benchmarks/results/2026-10-08-sprint08-a.json — đổi ngày theo ngày đo thực tế.
  So với mốc gần nhất trong cùng môi trường (hiện là Sprint 03, benchmarks/results/2026-10-08-sprint03.json).
  Nếu 04 đã hoàn tất thì dùng mốc backlog 04; không so số liệu Windows với mốc Linux như bằng chứng thoái lui.
- Chạy cùng case qua service có/không SSE để ghi chi phí adapter/live; PERF-4 ở 09, không nhận là đã đạt từ case nhỏ.
- Kiểm package wheel chứa SQL migrations và smoke mở service với DB mới từ package đã cài.

Ở A chưa chạy nghiệm thu GreenSM đầy đủ và FPS; đó là đầu ra 04 và tích hợp B/11. Ghi số liệu thực đo cùng môi
trường, phiên bản dependencies và seed; không đưa số dự đoán vào cột kết quả.

## 6. Mock & phần dự kiến chưa làm

Không dự kiến mock production. Test double chỉ dùng kiểm lỗi/timeout, không thay test worker thật hoặc bằng chứng AC.

| Mã dự kiến nếu còn mở khi kết thúc sprint | Phần chờ | Điều kiện xử lý |
|---|---|---|
| B08-1 | Fleet/EV, trường charging, matching/pricing của 05–06 và backlog đầu vào 06 | Sprint 05–06 Xong và cập nhật plan B |
| B08-2 | Replay chính thức, snapshot live, API quỹ đạo S08-6/S08-9 | Interface 04 được duyệt/hiện thực và kiểm thử chéo |
| B08-3 | Event log streaming ở adapter service | API 04 ổn định; không giữ log cả ngày trong RAM sau tích hợp |
| B08-4 | Metric phân rã fleet/loại xe/sản phẩm cùng zone/giờ và lưu/truy vấn thống nhất | Dữ liệu và quy tắc attribution từ 05–06; kiểm tổng phân rã đúng phạm vi đo |
| B01-4 | PostgreSQL | A giữ SQLite; chỉ xem lại khi có nhu cầu nhiều service/multi-user thực tế |

Các mã B08 trên là dự kiến, chưa phải backlog đã nghiệm thu. Dừng sau A vẫn giữ sprint Đang làm và plan Đã duyệt,
không chuyển sang Đã thực hiện/Xong. Khi kết thúc toàn bộ sprint, viết backlog bắt buộc (kể cả trống), cập nhật
bảng backlog và Backlog đầu vào của Sprint 09 theo AGENTS.md.

## 7. Rủi ro & phương án dự phòng

| Rủi ro | Xử lý |
|---|---|
| Plan 04 còn Chờ duyệt; replay v2/stream API có thể đổi | Không sửa các module do 04 sở hữu; không public wire format quỹ đạo ở A; thống nhất trước B |
| Adapter worker và execute có hai luồng lưu kết quả | Test cùng snapshot qua CLI/service; ghi điểm tích hợp, phối hợp trích helper chung sau 04 thay vì tự refactor runs.py |
| RunSpec hiện còn policy_group và pooling để tương thích | API mới từ chối các cấu hình ngoài phạm vi; không sửa behavior/CLI cũ, không thêm policy endpoint |
| SQLite connection khác thread/process hoặc transaction claim bị race | Connection theo owner, transaction ngắn; test đồng thời với DB file, không chỉ :memory: |
| Supervisor crash để lại worker hoặc cập nhật terminal muộn | Ownership/khoá thực thi + watchdog, startup từ chối nhận run mới khi chưa xác nhận worker cũ dừng; terminal update có điều kiện |
| Engine không có callback mỗi event xử lý và MetricSampler tạo bên trong run | Listener chỉ phát dữ liệu đã có; có phase loading/running và timestamp cập nhật; không cam kết nhịp tạo metric bằng nhịp SSE; nếu cần hook engine mới thì đưa sang B, duyệt interface với 04 |
| FastAPI phiên bản mới không hỗ trợ Python cũ hoặc test isolation hiện cấm toàn bộ web import | Chọn dependency bounds tương thích, kiểm môi trường service; nới allowlist đúng kami/service, giữ test core không import web/DB và không import service |
| Thiếu phụ thuộc 05–06 | Công bố capability/giới hạn trong tài liệu A; không trả số pin/sạc/pricing giả, không nhận toàn bộ sprint đã hoàn tất |

## 8. Lịch sử thay đổi

| Ngày | Thay đổi | Người duyệt |
|---|---|---|
| 2026-10-08 | Tạo plan cho phần backend có thể làm song song 04; A dùng engine/schema hiện tại, B chờ 04/05/06. Chưa sửa code, chưa duyệt plan | — |
| 2026-10-08 | Người dùng duyệt triển khai giai đoạn A trong hội thoại; bắt đầu thực hiện | Người dùng |
| 2026-10-08 | Implement giai đoạn A; bổ sung input/locks và test migration CLI phù hợp schema mới. B còn mở, full suite còn 5 lỗi tái hiện trên HEAD | Theo phê duyệt giai đoạn A |

### Tiến độ giai đoạn A — 2026-10-08

Đã implement giai đoạn A; giữ plan Đã duyệt và sprint Đang làm, chưa nghiệm thu toàn bộ sprint.
Không sửa engine/config/replay/store/runs.py hoặc web. Module phụ bổ sung: service/input.py và service/locks.py.
Đổi assertion migration trong tests/test_cli_spec.py từ version cố định sang version migration thực có;
test db init gọi CLI bằng subprocess để SQLite handle được OS nhả trên Windows. Đây là chi tiết kiểm chứng,
không đổi CLI hoặc quyết định đã duyệt.

| Phần | Kết quả |
|---|---|
| S08-1/2 | CRUD schema hiện tại; PUT giữ id; active refs; soft delete; snapshot run bất biến |
| S08-3/4/5 | Worker spawn thật, claim một run, huỷ/join, watchdog IPC và recovery ownership |
| S08-6 | SSE progress/metric/terminal, history/IPC bounded, resync, client disconnect; snapshot xe chờ B |
| S08-7/8 | Persist summary/timeseries/event log; transaction rollback khi persist fail; metric API/compare; phân rã chờ B |
| S08-9 | Chờ replay 04, chưa có endpoint quỹ đạo tạm |
| S08-10 | 21-service-api.md, engine/README và 18 đã cập nhật; 15-cli chờ phối hợp 04 ở B |

Môi trường: Windows 11 10.0.26200, CPython 3.12.1, FastAPI 0.128.0, Uvicorn 0.40.0, httpx 0.28.1.
Test đầy đủ dùng NumPy 1.26.4 và pyarrow 25.0.1 trong .runtime/sprint08/deps (workspace, không đổi Python hệ thống).
Runner đặt PYTHONUTF8=1 và PYTHONPATH tới deps, rồi chạy đúng unittest discover.
Core Python 3.9 chỉ kiểm cú pháp AST; không có interpreter 3.9/3.10 để kiểm runtime trong môi trường này.

- **24 test tập trung pass (18,668 s):** 14 test service mới, 9 isolation và 1 migration CLI.
  Bao gồm HTTP SSE nhận metric khi còn running, CLI cùng snapshot, hai start đồng thời, huỷ ≤ 3 giây,
  kill supervisor/restart, worker exit, spawn fail, monitor fail, persist fail và rollback summary.
- **Full suite:** 181 test, 151 pass, 25 skip, 1 failure + 4 errors (88,986 s), trước khi bổ sung test rollback cuối.
  Test rollback bổ sung đã pass riêng và trong nhóm 24 test trên. Không nhận full suite đã xanh.
- **5 vấn đề full suite đều tái hiện trên HEAD 002c62c:** xuất HEAD bằng git archive, cùng deps/UTF-8/data root,
  chạy lại đúng 5 test đó, kết quả 1 failure + 4 errors. Chưa sửa CLI/benchmark/module của sprint khác:
  1. test_bench.test_suite_json_and_compare so peak_rss_mb > 1, nhưng harness trả None trên Windows.
  2. test_cli_spec.test_run_spec_with_db: CLI gọi trong tiến trình test còn giữ SQLite handle khi xoá DB tạm.
  3. test_osm_pipeline.test_hanoi_network_and_zones: thiếu data/networks/hanoi/manifest.json.
  4. test_zonal.TestTrajectoryOutputs.test_cli_out_and_store: SQLite handle CLI cũ còn mở trên Windows.
  5. test_zonal.TestHanoiPresets.test_presets_command_lists_them: assertion dùng dấu /, CLI Windows in dấu ngược.
- Quickstart và presets chạy thành công. Wheel build/install smoke pass, app mở DB mới và health trả 200;
  wheel chứa cả 0001_initial.sql và 0002_service.sql. git diff --check không có lỗi whitespace.
- AC08-1/2/5/6/7/9 đã có bằng chứng cho engine/schema hiện tại, vẫn cần nghiệm thu lại phần B.
  AC08-3/4/8 đã có kiểm chứng giai đoạn A. Chưa tick AC hoặc chuyển sprint Xong khi phụ thuộc/DoD còn mở.

### Benchmark và giới hạn số liệu

Mốc đối chiếu là HEAD 002c62c xuất riêng; không so Windows với số Linux trong backlog 03.
Case road dùng cùng data_root tuyệt đối ở hai bản để tránh B02-4 (seed theo đường dẫn);
sau căn data root, metric và số event của cả 5 case đều giống hệt.
Bản baseline đầu với thư mục data khác đã được thay case road bằng phép đo lại đúng data root;
thông tin này nằm trong trường source của JSON baseline.

| Case | Wall median HEAD (s) | Giai đoạn A (s) | Δ |
|---|---:|---:|---:|
| grid_am_peak_baseline | 1,129 | 1,196 | +6,0% |
| grid_am_peak_baseline_nots | 1,014 | 1,113 | +9,7% |
| grid_am_peak_surge | 1,092 | 1,146 | +4,9% |
| grid_pm_peak_x5 | 3,432 | 3,618 | +5,4% |
| road_example_400 | 12,655 | 13,374 | +5,7% |

Mỗi case repeat 5, router road Python. Tất cả nằm trong ngưỡng 10%; biến động tải máy vẫn có.
Không đo RSS trên Windows vì harness hiện trả None; bảng CLI hiển thị 0 không phải RAM đo được.
Không chạy hanoi_am_peak_small/quy mô cả ngày làm bằng chứng: dữ liệu Hà Nội cục bộ chưa đầy đủ,
router C++/OSM deps chưa có. Phần đó vẫn thuộc kiểm chứng 04 và tích hợp B/11.

SSE đo riêng trên case synthetic 80 xe, 1.500 request/giờ, interval wall-clock 0,01 s, 3 lần mỗi chế độ:
engine median không client SSE 0,886 s, có SSE 0,840 s; end-to-end 2,014 s và 1,972 s.
Cả 6 run cùng 6.871 event và metric giống hệt. Sai khác thời gian nằm trong nhiễu case ngắn,
không suy ra SSE làm engine nhanh hơn hoặc đã đạt PERF-4 ở quy mô GreenSM.

Bằng chứng:
[baseline Windows](../../benchmarks/results/2026-10-08-sprint08-a-windows-before.json),
[sau thay đổi](../../benchmarks/results/2026-10-08-sprint08-a-windows-after.json),
[đo SSE](../../benchmarks/results/2026-10-08-sprint08-a-service.json),
[tổng hợp verification](../../benchmarks/results/2026-10-08-sprint08-a-validation.json).

Phần tiếp theo vẫn là B theo §6: EV/pricing, replay/snapshot live, log streaming và phân rã metric.
Các vấn đề Windows/dataset nói trên được ghi nhận làm đầu vào kiểm chứng tích hợp; không tự sửa scope 04/05/06.
