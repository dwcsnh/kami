# 21 · Backend service & quản lý lần chạy (Sprint 08, giai đoạn A)

Backend HTTP ở `kami/service` là lớp ngoài engine; mọi SQL vẫn ở `kami/store`.
Plan: [sprint-08-plan.md](../implementation-plan/sprint-08-plan.md), duyệt ngày 2026-10-08.
Giai đoạn A dùng simulation thật và schema hiện có. Sprint 08 vẫn Đang làm: EV/pricing chờ 05–06;
snapshot xe, replay và event log streaming chờ tích hợp 04. Không có mock production.

## 1. Chạy service

```bash
pip install -e '.[service]'
python -m kami.service --db kami.db --artifacts runs --host 127.0.0.1 --port 8000 --interval-s 0.25
```

OpenAPI/Swagger: http://127.0.0.1:8000/docs. GET /api/v1/health trả capability giai đoạn A.
Dùng SQLite file/WAL; không hỗ trợ :memory: vì worker là tiến trình riêng. Một supervisor cho một đường dẫn DB,
instance thứ hai bị khoá OS từ chối; không bật reload hoặc nhiều API worker.

API từ chối start nếu DB có run running, nhưng không điều phối các tiến trình CLI độc lập. Muốn bảo đảm một run
trong ứng dụng, bắt đầu run qua service. CLI/thư viện 0.1 giữ hành vi cũ.

Extra service giữ core dependencies rỗng. Dependency bounds cho Python 3.9 dùng FastAPI trước 0.129 và Uvicorn
trước 0.35; Python mới hơn dùng Uvicorn trước 0.41. Phiên bản Python thực tế đã test ghi ở plan, không suy diễn
rằng mọi môi trường được khai báo hỗ trợ đều đã được chạy test.

## 2. CRUD và cấu hình

Tiền tố: /api/v1. Mỗi resource có GET/POST /resource và GET/PUT/DELETE /resource/{id}.

| Resource | Nội dung POST/PUT |
|---|---|
| vehicle-types | VehicleTypeSpec: name, group, seats, range_km |
| fleets | FleetSpec: name, composition gồm vehicle_type theo tên và count |
| charging-stations | ChargingStationSpec: name, node hoặc lon/lat, ports, power_kw |
| scenarios | RunSpec hiện tại: scenario inline, fleets, vehicle_types, charging_stations, behavior, sim_config, seed/crn_seed, outputs |

POST trả 201; PUT giữ id; DELETE xoá mềm và trả 204. Đọc trả {id, name, spec}; danh sách là mảng object đó.
Tên đang active bị trùng trả 409, dùng lại tên sau xoá được. Loại xe đang được fleet active dùng không được xoá
hoặc đổi tên. Ref số nguyên và tên đều phải trỏ tới bản active. Lịch sử Repository thư viện không bị đổi.

Scenario API là mẫu RunSpec đầy đủ: scenario.name là tên entity duy nhất; name ở gốc là nhãn run.
Bảng scenario giữ thế giới ngoại sinh; service_scenario giữ mẫu RunSpec. Scenario tạo bằng Repository/CLI cũ
chưa có mẫu service không xuất hiện trong danh sách này, nhưng vẫn dùng làm ref trong POST /runs được.

API từ chối policy_group, sim_config.pooling và behavior pool_accept; không có endpoint policy.
Baseline được chọn nội bộ theo mặc định RunSpec. Matching/pricing mới chờ schema 06.
Pin/sạc hiện được lưu cấu hình nhưng chưa tác động vào simulation; capability EV trả false.

Cấu hình sai trả 422 với errors chứa path/message, dùng chung Spec.from_dict và SpecError.
Không tồn tại/đã xoá trả 404; xung đột tên/trạng thái trả 409. Input từ chối số không hữu hạn;
metric không xác định xuất JSON null.

## 3. Vòng đời run

