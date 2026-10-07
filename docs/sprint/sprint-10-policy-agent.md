# Sprint 10 — Policy agent (ngôn ngữ tự nhiên → policy)

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | POL-6, NFR-3 |
| Phụ thuộc | Sprint 07 (plugin tuỳ biến, kiểm tra, sandbox), Sprint 09 (trang policy) |
| Backlog đầu vào | [sprint-09-backlog.md](../backlog/sprint-09-backlog.md) |
| Implementation plan | [sprint-10-plan.md](../implementation-plan/sprint-10-plan.md) (chưa có) |

## Mục tiêu

Người dùng mô tả một policy bằng **ngôn ngữ tự nhiên** (ví dụ: "khách chờ quá 5 phút thì đề nghị ghép chuyến, giảm
15.000đ, chỉ áp dụng giờ cao điểm chiều ở quận Cầu Giấy"), **policy agent** hỏi lại chỗ mơ hồ, sinh ra plugin
tuỳ biến (mã + manifest + tham số), tự kiểm tra và chạy thử, rồi đưa cho người dùng **duyệt trước khi lưu**.

## Phạm vi

- Dịch vụ policy agent dùng LLM, có ngữ cảnh là tài liệu hook/API, manifest và các plugin mẫu.
- Hội thoại nhiều lượt trong trang policy.
- Vòng tự kiểm tra: sinh → kiểm tra tĩnh → chạy thử → sửa lỗi.
- Bước duyệt của người dùng và lưu thành phiên bản plugin.

## Ngoài phạm vi

- Agent tự apply policy vào hệ thống hoặc tự chạy run lớn mà không có người duyệt.
- Agent sửa engine hoặc plugin built-in.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S10-1 | Gói ngữ cảnh cho agent: danh sách hook, API engine được phép gọi, quy tắc (không `random`, dùng CRN, không sửa trạng thái agent trực tiếp), manifest/`params_schema`, các plugin mẫu theo nhóm. Sinh tự động từ code/tài liệu để không lệch phiên bản |
| S10-2 | Hội thoại: agent hỏi lại khi thiếu thông tin quan trọng (điều kiện kích hoạt, phạm vi zone/giờ, tham số, metric kỳ vọng); tóm tắt lại policy bằng ngôn ngữ tự nhiên trước khi sinh mã |
| S10-3 | Sinh plugin: mã nguồn + manifest (tên, nhóm, hook, `params_schema` với mặc định hợp lý) + mô tả; ưu tiên **tái sử dụng plugin có sẵn bằng tham số** khi yêu cầu đã được plugin built-in đáp ứng |
| S10-4 | Vòng tự kiểm tra: chạy bước kiểm tra tĩnh và chạy thử của Sprint 07; nếu lỗi, agent tự sửa tối đa N lần; báo cáo kết quả cuối cùng |
| S10-5 | Chạy thử so sánh nhanh: trên kịch bản nhỏ cấu hình được, so plugin mới với baseline (cùng seed) và đưa ra vài metric chính để người dùng thấy policy có tác dụng đúng chiều mô tả |
| S10-6 | Duyệt: UI hiển thị tóm tắt, mã, tham số, kết quả kiểm tra và chạy thử; người dùng chấp nhận (lưu phiên bản mới), yêu cầu sửa (tiếp tục hội thoại) hoặc bỏ |
| S10-7 | Lưu vết: lưu hội thoại, các phiên bản nháp, mô hình LLM đã dùng kèm plugin được tạo |
| S10-8 | Giới hạn & an toàn: mã sinh ra luôn đi qua sandbox Sprint 07; giới hạn số lượt gọi LLM/chi phí mỗi phiên; không gửi dữ liệu nhạy cảm ngoài ngữ cảnh cần thiết |
| S10-9 | Bộ đánh giá agent: ≥ 10 mô tả policy mẫu (từ dễ đến khó, gồm cả yêu cầu mơ hồ và yêu cầu không làm được) với kết quả mong đợi |
| S10-10 | Tài liệu: thêm `docs/engine/23-policy-agent.md` (kiến trúc, ngữ cảnh, vòng kiểm tra, giới hạn) |

## Acceptance criteria

- [ ] AC10-1 Trên bộ đánh giá S10-9, ≥ 80% mô tả làm được cho ra plugin qua được kiểm tra và chạy thử không lỗi.
- [ ] AC10-2 Với yêu cầu mơ hồ, agent hỏi lại ít nhất một câu thay vì tự đoán âm thầm.
- [ ] AC10-3 Với yêu cầu không làm được bằng hook/API hiện có, agent nói rõ thiếu gì thay vì sinh mã sai.
- [ ] AC10-4 Yêu cầu đã có plugin built-in tương ứng thì agent đề xuất dùng plugin đó với tham số thay vì sinh mã mới.
- [ ] AC10-5 Không plugin nào được lưu khi người dùng chưa bấm duyệt; plugin đã duyệt xuất hiện trên trang policy và
      thêm được vào policy group.
- [ ] AC10-6 Mã sinh ra cố ý vi phạm (import `os`, dùng `random`) bị chặn bởi bước kiểm tra.
- [ ] AC10-7 Kết quả chạy thử so sánh dùng cùng seed và hiển thị chênh lệch metric so với baseline.

## Rủi ro & câu hỏi mở

- Chọn mô hình LLM, nơi chạy và chi phí (requirements Q6).
- Chất lượng mã sinh ra phụ thuộc chất lượng tài liệu hook/API: Sprint 07 cần tài liệu tốt.
