# Sprint 07 — Policy plugin v2 & policy group

| | |
|---|---|
| Trạng thái | Chưa bắt đầu |
| Yêu cầu | POL-1, POL-2, POL-3, POL-5, NFR-3 |
| Phụ thuộc | Sprint 01 (schema/DB), Sprint 05 (hook sạc), Sprint 06 (pricing strategy) |
| Backlog đầu vào | [sprint-06-backlog.md](../backlog/sprint-06-backlog.md) |
| Implementation plan | [sprint-07-plan.md](../implementation-plan/sprint-07-plan.md) (chưa có) |

## Mục tiêu

Policy trở thành **thực thể có định nghĩa, tham số, phiên bản**, lưu được trong DB, nhóm được thành **policy group**
và bật/tắt được từng thành viên. Bộ hook và API đủ rộng để **viết bằng code** các policy vận hành ngoài đời thật.
Policy do người dùng (và sau này là policy agent) viết được nạp và chạy **an toàn**.

## Phạm vi

- Manifest cho policy plugin: tên, mô tả, nhóm (dispatch, pricing, reposition, charging, incentive,
  cancellation…), hook sử dụng, schema tham số, phiên bản.
- Hai nguồn plugin: dựng sẵn trong code (built-in) và **plugin tuỳ biến** lưu mã nguồn trong DB.
- Policy group với quy tắc kết hợp rõ ràng giữa các thành viên.
- Cơ chế apply/không apply.
- Mở rộng thư viện policy để phủ danh mục policy thực tế.
- Sandbox cho plugin tuỳ biến.

## Ngoài phạm vi

- API HTTP và UI (Sprint 08, 09).
- Sinh policy từ ngôn ngữ tự nhiên (Sprint 10). Sprint này chỉ chuẩn bị đường nạp/kiểm tra mà agent sẽ dùng.

## Hạng mục công việc

| Mã | Hạng mục |
|---|---|
| S07-1 | Manifest policy plugin: `name`, `display_name`, `description`, `category`, `hooks`, `params_schema` (JSON Schema: kiểu, mặc định, min/max, mô tả, đơn vị), `version`. Từ `params_schema` sinh được form ở UI (Sprint 09) |
| S07-2 | Chuyển mọi policy dựng sẵn (`Baseline`, `SurgePricing`, `HeatmapReposition`, các pricing strategy ở Sprint 06, policy sạc ở Sprint 05) sang có manifest. `PoolAfterWait` (pooling, ngoài phạm vi 0.2 — requirements §5) vẫn chạy như 0.1 nhưng không đưa vào danh mục plugin |
| S07-3 | Rà soát hook/API so với danh mục policy của design doc §7.3 và bổ sung chỗ thiếu: ví dụ sổ chi phí khuyến khích (Quest/Boost, trợ giá), phí hủy, hold control, gửi cuốc cho nhiều tài xế, switchback theo khung thời gian. Ghi bảng "policy thật → plugin/hook" trong tài liệu |
| S07-4 | Thêm tối thiểu các plugin mới: `QuestBonus` (thưởng theo số chuyến), `CancellationFee`, `HoldControl`, `OffPeakCharging` (nếu chưa có ở Sprint 05) |
| S07-5 | Policy group: danh sách thành viên có thứ tự, mỗi thành viên = (plugin, phiên bản, tham số, `enabled`). Quy tắc kết hợp theo nhóm: pricing nối chuỗi; dispatch chỉ một thành viên; reposition/charging lấy quyết định đầu tiên khác `None`; incentive/cancellation cộng dồn. Phát hiện và báo lỗi xung đột (ví dụ hai dispatch cùng bật) |
| S07-6 | Apply/không apply: mỗi kịch bản chọn một policy group; trong group bật/tắt từng thành viên; có policy group "baseline hệ thống" mặc định. Snapshot phiên bản thực tế đã dùng vào run (NFR-4) |
| S07-7 | Plugin tuỳ biến: lưu mã nguồn + manifest trong DB, có phiên bản bất biến (sửa = tạo phiên bản mới); nạp động khi chạy |
| S07-8 | Kiểm tra plugin tuỳ biến trước khi lưu: kiểm tra tĩnh (chỉ import module cho phép, không truy cập file/mạng/`random`), chạy thử trên kịch bản nhỏ, giới hạn thời gian/bộ nhớ mỗi hook; trả báo cáo lỗi dễ đọc |
| S07-9 | Sandbox khi chạy: plugin tuỳ biến lỗi hoặc quá thời gian không làm sập engine; run được đánh dấu lỗi với thông tin hook gây lỗi (NFR-3) |
| S07-10 | Tài liệu: viết lại `docs/engine/07-policy.md` (manifest, group, plugin tuỳ biến, checklist, bảng policy thật → plugin) |

## Acceptance criteria

- [ ] AC07-1 Mọi policy dựng sẵn có manifest hợp lệ; `params_schema` từ chối tham số sai kiểu/ngoài khoảng.
- [ ] AC07-2 Policy group lưu vào DB và đọc lại đúng (thành viên, thứ tự, phiên bản, tham số, `enabled`).
- [ ] AC07-3 Group gồm surge + heatmap_reposition cho kết quả giống `Composite` tương đương của 0.1 (cùng seed).
- [ ] AC07-4 Tắt một thành viên cho kết quả giống group không có thành viên đó.
- [ ] AC07-5 Group có hai plugin dispatch cùng bật bị từ chối với thông báo rõ ràng.
- [ ] AC07-6 Một plugin tuỳ biến hợp lệ (mã nguồn trong DB) chạy được trong group; plugin dùng `import os`, mở file
      hoặc vòng lặp vô hạn bị chặn ở bước kiểm tra hoặc bị dừng khi chạy mà engine không sập.
- [ ] AC07-7 Sửa plugin tạo phiên bản mới; run cũ vẫn tái lập được bằng phiên bản cũ (NFR-1, NFR-4).
- [ ] AC07-8 Tài liệu có bảng ánh xạ ít nhất 10 policy vận hành thực tế → plugin/hook, mỗi dòng ghi rõ đã có hay cần gì.
- [ ] AC07-9 Toàn bộ test cũ pass; API `Policy`/`Composite` của 0.1 vẫn dùng được trong code.

## Rủi ro & câu hỏi mở

- Sandbox Python trong cùng tiến trình không tuyệt đối an toàn; có thể cần chạy plugin tuỳ biến ở tiến trình riêng.
  Đánh đổi an toàn và hiệu năng quyết định trong plan.
- Khái niệm "hệ thống đang apply policy nào" (POL-5) cần chốt: theo từng kịch bản, hay có một cấu hình "hiện hành"
  toàn cục làm baseline cho mọi so sánh. Giả định tạm: cả hai (group baseline hệ thống + chọn group theo kịch bản).