| Endpoint | Hành vi |
|---|---|
| POST /runs | Đúng một trong {"scenario_id": id} hoặc {"spec": RunSpec}; trả 201, queued |
| GET /runs?status=... | Danh sách, gồm lịch sử CLI; lọc trạng thái tuỳ chọn |
| GET /runs/{id} | Trạng thái, snapshot resolved/source/provenance, progress, lỗi, managed |
| POST /runs/{id}/start | Chỉ run service queued; trả 202; bận hoặc terminal trả 409 |
| POST /runs/{id}/cancel | Huỷ queued hoặc dừng/join worker running; trả trạng thái cuối |
| GET /runs/{id}/metrics | Chỉ succeeded: {run_id, summary} |
| GET /runs/{id}/timeseries | Chỉ succeeded: {run_id, rows} |
| GET /runs/{id}/artifacts | Chỉ succeeded: metadata path/format/sha256/rows; chưa có download/quỹ đạo API |
| GET /runs/compare?ids=1,2,... | 2–20 run succeeded, không trùng; run đầu là baseline |
| GET /runs/{id}/stream | SSE tiến độ, metric và terminal |

queued → running → succeeded/failed/cancelled; queued cũng có thể cancelled.
Queued không tự chạy và không phải hàng đợi tự động. Run terminal không start lại: tạo run mới.

Tạo queued giải mọi ref và kiểm dependency output trước khi ghi run. Snapshot bất biến: sửa/xoá nguồn sau đó
không đổi run đã tạo. Start dùng snapshot, không resolve lại. Snapshot resolved vẫn dùng được với
python -m kami run --spec snapshot.json; nó chứa các trường tương thích 0.1 do builder tự thêm,
trong khi API input không nhận cấu hình policy/pooling.

Claim qua transaction ngắn rồi spawn worker; không giữ transaction trong lúc simulation chạy.
Worker gọi build_run → Simulation.run → ghi summary/timeseries/artifact → commit succeeded.
Build/persist fail hoặc worker chết thành failed. API không quảng bá kết quả một phần như kết quả thành công.
File dở có thể còn ở thư mục artifact để điều tra; không có endpoint đọc file tuỳ ý.

Huỷ mục tiêu ≤ 3 giây: terminate/join, force kill nếu cần, rồi nhả slot. Race hoàn tất/huỷ giữ trạng thái
terminal đầu tiên đã commit; nếu run vừa succeeded, cancel có thể trả succeeded hoặc 409.

Shutdown dừng worker và ghi failed/error_code interrupted. Nếu supervisor bị kill, watchdog IPC trong worker
thoát và OS nhả khoá. Startup chỉ recover run service sở hữu sau khi giữ được khoá thực thi;
worker cũ chưa dừng sau 5 giây thì từ chối startup. Không recover run CLI khác, không giết PID không thuộc ownership.
Schema dùng failed + error_code, không thêm trạng thái interrupted riêng.

## 4. Progress và SSE

Progress có phase (loading/running/persisting/finished), simulation_time, scenario_end, stop_time, fraction, eta_s.
Loading chưa có thời điểm mô phỏng. Fraction tính tới stop_time gồm drain, kẹp dưới 1 khi đang chạy;
chỉ persisted succeeded có fraction = 1. ETA ngoại suy wall-clock, null khi chưa đủ tiến độ.

--interval-s là khoảng cách tối thiểu giữa các lần worker phát cập nhật theo thời gian thực, trong (0, 60].
Metric row vẫn được engine tính tại mốc thời gian mô phỏng của timeseries_interval_s (mặc định 300 giây).
Tắt sampler thì chỉ có progress/terminal. Listener không thêm event, không rút ngẫu nhiên, không đổi engine state.
Load mạng hoặc không có callback log mới có thể khiến cập nhật thưa hơn interval.

