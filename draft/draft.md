Hiện tại tôi có hướng phát triển như sau cho kami


# Yêu cầu chức năng, phi chức năng

## Hiệu năng

Có thể mô phỏng được operation của GreenSM ở Hà Nội với ước tính khoảng 100k yêu cầu đặt xe/ngày và fleet khoảng 8k xe 

## Mô phỏng traffic, đường đi của xe

Mô phỏng được đường đi thật của xe trên map Hà Nội, tham khảo cách làm của FleetPy

Mô phỏng được tắc đường tại giờ cao điểm

## Mô phỏng việc sạc xe

Chia thành vài loại xe (Bike 1 loại, Car 4-5 loại)

Thời gian sạc, quãng đường tối đa có thể đi 

Behavioral model với quyết định sạc xe

## Mô phỏng fleet 

Có thể có nhiều fleet, mỗi fleet bao gồm

Số lượng xe

Loại xe (Tên, số km đi được tối đa trước khi sạc)

Các config này phải được chỉnh qua UI và phải được lưu trong DB

## Mô phỏng dynamic pricing

Tham khảo các chiến lược pricing của FleetPy

Chiến lược pricing ảnh hưởng đến offer cho rider và quyết định đặt/hủy của rider

## Mô phỏng policy

Có thể tạo/nhóm các policy plugin thành từng nhóm policy

Các policy plugin phải được thiết kế sao cho có thể mô phỏng được các policy ngoài đời thật bằng code

Các policy plugin/policy group phải được thiết kế sao cho có thể lưu vào DB

Thiết kế UI sao cho người dùng có thể tự định nghĩa và apply policy

Người dùng có thể chọn hệ thống đang apply/không apply policy nào

Tạo một policy agent giúp người dùng tạo 1 policy mới thông qua ngôn ngữ tự nhiên.


## Chạy các mô phỏng

Người dùng có thể tạo và chạy các kịch bản mô phỏng (hiện tại cho phép chạy 1 kịch bản/lần)

Người dùng có thể xem kịch bản mô phỏng nào đang chạy

Có thể config cho từng kịch bản mô phỏng (chọn fleet nào, nhóm policy nào)

## Giao diện

### Simulation visualizer (?)

Xem bản visualization của mô phỏng, cùng với live metric

### Simulation manager

Trang manage các kịch bản simulation hiện tại

Trang manage fleet xe

Trang manage policy, với policy agent

Trang xem metric của các kịch bản simulation, các metric lưu vào DB

# Quản lý dự án

### Documentation

Documentation cho các module của engine hiện tại lưu ở `docs`, chuyển những file này vào 1 folder con khác

Chia thành các sprint lưu ở `docs/sprint`, mỗi sprint mô tả chi tiết công việc cần làm, các acceptance criteria, không cần implementation

Backlog lưu ở `docs/backlogs` : Backlog sau mỗi sprint (phần nào chưa thể implement luôn sau sprint trước, phần nào còn đang mock, etc.)
### Workflow

Đọc file sprint và đưa ra hướng triển khai cho sprint đó. file hướng triển khai cho mỗi sprint lưu ở `docs/implementation plan`. mỗi file plan phải refer đến file sprint tương ứng

Khi người dùng duyệt implementation plan thì mới bắt đầu implement sprint

Sau thực hiện sprint, nếu còn phần nào chưa thể triển khai ngay (đợi module khác hoàn thành, đang phải dùng mock data) thì viết vào `docs/backlog` và refer đến file backlog ở sprint sau