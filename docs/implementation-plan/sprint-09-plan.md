# Implementation plan — Sprint 09: Giao diện Simulation manager & visualizer live

| | |
|---|---|
| Sprint | [sprint-09-ui-simulation-manager.md](../sprint/sprint-09-ui-simulation-manager.md) |
| Backlog đầu vào | [sprint-08-backlog.md](../backlog/sprint-08-backlog.md) — chưa tồn tại vì Sprint 08 mới hoàn thành giai đoạn A; đối chiếu phần còn mở trong [plan 08 §6](sprint-08-plan.md#6-mock--phần-dự-kiến-chưa-làm). Từ [sprint-03-backlog.md](../backlog/sprint-03-backlog.md): **B03-5**, **B03-9**; xem xét nhưng chưa nhận làm **B03-6**, **B03-7**, **B03-8** |
| Trạng thái | Đã duyệt (2026-10-08) |

## 1. Tóm tắt hướng tiếp cận

Người dùng yêu cầu tiếp tục Sprint 09 ngày 2026-10-08. Khảo sát trên commit 002c62c cùng working tree đã
implement Sprint 08 giai đoạn A: Next.js/React/TypeScript, Mapbox + deck.gl, ECharts, Zustand và design tokens
của Sprint 03 đã có; backend FastAPI + SQLite cung cấp CRUD, run lifecycle, summary/timeseries, compare và
SSE progress/metric. Sprint 04 còn Đang lập plan; Sprint 08 vẫn Đang làm; chưa có API quỹ đạo hoặc snapshot xe live.

Đề xuất hai giai đoạn, giữ nguyên toàn bộ phạm vi và acceptance criteria của sprint.
Theo yêu cầu người dùng ngày 2026-10-08, **tạm hoãn toàn bộ UI trạm sạc khỏi giai đoạn A**: không có tab/form
CRUD trạm hoặc control chọn trạm trong kịch bản. Phần này chuyển sang B khi người dùng yêu cầu tiếp tục.
API/schema/dữ liệu trạm sạc của Sprint 08 giữ nguyên; kịch bản mới không thêm trạm, mẫu đã có
charging_stations giữ nguyên trường đó khi sửa các phần khác, không tự xoá dữ liệu.

Kế hoạch hai giai đoạn:

- **Giai đoạn A — làm ngay sau khi duyệt:** khung điều hướng, UI CRUD loại xe/fleet/kịch bản theo schema hiện có, tạo/chạy/huỷ và
  theo dõi run thật, metric tổng hợp/chuỗi thời gian/so sánh/xuất CSV; ghép visualizer fixture hiện có vào khung.
  Người dùng thao tác bằng form, không phải viết JSON hoặc chạy CLI để tạo cấu hình/chạy mô phỏng.
- **Giai đoạn B — chờ phụ thuộc và ưu tiên tiếp theo:** UI trạm sạc khi người dùng yêu cầu tiếp tục; form fleet/EV/sản phẩm/ca và matching/pricing mới; metric phân rã; xe/vệt
  chạy live, phát lại qua API, bộ lọc bản đồ và khách đang chờ; đo PERF-4 với visualizer live thật.
  Đọc backlog 08 chính thức, interface replay 04 và schema 05–06 trước khi bổ sung chi tiết và xin duyệt B.

**Duyệt plan này là duyệt triển khai A trước khi Sprint 08 kết thúc.** Phụ thuộc 03/08 giữ nguyên; không đánh dấu
toàn bộ sprint Xong sau A. API hiện tại không đủ để nghiệm thu AC09-8/9/10/11. Metric live qua SSE không đồng
nghĩa với xe di chuyển live trên bản đồ; fixture demo luôn được ghi nhãn rõ.

Backlog được tiếp nhận:

| Mã | Xử lý trong plan |
|---|---|
| B03-5 | A: chạy audit lại, ghi kết quả theo lockfile thực tế; sửa bản vá tương thích nếu có và kiểm tra lại build/test. Không tự hạ major deck.gl hoặc thay renderer; khi chưa có bản vá tương thích, giữ mục mở và ghi rõ bằng chứng |
| B03-9 | A: thêm E2E tự động cho UI manager với backend/worker thật; B: mở rộng tương tác bản đồ live/replay khi có hợp đồng. Không coi manager E2E là đã xử lý toàn bộ tương tác bản đồ |
| B03-6 | Mũi tên xe: chưa nhận làm; là ý tưởng, chạm renderer do 04 đang phụ trách |
| B03-7 | KPI trung bình trượt: chưa nhận làm; giữ định nghĩa metric hiện tại, cần chốt định nghĩa riêng nếu muốn thay |
| B03-8 | Dark mode: chưa nhận làm; nghiệm thu light mode theo Sprint 03 |
| B08-1/2/3/4 dự kiến | Không phải backlog chính thức; giữ theo dõi tại plan 08. UI tương ứng chờ B, không đổi mã hoặc đóng các mục này trong A |

Không sửa các thay đổi có sẵn ở .gitignore, web/.gitignore, web/scripts/build-tokens.mjs; không ghi đè sản phẩm
Sprint 08 vừa làm hoặc các file replay/renderer do Sprint 04 dự kiến sửa.

## 2. Quyết định kỹ thuật

| Mã | Lựa chọn | Phương án đã cân nhắc và lý do |
|---|---|---|
| D1 | Giữ Next.js App Router, React, TypeScript strict, Zustand, CSS Modules và ECharts. Theo yêu cầu rõ ràng ngày 2026-10-09, bổ sung Tailwind v4 và toàn bộ component shadcn (Radix); dùng Dialog/Select/Switch/Skeleton cho UI A | Thay thế quyết định ban đầu không thêm thư viện UI theo chỉ đạo mới của người dùng. Không đổi renderer/state/chart/API; source shadcn được lưu tại web/src/components/ui, CLI chạy bằng npx và không là dependency runtime |
| D2 | Next.js chạy dưới dạng server ở dev và production; proxy /api/v1/:path* tới backend qua rewrites trong next.config.mjs. Biến server KAMI_SERVICE_URL mặc định http://127.0.0.1:8000, chỉ cấu hình origin cố định; trình duyệt luôn dùng đường dẫn /api/v1 | Giữ static export + gọi chéo origin cần thay CORS backend; proxy cùng origin nối được HTTP/SSE mà không sửa public API, service hoặc engine của 08. Bỏ output: export; npm start chuyển từ serve out sang next start. Đây là thay đổi cách chạy frontend cần người dùng duyệt trong plan này |
| D3 | Bốn route /scenarios, /fleets, /metrics, /visualizer; giữ / là lối vào visualizer tương thích và giữ query replay/t/view/palette hiện có. /ui tiếp tục mở gallery | Redirect / có thể làm mất link fixture/script đo FPS hiện có; không đổi data loader của 03/04 trong A |
| D4 | AppShell/RunProvider dùng chung giữa các trang; một nơi đọc health/runs, phát hiện running qua polling khoảng 2 giây, lấy detail và mở một EventSource cho run active | Mỗi trang tự poll/stream gây trùng kết nối và trạng thái bận lệch nhau. DB/backend quyết định running; nút UI khoá không thay cho kiểm tra 409 phía service |
| D5 | SSE xử lý status/progress/metric/resync/terminal; đóng kết nối khi đổi run/unmount/terminal, reconnect theo EventSource; fallback đọc detail khi lỗi | Dữ liệu SSE tạm thời có thể mất; lúc resync chỉ đọc detail khi running và ghi rõ khoảng thiếu metric, vì timeseries API hiện chỉ đọc được sau succeeded. Buffer live tối đa 2.000 hàng, hiển thị rõ cửa sổ đang xem. Khi succeeded tải lại summary/timeseries từ DB. Không điền 0 hoặc nội suy hàng metric bị mất |
| D6 | Typed API client và kiểu DTO ở web/src/manager, tách khỏi web/src/data để tránh conflict 04; validation cuối do API, client kiểm trường bắt buộc và đơn vị cơ bản | Copy toàn bộ Python validator sang TypeScript dễ lệch luật. Hiện lỗi 422 có path/message; map tới field và bảng lỗi chung, giữ nguyên bản nháp sau lỗi |
| D7 | Entity và cấu hình đã lưu lấy từ API; form giữ state cục bộ, không dùng localStorage thay DB. Sau save/delete/run action tải lại dữ liệu liên quan | Dùng browser storage làm nguồn dữ liệu vi phạm AC09-2. Các lần reload trong E2E phải chứng minh dữ liệu đến từ DB |
| D8 | UI A chỉ gửi trường schema hiện có; preset/synthetic/zonal, bản đồ grid/road, zone square/H3/file và fleet refs đều có form. Có nhóm thời tiết/sự cố theo các trường đang được hỗ trợ. Form giữ nguyên phần hợp lệ chưa có control khi sửa mẫu đã lưu; không âm thầm thay CSV/fleetpy source hoặc inline fleet thành cấu hình khác | Một textarea JSON duy nhất không đáp ứng thao tác không code. Các mẫu nguồn đặc biệt hiển thị tóm tắt và giới hạn chỉnh sửa rõ ràng; đổi loại nguồn có xác nhận. Không nâng schema hoặc tự thêm cấu hình policy để lách thiếu matching/pricing |
| D9 | A cho cấu hình loại xe name/group/seats/range_km và fleet name/composition; tạm hoãn UI trạm sạc và chọn trạm trong scenario theo yêu cầu người dùng. Ghi rõ range mới là cấu hình, EV chưa tác động vào engine. Không xoá API/schema/dữ liệu charging_stations đã có. Form sản phẩm, pin, ca, matching/pricing v2 chờ capability B | Nhận trường engine chưa có rồi giả tác dụng làm kết quả mô phỏng gây hiểu nhầm; phần trạm sạc sẽ tiếp tục khi người dùng yêu cầu, không bỏ khỏi AC toàn sprint |
| D10 | Metric dùng đúng key, đơn vị và null của API; so sánh dùng delta/direction/verdict/warnings từ API, không tính lại quy tắc tốt/xấu hoặc CRN ở trình duyệt | Hai định nghĩa khác nhau dễ đảo chiều kết luận; thiếu số hiển thị dấu —, baseline 0 giữ phần trăm null. Không đưa metric pooling/policy lên UI mới |
| D11 | CSV xuất ở trình duyệt từ dữ liệu API: summary, timeseries và comparison; UTF-8, escape dấu phẩy/ngoặc kép/xuống dòng, giữ giá trị số gốc, null để trống | Chưa cần endpoint export mới. Nội dung tên/nhãn bắt đầu bằng ký tự công thức được xuất thành văn bản để mở bảng tính đúng; không xuất số đã làm tròn trên màn hình |
| D12 | Giữ visualizer như module độc lập, ghép qua wrapper có kích thước/containing block riêng; không sửa ReplaySource, map layers/frame hoặc playback algorithm ở A | Visualizer hiện position: fixed/inset: 0; wrapper cần thử containing block và stacking để không che điều hướng/chỉ báo. Nếu wrapper không đủ thì chỉ sửa bố cục CSS với thay đổi tối thiểu, không chạm renderer hoặc wire format |
| D13 | E2E qua playwright-core hiện có và Chrome hệ thống, script Node dùng assert; service SQLite file và worker spawn thật, DB/artifacts riêng trong thư mục tạm | Không cần thêm framework/browser download. Test double chỉ dùng tái hiện lỗi, không thay cho hành trình DB/worker thật. E2E manager chạy được khi không có token Mapbox |
| D14 | Timestamp cập nhật scenario chưa có trong entity DTO; lịch sử run cần detail để biết scenario_id. A không suy ra timestamp từ giờ của client; hiện — với chú thích khi chưa có dữ liệu. Lịch sử ghép theo scenario_id/provenance của detail, tải giới hạn đồng thời và cache | Danh sách entity hiện chỉ có id/name/spec, list_runs không có scenario_id/progress. Không ghép bằng tên vì rename tạo kết quả sai; metadata/pagination cần phối hợp bổ sung backend ở B, không tự mở rộng API 08 trong A |

**Các điểm cần người dùng duyệt để bắt đầu A:** triển khai phần manager trước khi 08 hoàn tất; frontend cần
Next.js server thay static export để proxy cùng origin; visualizer A tiếp tục là demo fixture có nhãn, chưa phải
live/replay từ DB.

**Câu hỏi chặn B nhưng không chặn A:** requirements Q1 vẫn chưa chốt hệ số PERF-4 (giả định ≥ 60×).
Trước S09-12 cần người dùng chốt hệ số và môi trường/quy mô đo; không coi duyệt A là chốt Q1.
Không cần chốt màu A/B, KPI trượt, dark mode hoặc thông số xe thật để làm manager theo schema hiện tại.

## 3. Thay đổi theo module

Các đường dẫn dưới đây là dự kiến cho A; có thể tách file nhỏ hơn nhưng giữ ranh giới trách nhiệm.

| File/module | Thay đổi |
|---|---|
| web/next.config.mjs, web/package.json, web/.env.example | Proxy API, biến server origin, lệnh production/E2E; giữ token Mapbox hiện có, không đọc hoặc ghi giá trị .env.local |
| web/src/app/layout.tsx, globals.css | Gắn AppShell/provider; metadata manager và bố cục trang, giữ font/tokens |
| web/src/app/scenarios/page.tsx, fleets/page.tsx, metrics/page.tsx, visualizer/page.tsx (mới) | Entry route cho ba trang quản lý và wrapper visualizer; chọn run qua query ?run=<id>, comparison qua query ids, không cần dynamic route phía server |
| web/src/app/page.tsx, VisualizerClient.tsx | Giữ alias visualizer ở / và query fixture cũ; kết nối wrapper chung nếu cần |
| web/src/manager/api.ts, types.ts, runStore.ts, RunProvider.tsx (mới) | Typed CRUD/run/metric client, lỗi API, capability, polling/SSE và cache detail; tách khỏi loader replay |
| web/src/manager/AppShell.tsx, manager.module.css, components/* (mới) | Điều hướng, chỉ báo run, trường form/bảng/dialog xoá, loading/error/empty, focus/keyboard |
| web/src/manager/ScenariosPage.tsx, scenarioForm.ts, ScenarioForm.tsx (mới) | CRUD mẫu RunSpec, chọn nhiều fleet, lịch sử, queued/start/cancel, bảo toàn bản nháp và phần spec chưa có control |
| web/src/manager/FleetsPage.tsx, EntityForms.tsx (mới) | CRUD loại xe/fleet, thao tác thành phần nhiều dòng, validation theo path |
| web/src/manager/MetricsPage.tsx, metricFormat.ts, csv.ts (mới) | Chọn run, summary, ECharts timeseries, compare ≥ 2 run, cảnh báo và CSV; dùng lại Chart hiện có |
| web/src/manager/VisualizerPage.tsx (mới) | Mở fixture demo trong khung; nếu nhận run id thì hiển thị trạng thái/metric của run và giải thích chưa có dữ liệu bản đồ live/API. Không hiển thị xe fixture dưới nhãn của run thật |
| web/src/manager/*.test.ts, web/scripts/manager-e2e.mjs, manager-test-host.py (mới) | Unit test hành vi chuyển dữ liệu/CSV/lifecycle và E2E thật; host chỉ là công cụ kiểm thử |
| docs/engine/22-ui-guide.md, docs/engine/img/manager/* (mới); 20-visualizer.md, engine/README.md | Cách khởi động, thao tác, lưu DB, giới hạn A, ảnh 1280/1440, đường dẫn visualizer cũ/mới và vận hành frontend mới |
| web/package-lock.json | Chỉ thay nếu audit tìm được bản vá tương thích đã kiểm chứng; không cập nhật phụ thuộc hàng loạt |
| docs/implementation-plan/sprint-09-plan.md, docs/sprint/README.md, sprint-09-ui-simulation-manager.md | Cập nhật tiến độ và bằng chứng; chỉ kết thúc/backlog theo quy trình khi đủ điều kiện |

A không sửa kami/core, kami/config, kami/matching.py, kami/pricing.py, kami/trajectory.py, kami/replay,
kami/store, kami/service, web/src/data, web/src/map hoặc wire format của Sprint 04. Trường hợp phát hiện API thiếu
ngoài các giới hạn đã nêu: ghi vào phần chờ B, không tự đổi interface trong sprint UI.

## 4. Kế hoạch theo hạng mục

Thứ tự thực hiện A: transport/client → shell/run state → fleet → scenario/run → metric/CSV → visualizer wrapper
→ E2E/tài liệu. Mỗi phần kiểm chứng được trước khi nối phần sau.

| Hạng mục | Giai đoạn A: các bước và file/module | Phần B hoặc phụ thuộc |
|---|---|---|
| S09-1 | 1. Cấu hình proxy và kiểm CRUD/SSE xuyên Next. 2. Tạo AppShell/RunProvider với 4 liên kết. 3. Poll phát hiện running ở client khác, đọc detail, stream progress; hiện tên scenario từ snapshot, phase/fraction/ETA hoặc chưa xác định; liên kết mở run. 4. Kiểm 409 và trạng thái service mất kết nối | B giữ khung, bổ sung dữ liệu bản đồ/capability mới; không bỏ chỉ báo khi chưa xác nhận run đã kết thúc |
| S09-2 | 1. Danh sách template + trạng thái/run gần nhất qua detail. 2. Form tên, network/zones/source, khung giờ/demand, weather/incidents, nhiều fleet, seed/crn_seed và nhịp metric; mặc định event_log csv.gz để demo không bắt buộc pyarrow. 3. Giữ đầy đủ nội dung gốc khi sửa; không loại bỏ trường vì UI chưa hiểu. 4. Save → POST runs scenario_id → start; giữ run queued nếu start 409 để retry, không tạo run lặp. 5. Huỷ và lịch sử; khoá chạy khi bận hoặc chưa xác định trạng thái backend | Matching/pricing 0.2 chờ 06/08 B; timestamp cập nhật chờ DTO. Nguồn CSV/fleetpy đã lưu giữ nguyên, chưa có bộ editor đầy đủ trong A |
| S09-3 | 1. Tab loại xe/fleet và CRUD thật. 2. Fleet composition chọn vehicle type + count, thêm/xoá dòng. 3. Hiển thị lỗi trùng tên, ref không còn và loại xe đang được dùng; xác nhận trước DELETE | UI CRUD trạm sạc tạm hoãn theo yêu cầu người dùng, tiếp tục ở B khi được yêu cầu. Sản phẩm, phân bố ban đầu, ca và pin/sạc đầy đủ chờ 05/08 B. Không giả số SOC hoặc tính năng EV |
| S09-5 | 1. Danh sách run theo trạng thái. 2. Run succeeded đọc summary/timeseries; running đọc metric SSE có nhãn tạm thời. 3. Biểu đồ chọn metric, giữ thời gian/đơn vị đúng. 4. Chọn baseline + 1–19 candidate, gọi compare, hiện delta/%/verdict và mọi warning theo candidate. 5. CSV cho ba loại kết quả, nút tải bị khoá khi dữ liệu chưa có | Phân rã zone/fleet/loại xe/sản phẩm chờ B08-4 dự kiến; không suy ra phân rã từ tổng |
| S09-6 | 1. Loading/empty/offline/404/409/422/5xx ở mọi trang. 2. Draft state tồn tại khi submit lỗi, lỗi field và focus bảng lỗi. 3. Dialog xoá có tên, huỷ không gửi DELETE. 4. Không bật run action dựa trên trạng thái cache đã mất kết nối; refresh và retry rõ ràng. 5. Test đổi run nhanh không bị response cũ ghi đè, không subscribe trùng sau navigation | B áp dụng cùng chuẩn cho stream/chunk/snapshot và thiếu dữ liệu bản đồ |
| S09-7 | Viết 22-ui-guide.md cùng implementation; ảnh scenario/fleet/metrics/shell + fixture visualizer; hướng dẫn backend/Next, env proxy, vị trí DB/artifacts, run lifecycle và giới hạn A | B thêm ảnh live/replay thật, filter/khách chờ, kết quả PERF-4 |
| S09-8 | Wrapper visualizer hiện có trong khung, vẫn giữ entry /; mở ?run=id từ history/banner vào thông tin đúng run. Khi chưa có map data của run, hiện trạng thái/metric và thông báo rõ, kèm liên kết riêng tới demo | B mở bản đồ run từ API, chỉ khi contract S08-6/S08-9 sẵn sàng |
| S09-9 | A nối SSE progress/metric cho manager, không tạo snapshot xe giả hoặc lái playback fixture theo thời gian run thật | B bổ sung source live theo snapshot/vệt chính thức 08, cập nhật map không qua render React mỗi xe; terminal cho phép chuyển replay |
| S09-10 | A giữ static fixture như demo, không biến path artifact trên đĩa thành URL trình duyệt | B ApiReplaySource theo hợp đồng 04/08 đã duyệt, tải chunk/seek, lỗi chunk/schema rõ ràng và kiểm các mốc thời gian |
| S09-11 | Chưa thêm bộ lọc bản đồ trong A để tránh sửa map/data đang thuộc 04 | B fleet/type/product ở live và replay; lớp khách chờ từ dữ liệu đúng; đối chiếu đếm và màu/đơn vị thời gian |
| S09-12 | A chỉ đo overhead transport/metric UI nhỏ để tìm lỗi và giữ benchmark engine; không dùng số đo này kết luận PERF-4 | B sau chốt Q1: cùng case/quy mô/môi trường, đo tắt/bật snapshot+metric+visualizer thật, wall/CPU/RAM, hệ số thời gian thực, payload và FPS |

## 5. Kiểm chứng acceptance criteria

| AC | Cách kiểm chứng | Giới hạn sau A |
|---|---|---|
| AC09-1 | E2E trình duyệt: tạo loại xe → fleet → scenario với fleet đã chọn → chạy → succeeded → xem summary/chart; mọi cấu hình/run tạo qua UI, kiểm lại bằng API/DB snapshot. Không nhập JSON hoặc chạy CLI để tạo dữ liệu | Một phần: UI trạm sạc được tạm hoãn; giữ AC09-1 nguyên bản, bổ sung bước tạo/chọn trạm và nghiệm thu EV/pricing ở B |
| AC09-2 | Sau mỗi loại CRUD, reload trang và so nội dung; restart service trên cùng DB rồi reload, kiểm entity/run/metric còn nguyên. Sửa template/fleet sau run và chứng minh snapshot run cũ không đổi; không dùng mock hoặc localStorage để dựng kết quả | Có thể kiểm phần A; lặp lại với schema B |
| AC09-5 | Run đủ dài trên worker thật; chuyển qua 4 trang đều có cùng run/progress, nút start khác bị khoá. Client thứ hai/start race trả 409 và UI giữ draft/run queued. Huỷ từ UI, chỉ báo kết thúc sau trạng thái terminal xác nhận | Có thể kiểm ở A |
| AC09-6 | Tạo/chạy hai run thật, chọn baseline/candidate, so từng delta/verdict/warning hiển thị với response compare; seed khác sinh unpaired_seed, scenario khác sinh different_scenario. Unit test null/0/giá trị âm và màu không thay nhãn chữ | Có thể kiểm ở A |
| AC09-8 | A kiểm SSE metric/progress trước terminal và summary sau terminal khớp DB; B mở run đang chạy, kiểm xe/vệt tại mốc stream và metric bằng API/event data | A chưa đạt phần xe/vệt; không tick AC09-8 |
| AC09-9 | B tạo run có replay chính thức, mở qua API và chặn request /fixtures; phát hết, seek đầu/giữa/cuối/ranh giới chunk đối chiếu Python query/contract | Chờ API quỹ đạo, chưa đạt ở A |
| AC09-10 | B test fleet/type ở cả live/replay bằng tập dữ liệu có ≥ 2 fleet/loại xe; hiển thị đúng tập id/count và không vẽ xe/vệt bị lọc | Chờ B; product và khách chờ kiểm thêm theo S09-11 |
| AC09-11 | Sau khi Q1 chốt, benchmark có/không live trên cùng snapshot/seed/router/solver; metric/số event bằng nhau, hệ số thời gian thực đạt ngưỡng được duyệt khi browser thực sự nhận và vẽ xe/metric | Chờ B và chốt Q1; benchmark SSE A của 08 không thay thế |
| AC09-7 | E2E và ảnh 1280×800, 1440×900: từng trang, bảng so sánh nhiều cột, dialog/form dài, chỉ báo run, fixture visualizer. Kiểm nav không bị fixed map che, không tràn ngang toàn trang; bảng riêng được cuộn. Kiểm keyboard, nhãn control/focus, tương phản tokens | Kiểm phần A; mở rộng màn hình live B |

### Bộ test và lệnh dự kiến

Unit test manager: API error mapping; form → DTO và round-trip không mất trường; chuyển giờ phút ↔ giây,
tọa độ/khoảng giá trị; giữ queued id sau start fail; lifecycle/SSE terminal-resync và response cũ; định dạng
metric/null, warnings và CSV có dấu phẩy/ngoặc kép/xuống dòng/Unicode/công thức.

    cd web
    npm test
    npm run typecheck
    npm run build
    npm run test:manager-e2e

test:manager-e2e là script dự kiến thêm: tạo DB/artifacts tạm, khởi động service/Next trên port test được cấu hình,
dùng Chrome hệ thống (biến CHROME nếu cần), chạy hành trình UI với worker thật, ghi ảnh/bằng chứng,
dừng tiến trình do test sở hữu trong finally. Không dùng DB người dùng; không dựa vào token Mapbox để pass
hành trình manager. Chạy smoke production bằng next start sau build để kiểm proxy/SSE ngoài dev.

Các nhánh lỗi bổ sung: backend tắt/kết nối lại, lỗi validation và conflict giữ form, xác nhận xoá/huỷ dialog,
refresh đang chạy, service restart khi terminal, client SSE disconnect rồi reconnect, chuyển trang liên tục,
run failed/cancelled không hiển thị metric hoàn chỉnh; so CSV với giá trị API chưa làm tròn.

Kiểm hồi quy:

    python -m unittest discover -s tests -t .
    python examples/01_quickstart.py
    python -m kami presets
    python -m kami bench --repeat 5 --cases grid_am_peak_baseline,grid_am_peak_baseline_nots,grid_am_peak_surge,grid_pm_peak_x5,road_example_400 --compare benchmarks/results/2026-10-08-sprint08-a-windows-after.json --out benchmarks/results/<ngay>-sprint09-a-windows.json

Chạy benchmark trong cùng môi trường/data root với mốc 08; cố định 5 case của mốc, ghi case được chọn/skip,
so events và metric trước khi kết luận wall median không thoái lui > 10%. Case Hà Nội/quy mô thành phố chỉ
nghiệm thu khi đủ mạng và phụ thuộc 04. Không so trực tiếp số Windows/Python router với mốc Linux/C++ của 03.

Full suite ở 08 có 5 lỗi đã tái hiện trên HEAD (benchmark RSS trên Windows, handle SQLite CLI cũ, thiếu manifest
Hà Nội và dấu phân cách đường dẫn). Chạy lại và phân biệt hồi quy mới; không tự coi suite là xanh hoặc sửa engine/
CLI/benchmark thuộc sprint khác. Bằng chứng gốc:
[validation 08](../../benchmarks/results/2026-10-08-sprint08-a-validation.json).
Nếu còn lỗi thì DoD toàn sprint chưa đạt.

npm audit: ghi bản hiện tại và thay đổi tương thích thực sự đã kiểm; số lượng 13 trong B03-5 là mốc cũ, không
coi là kết quả hiện tại. Không chạy audit fix --force hoặc đổi major renderer để xoá cảnh báo.

## 6. Mock & phần dự kiến chưa làm

Không dự kiến mock production. Fixture visualizer là demo riêng của Sprint 03, luôn ghi nhãn; không hiển thị
như xe của một run trong DB. Test double chỉ dùng nhánh lỗi, các bằng chứng persistence/run/compare dùng thật.

Các mã dưới đây chỉ là **dự kiến** nếu còn mở khi kết thúc sprint; chưa tạo backlog cuối sprint hoặc đổi trạng thái
backlog gốc khi mới lập plan.

| Mã dự kiến | Phần còn mở | Điều kiện xử lý |
|---|---|---|
| B09-1 | Form fleet/EV/sản phẩm/ca và matching/pricing đầy đủ | Schema/engine 05–06 và API 08 B hoàn tất |
| B09-2 | Bản đồ live và replay qua API, chuyển live → replay | Contract 04/08 được duyệt và implement; S09-9/S09-10 |
| B09-3 | Bộ lọc fleet/type/product và lớp khách chờ | Dữ liệu attribution/snapshot/event đủ; S09-11 |
| B09-4 | Metric phân rã zone/fleet/type/product | B08-4 dự kiến và quy tắc aggregation chính thức |
| B09-5 | PERF-4 nghiệm thu đầy đủ | Người dùng chốt Q1, đủ dữ liệu/quy mô và live renderer |
| B09-6 | Timestamp scenario, run list liên kết scenario và pagination từ API | Phối hợp 08 B; A không giả timestamp, lấy detail có cache/giới hạn đồng thời |
| B09-7 | UI CRUD trạm sạc và chọn trạm trong kịch bản | Người dùng tạm hoãn khỏi A; tiếp tục khi có yêu cầu. API/schema/dữ liệu hiện có giữ nguyên; AC09-1 chỉ đạt một phần cho tới khi bổ sung kiểm thử trạm |
| B03-5/B03-9 | Phần audit hoặc E2E bản đồ chưa xử lý được | Giữ mã gốc và bằng chứng, không tạo mã thay thế |

Khi A xong: plan giữ Đã duyệt, sprint Đang làm; ghi bằng chứng và AC đạt một phần tại plan này.
Khi mọi phần đủ phụ thuộc và DoD: viết docs/backlog/sprint-09-backlog.md đúng mẫu (kể cả trống), cập nhật backlog
gốc thực sự được xử lý, liên kết mục liên quan sang Sprint 11 (sprint tiếp theo còn tồn tại, 10 đã xoá),
đổi plan Đã thực hiện/sprint Xong theo AGENTS.md.

## 7. Rủi ro & phương án dự phòng

| Rủi ro | Xử lý |
|---|---|
| 08 chưa kết thúc, replay v2 của 04 có thể thay toàn bộ loader | A giữ code manager ở thư mục riêng, không đoán contract; B phải đọc backlog và xin duyệt cập nhật |
| Next bỏ static export làm lệnh triển khai cũ thay đổi | Nêu rõ D2, cập nhật script/hướng dẫn và kiểm cả dev/production; không xoá fixture hoặc thay token |
| Proxy có thể buffer SSE hoặc đóng kết nối | Integration test xuyên Next phải nhận metric trước terminal. Nếu rewrites không đạt, dừng phần transport và cập nhật plan cho route streaming proxy, xin duyệt thay đổi nếu interface/cách vận hành đổi lớn |
| Visualizer fixed toàn viewport che shell | Thử wrapper tạo containing block và height rõ ràng; kiểm resize/map controls tại 1280/1440. Chỉ sửa layout tối thiểu nếu cần, giữ frame/layers nguyên |
| List runs thiếu scenario/progress, nhiều detail request | Poll danh sách một nơi, chỉ fetch running detail thường xuyên, history cache và giới hạn đồng thời. Không ghép tên; metadata/pagination đưa B |
| Cache/stream mất kết nối khiến UI báo rảnh sai | Hiện trạng thái chưa xác định/mất kết nối và khoá start cho tới lần xác nhận mới; vẫn xử lý 409/queued retry phía backend |
| Resync khi run đang chạy không truy được rows đã mất | Giữ marker dữ liệu live thiếu; chỉ tải timeseries đầy đủ khi succeeded, không quảng bá live chart là kết quả cuối |
| Form sửa mẫu chứa inline entities/nguồn đặc biệt làm mất cấu hình | Round-trip test bằng các template thực; giữ phần gốc, tóm tắt trường chưa có editor và không silently convert. Đổi loại nguồn hoặc bỏ inline entity cần thao tác rõ ràng |
| Thiếu Chrome/token hoặc mạng tải font/Mapbox | Manager E2E không phụ thuộc Mapbox; nêu môi trường cụ thể, không coi screenshot thiếu bản đồ là bằng chứng live/perf. Build font giữ cơ chế hiện có, ghi thiếu môi trường nếu bị chặn |
| Full Python suite còn lỗi nền trên Windows | Đối chiếu evidence 08/HEAD; giữ danh sách mở, không tick DoD toàn sprint khi còn lỗi |
| Bản vá dependency gây thay đổi visualizer | Chỉ nhận cập nhật tương thích đã qua test/typecheck/build/fixture smoke; đổi major/renderer là thay đổi lớn cần duyệt lại |

## 8. Lịch sử thay đổi

| Ngày | Thay đổi | Căn cứ |
|---|---|---|
| 2026-10-08 | Lập plan lần đầu: đề xuất A dùng backend hiện có, B chờ API/schema; ghi rõ đổi cách chạy Next và giới hạn nghiệm thu | Người dùng yêu cầu tiếp tục Sprint 09; chưa duyệt plan 09 |
| 2026-10-08 | Tạm hoãn UI CRUD trạm sạc và chọn trạm trong scenario khỏi A; cập nhật module, S09-2/3, kiểm chứng AC09-1 và mục chờ B09-7. Giữ API/dữ liệu của 08 và AC sprint nguyên bản; plan vẫn Chờ duyệt | Người dùng: “Tạm thời bỏ phần trạm sạc đi nhé” |
| 2026-10-08 | Người dùng duyệt triển khai giai đoạn A đã hoãn UI trạm sạc; bắt đầu implement | Người dùng trong hội thoại |
| 2026-10-09 | Hoàn thành manager giai đoạn A, kiểm chứng production và ghi bằng chứng tại §9; giữ plan Đã duyệt/sprint Đang làm | Phạm vi A được duyệt trong hội thoại; B chưa đủ phụ thuộc |
| 2026-10-09 | Tách helper thành scenarioDraft.ts để tránh trùng tên ScenarioForm.tsx trên Windows; state thuần ở runState.ts, form entity nằm cùng FleetsPage, kết quả run dùng RunResults chung. Host E2E dừng bằng stop-file để không cản worker spawn | Chi tiết hiện thực nhỏ, giữ interface và quyết định kỹ thuật đã duyệt |
| 2026-10-09 | Bổ sung loading/skeleton chung, chuyển mọi form editor sang modal, thay dropdown native và switch bằng shadcn; cài đầy đủ registry và Tailwind, cập nhật D1 theo yêu cầu người dùng | Người dùng yêu cầu rõ ràng implement và cài toàn bộ shadcn trong hội thoại; giữ nguyên AC/phạm vi A/API |
| 2026-10-09 | Cải thiện UI A bằng skill ui-ux-pro-max theo yêu cầu người dùng: sidebar, phân cấp thông tin, tìm kiếm kịch bản/đội xe, tổng quan từ API, điều hướng nhóm form, nhãn chỉ số tiếng Việt, responsive và keyboard. Giữ stack, tokens chung, API và AC; bổ sung ảnh và kiểm thử trình duyệt | Người dùng yêu cầu tái thiết kế và implement theo Green SM; đây là chi tiết UI trong S09-1/2/3/6/7 và AC09-7, không đổi quyết định D1–D14 |

## 9. Kết quả giai đoạn A — 2026-10-09

Đã implement CRUD loại xe/fleet/kịch bản, form cấu hình và bảo toàn trường chưa có editor; run queued/start/cancel,
chỉ báo dùng chung và SSE metric/progress; summary/timeseries/chart/compare/CSV; wrapper demo visualizer.
Các route /scenarios, /fleets, /metrics, /visualizer và alias / hoạt động với API thật.
Không có mock dữ liệu manager production; không dùng localStorage thay SQLite.
UI trạm sạc vẫn tạm hoãn. Không sửa service/store/engine/replay hoặc renderer thuộc Sprint 04 trong phần 09.
Các thay đổi Sprint 08 và .gitignore/script token có trước được giữ nguyên.

Bằng chứng tổng hợp: [validation 09 A](../../benchmarks/results/2026-10-09-sprint09-a-validation.json).
Hướng dẫn và ảnh: [22-ui-guide.md](../engine/22-ui-guide.md).
Log chi tiết ở .runtime/sprint09 (không commit); E2E có thể chạy lại bằng npm run test:manager-e2e.
Sau E2E, production build đã được tạo lại với backend http://127.0.0.1:8000, không để origin test 8099 trong build bàn giao.

### 9.1. AC và phần còn mở

| AC | Kết quả kiểm chứng A | Trạng thái toàn sprint |
|---|---|---|
| AC09-1 | E2E tạo loại xe → fleet → kịch bản → worker succeeded → summary/chart/CSV hoàn toàn qua form; đối chiếu snapshot/API | Một phần; trạm sạc đang hoãn, EV/pricing đầy đủ chờ B |
| AC09-2 | CRUD/reload/restart service trên cùng SQLite giữ dữ liệu; sửa fleet/loại xe/template không đổi snapshot run cũ | Đạt phần schema A; cần lặp lại khi có schema B |
| AC09-5 | Một run thật hiện trên cả 4 trang, chuyển trang không mở SSE trùng; khoá start khi bận/offline, huỷ từ UI đến cancelled. Unit test giữ queued id khi start trả 409 | Đạt phần manager A; chưa kết luận luồng bản đồ live |
| AC09-6 | Hai run succeeded; delta/verdict khớp response API, warning seed không ghép cặp hiện đúng; CSV giữ số gốc/null và escape nội dung | Đạt phần metric tổng hợp A; phân rã chờ B |
| AC09-7 | Ảnh/kiểm tra 1280×800 và 1440×900, bảng cuộn riêng, label/focus/error/confirm, nav không bị fixed map che; Mapbox demo đã idle | Đạt các màn hình A; live/replay mới cần nghiệm thu tiếp |
| AC09-8 | Nhận metric SSE xuyên Next production khi status vẫn running, terminal tải lại DB; trang run thật không vẽ fixture | Một phần; chưa có xe/vệt live |
| AC09-9 | Chỉ giữ demo fixture cũ có nhãn | Chưa đạt; replay API chờ 04/08 B |
| AC09-10 | Không thêm filter giả | Chưa đạt; chờ attribution/snapshot B |
| AC09-11 | Benchmark engine nhỏ và smoke transport; chưa có browser vẽ xe live thật | Chưa đạt; chờ B và người dùng chốt Q1/PERF-4 |

S09-1/2/3/5/6/7 hoàn thành phần A theo schema hiện có; S09-8 hoàn thành wrapper và trang thông tin run;
S09-9 chỉ có progress/metric SSE. S09-10/11 và nghiệm thu S09-12 còn mở theo §6.
Chưa viết backlog kết thúc Sprint 09 vì chưa đủ AC/DoD; các mục B09-1…7 vẫn là mục dự kiến tại plan.

### 9.2. Kiểm thử và audit

- Web unit: **71/71 test**, 7 file; trong đó 15 test mới về API/error, form round-trip/thời gian, lifecycle/queued và CSV.
- TypeScript strict và production build: **đạt**. Dependency/lockfile giữ nguyên.
- Browser E2E production: **20/20 check**, SQLite file và worker spawn thật; không có pageerror.
  Kiểm cả conflict/draft, xoá có xác nhận, failed/404, restart/offline, snapshot bất biến, compare và SSE trước terminal.
- Next dev smoke trên bản sao source/dist riêng: proxy health, nhận metric trước terminal, điều hướng 4 trang và không có pageerror đều đạt; không dùng chung lock .next/dev với server người dùng.
- Python full suite: **182 test**, 152 đạt, 25 skip, **1 failure + 4 error**, 70,491 giây.
  Cùng đúng 5 lỗi nền đã tái hiện trên HEAD ở Sprint 08: RSS benchmark trên Windows, hai handle SQLite của CLI cũ,
  thiếu manifest mạng Hà Nội, dấu phân cách đường dẫn preset. Không phát sinh loại lỗi mới; suite toàn repo vẫn chưa xanh.
  Chạy với python -X utf8 và dependency test riêng của 08 (NumPy 1.26.4/pyarrow 25.0.1).
- Quickstart và python -m kami presets: exit 0. Môi trường benchmark hệ thống vẫn cảnh báo NumPy 2.4.3 ngoài
  khoảng hỗ trợ của SciPy 1.14.1; giữ cùng môi trường mốc 08 để so sánh, không thay dependency máy người dùng.
- npm audit hiện tại: **13 vulnerability (5 moderate, 8 high)**. audit fix --dry-run --ignore-scripts không đề xuất
  cập nhật tương thích để xoá các lỗi này (changed = 0); phương án được gợi ý hạ deck.gl về 9.0.6, ngoài dải ^9.4.0 đang dùng, nằm ngoài A.
  Không chạy force, không sửa package-lock.json; **B03-5 giữ mở**.
- **B03-9 xử lý một phần** bằng manager E2E thật; tương tác bản đồ live/replay còn chờ B.

### 9.3. Benchmark engine

Cùng repo/data root, Python 3.12.1, Windows, router Python, 5 lần/case; so với mốc sau Sprint 08.
Số event và metric của cả 5 case **bằng nhau chính xác**, mỗi case deterministic.

| Case | Mốc 08 median (s) | Lần đo đầy đủ 09 (s) | Thay đổi | Đo xác nhận riêng (s) |
|---|---:|---:|---:|---:|
| grid_am_peak_baseline | 1,1964 | 1,4188 | +18,58% | 1,2905 (+7,87%) |
| grid_am_peak_baseline_nots | 1,1126 | 1,1504 | +3,40% | — |
| grid_am_peak_surge | 1,1462 | 1,1585 | +1,07% | — |
| grid_pm_peak_x5 | 3,6182 | 3,1982 | −11,61% | — |
| road_example_400 | 13,3740 | 9,0686 | −32,19% | — |

Giữ nguyên [kết quả đo đầy đủ](../../benchmarks/results/2026-10-09-sprint09-a-windows.json), kể cả cảnh báo >10%.
Do case đầu dao động 1,11–1,69 giây, đo xác nhận riêng thêm 5 lần:
[kết quả xác nhận](../../benchmarks/results/2026-10-09-sprint09-a-grid-confirmation.json).
Đo lại không tái hiện ngưỡng >10%; đây là bằng chứng dao động thời gian máy, **không khẳng định đã tối ưu engine**.
Engine không đổi trong 09, các case khác không thoái lui >10%. RAM vẫn null/chưa đo trên Windows;
không suy ra 0 MB từ bảng CLI. Metadata git trong benchmark là null do quyền sở hữu Git của môi trường;
validation ghi HEAD 002c62c và working tree có thay đổi chưa commit.
Không có benchmark Hà Nội/C++ hay nghiệm thu PERF-4; không dùng các số trên thay cho AC09-11.

Smoke transport dev: 20 GET health tuần tự mỗi đường, median trực tiếp 2,375 ms và xuyên Next 4,799 ms.
Đây chỉ là độ trễ HTTP trên máy hiện tại; không đo overhead worker/renderer hoặc thay cho PERF-4.

### 9.4. Cải thiện UI Green SM — 2026-10-09

Theo yêu cầu người dùng, đã tái thiết kế manager bằng skill ui-ux-pro-max: sidebar, nền sáng/cyan,
thẻ tổng quan dữ liệu thật, tìm kiếm entity, nhóm form có liên kết điều hướng và nút lưu ở đáy,
nhãn metric tiếng Việt và thao tác bảng gọn hơn. Giữ stack/API/tokens chung và phạm vi A đã duyệt.
Tham khảo thương hiệu và quyết định: [green-sm-ui.md](../research/green-sm-ui.md).

- Unit web: 71/71; typecheck strict và production build đạt.
- E2E production: 23/23 kiểm tra, SQLite/worker thật; tìm kiếm, keyboard skip link, navigation có tên
  và kích thước ít nhất 44 px; CRUD/conflict/restart/run/SSE/CSV/compare/cancel vẫn đạt.
- Kiểm bố cục 375/768/1280/1440; không tràn ngang toàn trang manager, bảng cuộn riêng.
  Đã xem ảnh form, danh sách, kết quả, điện thoại và demo map; Mapbox idle, không có pageerror.
- Ảnh mới ở docs/engine/img/manager/redesign; log test ở web/.ui-validation (gitignored).
  Thêm KAMI_E2E_EVIDENCE_DIR để chọn thư mục ghi được, không thay quyền thư mục log cũ.
- Build bàn giao trỏ backend http://127.0.0.1:8000. Không chạy lại benchmark engine hoặc Python full
  suite trong lượt UI này; không có thay đổi engine/service/API. Lỗi nền và phụ thuộc tại §9.1–9.3 vẫn mở.

Bằng chứng: [validation UI redesign](../../benchmarks/results/2026-10-09-sprint09-ui-redesign-validation.json).
Trạng thái plan/sprint và các AC còn phụ thuộc B giữ nguyên.

### 9.5. Loading, modal và shadcn — 2026-10-09

Người dùng yêu cầu rõ ràng chuyển form sang modal, chuẩn hoá loading/skeleton, thay dropdown/switch và
cài toàn bộ shadcn; quyết định D1 được cập nhật theo chỉ đạo đó. Phạm vi A và các AC giữ nguyên.

- Cài source của toàn bộ registry radix-nova bằng shadcn CLI 4.21.4: 61 component UI và hook use-mobile.
  Bổ sung Tailwind v4/PostCSS và theme cyan; không bật Preflight reset cho visualizer.
  CLI dùng để sinh source qua npx, không giữ trong dependency sau cài. Không import component chưa dùng
  vào màn hình manager.
- LoadingState/LoadingValue dùng chung cho route/Suspense, entity, run result, comparison và map.
  Skeleton có pulse nhẹ, tắt animation với reduced motion; số liệu loading tách khỏi lỗi/thiếu dữ liệu.
  Reload entity cập nhật loading; lịch sử chờ detail không hiện empty state sai ở lần tải đầu.
- Form loại xe/fleet/scenario giữ danh sách phía sau và mở bằng Dialog; errors nằm trong modal.
  Nội dung cuộn riêng, giới hạn viewport, footer lưu sticky; Escape và nút đóng hỗ trợ focus.
  Click ra ngoài không bỏ draft, đóng khi đang lưu bị khoá. Modal xác nhận xoá dùng cùng nền tảng.
- Dropdown manager dùng Select shadcn thay HTML select; hỗ trợ bàn phím và portal trong modal.
  Switch shadcn có track/nhãn gọn; bỏ viền nền bao quanh các tab manager.
- Unit web 71/71 và TypeScript strict đạt; production E2E mở rộng kiểm loading chờ API thực,
  reduced motion, modal không làm dịch trang, dropdown keyboard/focus, switch, layout/menu mobile.
  Browser đạt 27/27 kiểm tra, không có pageerror; modal/dropdown nằm trong viewport 375/768/1440, switch thumb nằm trong track. Production build đạt và bản bàn giao trỏ backend 8000. Bằng chứng ở validation riêng bên dưới.
- npm audit sau cài: 13 cảnh báo (5 moderate, 8 high), bằng mốc trước lượt này. Không giữ 7 cảnh báo
  thêm của CLI shadcn dev; không force fix hoặc đổi major renderer. B03-5 tiếp tục mở.

Bằng chứng: [validation loading/modal/shadcn](../../benchmarks/results/2026-10-09-sprint09-shadcn-validation.json).
Ảnh loading, modal, dropdown và switch ở docs/engine/img/manager/redesign; hướng dẫn tại
[22-ui-guide.md §8](../engine/22-ui-guide.md#8-loading-và-component-shadcn).
Không chạy lại engine benchmark/Python suite ở lượt chỉnh UI; engine/service/API không đổi.