```text
event: status
data: {"run_id": 1, "status": "running", "progress": {"phase": "loading"}}

id: 12
event: metric
data: {"run_id": 1, "row": {"t": 25260, "rider.requests": 3}}

id: 13
event: progress
data: {"phase": "running", "simulation_time": 25262, "fraction": 0.1, "eta_s": 2.8}
```

Reconnect gửi Last-Event-ID không âm. History và IPC đều bounded; client chậm/mất history nhận resync
rồi đọc trạng thái/chuỗi thời gian qua API. DB là nguồn kết quả cuối, stream không cam kết giao mọi row
trong mọi điều kiện mạng. Ngắt SSE không huỷ run. Terminal kết thúc stream, có comment keepalive khi chờ.
Progress/metric chưa phải snapshot xe của replay; phần đó chờ tích hợp 04.

## 5. So sánh metric

Candidate trả metric với baseline/candidate/delta/delta_percent/direction/verdict. Delta là candidate trừ baseline;
phần trăm chia trị tuyệt đối baseline, null khi baseline = 0 hoặc thiếu số. Direction lấy từ
[11-metrics.md](11-metrics.md); verdict better/worse/equal chỉ có khi direction khác 0 và đủ số.
Metric pooling không xuất trong báo cáo API 0.2; NaN/null/thiếu không có verdict.

Warnings: different_scenario, unpaired_seed, different_fleet, different_environment nếu có metadata khác.
Đây không phải kiểm định thống kê hoặc đánh giá cặp qua nhiều seed.
Phân rã fleet/loại xe/sản phẩm chờ dữ liệu/attribution 05–06.

## 6. Ví dụ từ đầu đến cuối

Sau khi chạy server, Python thư viện chuẩn:

```python
import json
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8000/api/v1"
def post(path, data=None):
    body = json.dumps(data).encode() if data is not None else b""
    req = Request(base + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req) as response:
        return json.load(response)

post("/vehicle-types", {"name": "car", "group": "car", "seats": 4})
fleet = post("/fleets", {"name": "taxi", "composition": [{"vehicle_type": "car", "count": 20}]})
scenario = post("/scenarios", {
    "name": "demo-run",
    "scenario": {"name": "demo", "seed": 2, "source": {
        "kind": "synthetic", "t_start": 25200, "t_end": 25800, "demand_per_hour": 200}},
    "fleets": [{"ref": fleet["id"]}],
    "outputs": {"event_log": "csv.gz"},
    "sim_config": {"timeseries_interval_s": 60}
})
run = post("/runs", {"scenario_id": scenario["id"]})
post(f"/runs/{run['id']}/start")
print(run["id"])
```

Theo dõi GET /runs/{id} hoặc /stream; khi succeeded đọc metrics/timeseries.
Parquet cần extra store (pyarrow); ví dụ dùng csv.gz không cần Parquet.

## 7. Kiểm chứng

Cài extra service-test rồi chạy python -m unittest discover -s tests -t .
Test mới: test_service_entities, test_service_runs, test_service_metrics, test_service_stream.
Kiểm worker spawn thật, CLI cùng snapshot, HTTP SSE trước khi hoàn tất, disconnect, hai service,
kill supervisor, worker chết, spawn/persist fail và ownership. Isolation vẫn cấm core import DB/web/service.
Kết quả và benchmark ghi trong plan; chưa nghiệm thu toàn bộ Sprint 08 hoặc quy mô GreenSM.

## Shared V1

GET /health trả `shared_ride_versions: [1]`. Public RunSpec nhận cấu hình Shared
V1 đã validate qua parser hiện có, hai preference và cước cố định 70%; không
mở policy/pooling legacy cho API. Create queued resolve defaults vào snapshot.
Worker thật ghi shared.* vào metric_summary/metric_timeseries bằng đường persist
hiện có. API metrics, CSV và comparison đọc dữ liệu đã lưu, no-data là null.
Test test_shared_service và browser E2E kiểm SQLite/worker/snapshot sau sửa nguồn.
Xem [Shared V1](23-shared-rides-v1.md).
