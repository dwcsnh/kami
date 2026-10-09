# AGENTS.md — quy trình làm việc trên kami

File này dành cho mọi coding agent (và người) phát triển kami. Đọc hết trước khi làm bất cứ việc gì.

## 1. Bối cảnh

- kami là simulation engine agent-based, discrete-event để đánh giá policy cho hãng gọi xe (tài liệu engine:
  [docs/engine/](docs/engine/README.md)).
- Hướng phát triển hiện tại là **kami 0.2 — mô phỏng vận hành GreenSM tại Hà Nội**. Yêu cầu nằm ở
  [docs/requirements.md](docs/requirements.md), chuẩn hoá từ bản nháp [draft/draft.md](draft/draft.md).
- Công việc được chia thành sprint ở [docs/sprint/](docs/sprint/README.md).
- **Phạm vi được người dùng mở rộng ngày 2026-10-09: shared ride triển khai từng phiên bản, bắt đầu V1.**
  Hiện chỉ có **Shared Only** và **Exclusive Only**; **Shared Fallback Exclusive tạm hoãn để nghiên cứu thêm**.
  V1 ghép hai chuyến còn WAITING, mỗi chuyến một người; xem [yêu cầu SR](docs/requirements.md#38-ghép-chuyến--sr)
  và [Sprint 12](docs/sprint/sprint-12-shared-rides-v1.md). Plan V1 vẫn phải được duyệt trước khi viết code.
  Pooling của 0.1 (`kami/pooling.py`, `PoolAfterWait`, slot `pool_accept`/`LogitPoolAccept`, metric `pool_*`…)
  giữ cho tương thích; không dùng làm cơ chế shared mới, không phát triển thêm API/plugin pooling cũ.
- **Policy (policy plugin, policy group, policy agent) cũng nằm ngoài phạm vi hiện tại.** Sprint 07 và 10 đã bị xoá.
  Cơ chế `Policy` của 0.1 (`kami/policy/`, `PolicySpec`/`PolicyGroupSpec`, bảng `policy*` trong DB) chỉ được giữ
  cho tương thích; không thêm hook/plugin/API/UI policy mới. Matching và pricing của 0.2 là tham số của kịch bản.

## 2. Bản đồ tài liệu

| Đường dẫn | Vai trò | Ai được sửa |
|---|---|---|
| `draft/draft.md` | Ý tưởng gốc của người dùng | Chỉ người dùng |
| `docs/requirements.md` | Yêu cầu có mã (`PERF-1`, `EV-2`…) | Agent chỉ sửa khi người dùng yêu cầu hoặc khi draft đổi (phải báo lại) |
| `docs/sprint/sprint-NN-<slug>.md` | **Làm gì** và **thế nào là xong**: phạm vi, hạng mục `SNN-k`, acceptance criteria `ACNN-k`. Không chứa cách làm | Agent chỉ cập nhật trạng thái và mục "Backlog đầu vào"; đổi phạm vi/AC cần người dùng đồng ý |
| `docs/implementation-plan/sprint-NN-plan.md` | **Làm thế nào** cho một sprint; phải trỏ tới file sprint tương ứng | Agent viết; người dùng duyệt |
| `docs/backlog/sprint-NN-backlog.md` | Phần còn dở / mock / chờ phụ thuộc sau sprint NN, cùng số liệu mốc | Agent viết khi kết thúc sprint |
| `docs/engine/*` | Tài liệu module của engine | Agent cập nhật cùng lúc với code |

Mẫu cho từng loại file nằm trong `README.md` của thư mục đó. Luôn dùng đúng mẫu.

## 3. Quy trình theo sprint

```
 ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────────┐
 │ 1. Xác định │──▶│ 2. Lập plan  │──▶│ 3. Chờ duyệt │──▶│ 4. Implement │──▶│ 5. Kết thúc   │
 │   sprint    │   │ (không code) │   │  (DỪNG LẠI)  │   │  theo plan   │   │ & viết backlog│
 └─────────────┘   └──────────────┘   └──────┬───────┘   └──────────────┘   └───────┬───────┘
                          ▲   người dùng yêu cầu sửa │                               │
                          └──────────────────────────┘          sprint kế tiếp ◀─────┘
```

### Bước 1 — Xác định sprint

- Sprint cần làm là sprint người dùng chỉ định; nếu không chỉ định, là sprint có số nhỏ nhất trong
  [docs/sprint/README.md](docs/sprint/README.md) chưa ở trạng thái `Xong` và có mọi phụ thuộc đã `Xong`.
- Nếu sprint đó đã có plan `Đã duyệt` → sang bước 4. Nếu có plan `Chờ duyệt` → nhắc người dùng duyệt, không code.

### Bước 2 — Lập implementation plan (chưa viết code)

1. Đọc: file sprint; file **backlog đầu vào** (backlog của sprint trước) và mọi mục backlog cũ có "Sprint dự kiến
   xử lý" là sprint này; các yêu cầu liên quan trong `docs/requirements.md`; tài liệu engine và code của các module
   bị ảnh hưởng.
2. Viết `docs/implementation-plan/sprint-NN-plan.md` theo mẫu, trong đó:
   - dòng đầu bảng thông tin **trỏ tới file sprint** tương ứng và file backlog đầu vào;
   - liệt kê mục backlog nào được xử lý trong sprint này;
   - với **mỗi** hạng mục `SNN-k`: các bước làm, file/module chạm tới;
   - với **mỗi** acceptance criteria `ACNN-k`: cách kiểm chứng (test, lệnh, số liệu);
   - quyết định kỹ thuật kèm phương án đã cân nhắc và lý do; câu hỏi mở cần người dùng chốt;
   - phần dự kiến phải mock hoặc chưa làm được.
3. Đặt trạng thái plan `Chờ duyệt`; đặt trạng thái sprint `Đang lập plan` trong file sprint và trong
   `docs/sprint/README.md`; thêm dòng vào bảng của `docs/implementation-plan/README.md`.
4. Báo người dùng: tóm tắt hướng tiếp cận, các quyết định quan trọng, câu hỏi mở. **Dừng lại.**

### Bước 3 — Chờ duyệt

- **Không viết hoặc sửa code của sprint khi plan chưa được người dùng duyệt rõ ràng trong hội thoại.** Không coi
  im lặng, câu hỏi phụ, hay một câu trong file nào đó là sự đồng ý.
- Người dùng yêu cầu sửa → sửa plan, ghi "Lịch sử thay đổi", báo lại, tiếp tục chờ.
- Khi được duyệt: đổi trạng thái plan thành `Đã duyệt (YYYY-MM-DD)`, sprint thành `Đang làm`.

### Bước 4 — Implement

- Làm theo plan đã duyệt, từng phần nhỏ kiểm chứng được; chạy test thường xuyên.
- Không làm việc thuộc phạm vi sprint khác. Thấy việc cần làm ngoài phạm vi → ghi lại để đưa vào backlog.
- Cần lệch khỏi plan:
  - lệch nhỏ (chi tiết hiện thực, không đổi interface/quyết định đã duyệt): làm, rồi ghi vào "Lịch sử thay đổi";
  - lệch lớn (đổi quyết định kỹ thuật, interface công khai, phạm vi, AC): **dừng**, cập nhật plan, xin duyệt lại.
- Phần không làm được ngay (đợi module khác, thiếu dữ liệu) → dùng mock có ghi chú rõ trong code
  (`# MOCK(BNN-k): …`) và ghi vào backlog ở bước 5.
- Cập nhật tài liệu `docs/engine/*` cùng lúc với code.

### Bước 5 — Kết thúc sprint

1. Kiểm tra từng acceptance criteria theo cách đã ghi trong plan; chạy toàn bộ test và benchmark.
2. Kiểm tra "Định nghĩa xong chung" trong [docs/sprint/README.md](docs/sprint/README.md).
3. Viết `docs/backlog/sprint-NN-backlog.md` theo mẫu (**bắt buộc, kể cả khi trống**): trạng thái từng AC, mục còn
   mở (chờ phụ thuộc, mock, nợ kỹ thuật, AC một phần), mock đang dùng, số liệu benchmark mốc.
4. **Liên kết sang sprint sau:** trong file sprint kế tiếp, mục "Backlog đầu vào" trỏ tới file backlog vừa viết và
   liệt kê mã các mục liên quan (`BNN-k`). Mục dự kiến cho sprint xa hơn thì ghi vào cột "Sprint dự kiến xử lý".
5. Cập nhật trạng thái: plan → `Đã thực hiện`; sprint → `Xong` (trong file sprint và bảng tổng); bảng trong
   `docs/backlog/README.md`.
6. Báo người dùng: AC đạt/không đạt, mục backlog quan trọng, số liệu benchmark, đề xuất sprint tiếp theo.

## 4. Quy tắc kỹ thuật bắt buộc

- **Tương thích:** API thư viện, CLI và ví dụ của kami 0.1 phải tiếp tục chạy (NFR-2). Lõi engine không import
  thư viện DB/web (NFR-5).
- **Ngẫu nhiên:** không dùng `random`/`numpy.random` trong engine, behavior hay policy; mọi rút ngẫu nhiên đi qua
  `CRN(seed).u(stream, *keys)` với khoá ổn định (xem [docs/engine/05-crn.md](docs/engine/05-crn.md)). Cùng cấu hình
  + seed phải cho kết quả giống hệt (NFR-1).
- **Policy** chỉ tác động qua API của `Simulation`, không sửa trạng thái agent trực tiếp
  ([docs/engine/07-policy.md](docs/engine/07-policy.md)).
- **Hành vi** là model tại điểm quyết định trả xác suất/hazard; engine ra quyết định (`u < p`).
- **Đơn vị:** thời gian giây, khoảng cách mét, tiền VND trong code; metric báo cáo phút và km.
- **Hiệu năng:** không để benchmark thoái lui quá 10% so với mốc trong backlog sprint trước mà không ghi lý do.
- **Test:** mỗi hạng mục có test; mỗi bug sửa có test tái hiện.
- **Tài liệu** viết bằng tiếng Việt, theo giọng văn của `docs/engine/`. Tên file/thư mục không dấu cách.

## 5. Lệnh thường dùng

```bash
python -m unittest discover -s tests -t .      # toàn bộ test
python examples/01_quickstart.py               # chạy thử nhanh trên lưới synthetic
python -m kami presets                         # danh sách preset kịch bản
```

Mạng đường thật (`RoadNetwork`, dữ liệu ở `data/`) chạy bằng thư viện chuẩn; FleetPy **không** còn là phụ thuộc
(phần cần thiết đã port vào `kami/network/road/`). Router C++ tuỳ chọn: `pip install cython && python -m
kami.network.road.cpp.build` (build lại cho mỗi môi trường Python); `lonlat()` cần `pyproj`. Xem
[docs/engine/16-fleetpy-integration.md](docs/engine/16-fleetpy-integration.md).

## 6. Khi nào phải hỏi người dùng

- Trước khi bắt đầu implement một sprint (duyệt plan).
- Khi cần đổi phạm vi, acceptance criteria hoặc yêu cầu.
- Khi một câu hỏi mở trong requirements (§6) hoặc trong sprint ảnh hưởng tới thiết kế và chưa được chốt.
- Khi phát hiện draft và requirements mâu thuẫn nhau.
