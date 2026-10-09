# Hướng thiết kế UI vận hành Green SM — 2026-10-09

Phạm vi: cải thiện giao diện manager A trong [plan Sprint 09](../implementation-plan/sprint-09-plan.md),
theo yêu cầu người dùng. Không thay đổi phạm vi sprint, schema hoặc định nghĩa metric.

## 1. Nguồn tham khảo

- [Website Green SM Việt Nam](https://www.greensm.com/vn-vi) mô tả màu cyan thương hiệu của
  Green SM Car, dịch vụ thuần điện và các nhóm sản phẩm/đối tượng.
- [Thông báo đồng bộ nhận diện Green SM](https://www.greensm.com/vn-vi/news/xanh-sm-doi-ten-thanh-green-sm-dong-bo-nhan-dien-thuong-hieu-tren-toan-cau)
  đề cập giao diện ứng dụng tối giản, tối ưu trải nghiệm.
- Skill ui-ux-pro-max: truy vấn design-system “enterprise SaaS analytics dashboard” trả về
  Data-Dense Dashboard; phù hợp bảng, thẻ chỉ số, trạng thái và ít hiệu ứng. Truy vấn đầu
  “fleet operations dashboard mobility” trả HUD/Sci-Fi, không phù hợp người dùng vận hành;
  đã thu hẹp truy vấn trước khi sử dụng. Pattern landing bán hàng trong kết quả không áp dụng.
- Truy vấn stack Next.js “accessible forms navigation”, cùng checklist của skill:
  nhãn trường, focus, kích thước tương tác, responsive, empty state và giảm chuyển động.
  Giữ API client đã duyệt thay vì chuyển mutations sang Server Actions.

## 2. Quyết định thiết kế

| Thành phần | Lựa chọn và lý do |
|---|---|
| Nhận diện | Giữ kami là tên sản phẩm; Green SM là ngữ cảnh workspace. Dùng accent cyan #0ABAB5 đã có trong tokens, không coi đây là bảng màu chính thức do GSM cung cấp |
| Bố cục | Sidebar xanh đậm #103C3E, canvas sáng #F3F7F7, nội dung trắng; tách điều hướng khỏi vùng thao tác |
| Chữ | Giữ Inter có Vietnamese subset, phân cấp tiêu đề/nội dung/chú thích và số tabular; không tải thêm font |
| Hành động | Một nút tạo chính ở đầu trang; chạy/sửa/xoá tách mức độ, tên truy cập có tên entity để phân biệt các dòng |
| Danh sách | Tìm theo tên, thông báo không có kết quả, tổng quan lấy từ entity/run thật; không điền số 0 khi đang tải hoặc lỗi |
| Kịch bản | Nhóm bản đồ, nhu cầu, đội xe, kết quả và liên kết tới từng nhóm; thời tiết/sự cố tiếp tục là phần mở rộng |
| Phân tích | Các thẻ chỉ số đã lưu, diễn giải tiếng Việt, mã metric trong bảng; không tự tính lại delta/verdict |
| Responsive | Sidebar đầy đủ ở desktop, biểu tượng ở tablet, biểu tượng và nhãn ngắn trên điện thoại; bảng cuộn riêng |
| Accessibility | Điều hướng có tên và aria-current; focus rõ; skip link đưa focus tới nội dung; lỗi field được liên kết bằng aria-describedby; ô nhập mobile 16 px |

Không dùng ảnh xe hoặc dashboard giả vì UI dành cho thử nghiệm vận hành và dữ liệu manager phải có nguồn thật.
Bản đồ fixture giữ nhãn demo; xe live, EV đầy đủ và phân rã metric tiếp tục theo phụ thuộc đã ghi trong plan.

## 3. Kiểm chứng

Web unit, typecheck, production build và E2E dùng SQLite/worker thật. E2E bổ sung tìm kiếm, bàn phím,
điều hướng và bố cục 375/768/1280/1440. Ảnh tại [manager/redesign](../engine/img/manager/redesign/).
Kết quả cuối ghi bổ sung trong plan Sprint 09; đây không phải nghiệm thu kết thúc toàn sprint.
