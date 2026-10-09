# Nghiên cứu cước shared ride và phân chia doanh thu

| | |
|---|---|
| Ngày khảo sát | 2026-10-09 |
| Trạng thái | Người dùng đã chọn phương án A: Shared trả 70% cước đi riêng; toàn bộ plan V1 vẫn Chờ duyệt, chưa implement |
| Phạm vi | Shared Only / Exclusive Only; đúng hai booking, mỗi booking một người |
| Yêu cầu người dùng | Ví dụ đi riêng 10 thì shared trả 7; xét khoảng cách/thời gian mỗi khách; nếu hãng không công khai công thức thì nghiên cứu mô hình tổng cước bằng 1,5 lần cước tuyến chung rồi chia theo tỷ lệ |
| Liên quan | [Các phiên bản](shared-rides-versions.md), [plan V1 Chờ duyệt](../implementation-plan/sprint-12-plan.md), [FareModel hiện tại](../../kami/pricing.py) |

## 1. Kết luận khảo sát

**Quyết định mới nhất ngày 2026-10-09:** người dùng chốt mỗi khách Shared trả **70% cước đi riêng của họ**.
Phương án A được chọn; phương án B 1,5 lần tuyến chung bên dưới giữ làm nghiên cứu, không triển khai V1.
Chi tiết quote/payout được cập nhật ở plan D10/S12-9/AC12-11. Các đề xuất sàn payout/bonus/lọc kinh tế chưa
được chốt chỉ bởi quyết định giá khách; toàn bộ implementation plan vẫn cần duyệt.

Có nguồn thực tế cho cách giảm giá theo chuyến riêng và báo giá trước; có nghiên cứu cho cách phân bổ tổng cước
theo tỷ lệ cước đi riêng. Chưa tìm thấy trong các nguồn đã khảo sát công thức thương mại công khai quy định
**tổng cước = 1,5 × cước của toàn tuyến chung**, rồi phân bổ cho hai người theo 60/40.
Hệ số 1,5 vì vậy là giả định để thử nghiệm, không phải thông số thực tế của Uber/Grab/Green SM.

Phương án đã được người dùng chọn: mỗi khách trả **70% cước đi riêng**, tổng hai khoản là ngân sách
shared; chỉ lập cặp khi cả thời gian và kinh tế khả thi. Mô hình này khớp ví dụ 10 → 7, tự chia 60/40 khi cước
đi riêng có tỷ lệ đó, và báo giá được trước khi biết đối tác. Mô hình 1,5 lần tuyến chung giữ làm nghiên cứu
đối chứng; nếu được yêu cầu triển khai sau này thì cần thêm trần cước khách và kiểm tra payout tài xế.

Hiểu “nếu không được chia sẻ” trong yêu cầu là hãng không công khai công thức tính cước.
Khách Shared Only không tìm được cặp vẫn hủy theo deadline; không phát sinh cước 1,5 lần cho chuyến không có cặp.

Các số 12.000đ ban đầu, 9.000đ/km, 400đ/phút, tối thiểu 25.000đ trong trao đổi trước là **default của
FareModel trong kami**, không phải bảng giá Green SM được xác minh. Discount 30% nay đã được người dùng chọn;
hệ số 1,5 và các quy tắc sàn payout/chi phí vẫn là nghiên cứu chưa được duyệt.

## 2. Nguồn thực tế và giới hạn áp dụng

### GrabShare — có tiền lệ gần ví dụ 10 → 7

Thông cáo Grab Singapore ngày **06/12/2016** công bố GrabShare rẻ hơn GrabCar Economy **đến 30%**, với giá cố
định hiển thị trước. Bài này mô tả ghép hai booking. Đây là chính sách lịch sử tại Singapore, không chứng minh
mọi chuyến hiện tại ở Việt Nam đều giảm 30%.
[Nguồn Grab](https://www.grab.com/sg/press/tech-product/share-ride-fare-grabshare-grabs-new-commercial-carpool-service/).

Grab Việt Nam ngày **16/06/2017** có bảng minh họa GrabCar 50.000đ và GrabShare 35.000đ, cùng chương trình
thưởng tài xế. Bảng cặp shared dùng hai cước 35.000đ + 28.000đ và payout 69.300đ, có thưởng 30% trên tổng cước
và phí 20%. Đây là minh họa/chương trình lịch sử ở TP.HCM, không phải biểu giá hay thu nhập đảm bảo hiện nay.
[Nguồn Grab Việt Nam](https://www.grab.com/vn/blog/driver/car/hcm-cap-nhat-thuong-grabshare/).

**Suy luận từ bảng cặp:** khách trả tổng 63.000đ nhưng tài xế nhận 69.300đ; nếu chỉ xét các khoản đó, nền tảng
chi thêm 6.300đ trước chi phí khác. Do đó “khách rẻ hơn, tài xế nhận nhiều hơn” có thể đến từ trợ giá,
không tự chứng minh mô hình không cần trợ giá.

### UberX Share — tách giá khách và payout tài xế

Trang Uber dành cho khách hiện mô tả giá upfront, dùng thời gian dự kiến, khoảng cách, giao thông, surge và
dự đoán khả năng ghép. Không công bố một công thức chia tổng cước giữa A/B theo phần trăm cố định.
[Nguồn Uber khách](https://www.uber.com/us/en/ride/uberx-share/).

Trang Uber dành cho tài xế mô tả payout theo thời gian/quãng đường từ pickup đầu tới dropoff cuối, thêm tiền
cho pickup sau; mức nhận được không thấp hơn chuyến UberX tương đương trên tuyến đó. Giá/khuyến mãi của khách
không trực tiếp quyết định payout. Trang cũng giới hạn thông tin theo thị trường và có thể thay đổi.
[Nguồn Uber tài xế](https://www.uber.com/us/en/drive/services/shared-rides/).

**Suy luận thiết kế:** nên mô phỏng hai đại lượng riêng: tiền khách trả và tiền tài xế nhận.
Không lấy quảng cáo giảm giá của khách làm bằng chứng tài xế bị giảm cùng tỷ lệ.

### Green SM — có ghép liên tỉnh, khác mô hình đô thị hai booking

Green SM ngày **21/11/2025** công bố ghép chuyến liên tỉnh bằng Limo Green theo tuyến cố định; ví dụ Hà Nội–Nam
Định là 140.000đ/khách, thuê trọn chuyến 1.110.000đ, có gói đón/trả quanh tuyến. Bài ngày **08/01/2026** tiếp tục
mô tả đặt theo chỗ hoặc nguyên xe trên các tuyến cố định. Đây là bằng chứng có sản phẩm ghép, chưa phải công
thức shared đô thị linh hoạt hai booking ở Hà Nội.
[Thông cáo 2025](https://www.greensm.com/vn-vi/news/xanh-sm-trien-khai-dich-vu-xe-7-cho-lien-tinh-bang-xe-limo-green),
[tính năng liên tỉnh 2026](https://www.greensm.com/vn-vi/news/ra-mat-tinh-nang-xanh-lien-tinh-tren-ung-dung-xanh-sm).

Chưa tìm được công thức đô thị đó trong các nguồn chính thức đã khảo sát; không suy ra Green SM không có
thông tin nội bộ hoặc không thể triển khai sản phẩm tương tự.

## 3. Cơ sở nghiên cứu về phân bổ cước

Chau, Shen và Zhou (2020), mục IV, phương trình **(5)**, nghiên cứu **proportional cost-sharing**:
phần trả của mỗi khách bằng tổng chi phí chung nhân tỷ lệ chi phí đi riêng của người đó trên tổng chi phí
đi riêng. Bài cũng xét chia đều, chia khoản tiết kiệm đều và chia theo đoạn đường. Đây là cơ sở học thuật cho
tỷ lệ theo cước đi riêng, không phải công thức thương mại của hãng.
[Bài gốc, trang 4 PDF](https://arxiv.org/pdf/2007.08064).

Nghiên cứu của Bujak và Kucharski (2024) xem giảm cước là bù cho bất tiện đi chung/đi lâu hơn và nghiên cứu
discount cá nhân hóa; cho thấy cần cân bằng khả năng chấp nhận với hiệu quả kinh tế trong mô hình của bài.
Không dùng kết quả nghiên cứu đó để khẳng định một mức discount tối ưu cho Hà Nội.
[Bài gốc](https://arxiv.org/abs/2411.03370).

Việc chia theo cước trực tiếp do đó có căn cứ. Hệ số markup tuyến chung và lựa chọn 30% discount trong kami
là đề xuất riêng, cần thí nghiệm và duyệt trước implement.

## 4. Ký hiệu và cách đo

| Ký hiệu | Nghĩa |
|---|---|
| `F_A`, `F_B` | Cước Exclusive trực tiếp của từng booking, cùng bảng giá và quy tắc surge/quote đã khóa |
| `L_A`, `T_A`; `L_B`, `T_B` | Khoảng cách/thời gian tuyến đi riêng, không gồm vòng để phục vụ đối tác |
| `L_pair`, `T_pair` | Tuyến xe từ pickup đầu tới dropoff cuối, mỗi đoạn chỉ tính một lần; thời gian gồm dwell giữa hai mốc đó |
| `Q = fare(L_pair, T_pair)` | Cước tham chiếu nếu tính tuyến chung như một cuốc bình thường; **không phải chi phí vận hành xe** |
| `R` | Tổng tiền hai khách trả cho chuyến shared |
| `p_A`, `p_B` | Tiền từng khách trả, tổng đúng bằng R |
| `W` | Tổng payout tài xế cho chuyến shared |
| `c` | Tỷ lệ phí nền tảng trong mô hình mô phỏng; hiện default FareModel là 25%, chưa hiệu chỉnh Green SM |

Đường xe rỗng tới pickup đầu không đưa vào tỷ lệ đi của A/B trong đề xuất đơn giản, nhưng phải tính vào
chi phí/thu nhập theo giờ của xe và tài xế. Toll, phí hủy, thuế và khuyến mãi cần định nghĩa riêng nếu đưa vào;
không tự nhân tất cả chúng với 1,5.

## 5. Phương án A — giảm cước từng khách

Với mức giảm `d = 0,30`:

```text
p_A = (1 - d) × F_A
p_B = (1 - d) × F_B
R   = (1 - d) × (F_A + F_B)
```

Ví dụ F_A = F_B = 10: mỗi người trả 7, tổng 14. Ví dụ F_A = 60 và F_B = 40: A trả 42, B trả 28, tổng 70.
Tỷ lệ tự là 60/40 vì nhu cầu của A/B đã phản ánh khoảng cách và thời gian đi riêng.

Ưu điểm: đơn giản, báo giá ngay lúc khách đặt; không cần biết người ghép là ai; người bị vòng không tự trả
thêm vì vòng. Nhược điểm: không bảo đảm mọi cặp đủ doanh thu cho tuyến xe chung; cần lọc kinh tế hoặc ghi trợ giá.

**Đã chọn cho V1:** người dùng duyệt mỗi khách trả 70% cước đi riêng. Không thêm control đổi discount trong
V1 hiện tại; thay tỷ lệ sau này cần chỉ đạo mới. Cước tham chiếu vẫn theo bảng giá kịch bản.

## 6. Phương án B — 1,5 lần cước tuyến chung rồi chia tỷ lệ

Diễn đạt ý tưởng người dùng thành công thức thử nghiệm:

```text
R_raw = alpha × Q                  # alpha = 1,5
w_A   = F_A / (F_A + F_B)
w_B   = F_B / (F_A + F_B)
p_A   = R_raw × w_A
p_B   = R_raw × w_B
```

Nên dùng **tỷ lệ cước đi riêng**, thay vì số km/thời gian khách thực ngồi trong xe shared:

- Cước trực tiếp đã đổi km và phút sang cùng đơn vị tiền, gồm phí ban đầu/tối thiểu của bảng giá.
- Không cộng `km + phút` vì khác đơn vị. Nếu chỉ dùng km thì bỏ qua khác biệt thời gian do traffic.
- Dùng quãng đường shared thực tế có thể bắt khách bị vòng trả tỷ lệ lớn hơn vì bất tiện của đối tác.
- Đo mức sử dụng tuyến thực tế vẫn hữu ích cho metric và phương án chia theo từng đoạn về sau.

Với F_A = F_B = 10, Q = 10: tổng 15, mỗi người **7,5**, không phải 7. Muốn đúng 7 trong ca đó thì alpha = 1,4.
Với F_A = 60, F_B = 40, Q = 60: tổng 90, chia 54/36; cả hai giảm 10%, không phải 30%.

Vì vậy hệ số 1,5 không tương đương discount 30%. Mức giảm thực tế dưới tỷ lệ này là:

```text
d_effective = 1 - alpha × Q / (F_A + F_B)
```

Hai khách được giảm cước nếu `alpha × Q < F_A + F_B`. Muốn mỗi khách giảm ít nhất d:
`alpha × Q <= (1-d) × (F_A + F_B)`. Với alpha=1,5 và d=30%, đòi Q không quá 46,67% tổng cước đi riêng.
Cặp có chuyến rất ngắn xen vào chuyến rất dài thường khó đáp ứng mức giảm đó; phải đo tỷ lệ cặp bị loại.

### Phản ví dụ cần tránh

F_A = F_B = 10, Q = 14: tổng 21, mỗi người trả **10,5**, cao hơn đi riêng.
Tuyến có overlap không tự bảo đảm cước kinh tế khả thi.

Có thể đặt trần tổng cước:

```text
R = min(alpha × Q, (1-d_min) × (F_A + F_B))
p_i = R × F_i / (F_A + F_B)
```

Sau trần phải kiểm payout và chi phí. Không chỉ `min()` giá rồi mặc định tài xế/nền tảng chịu khoản thiếu.
Nếu R không đủ, đề xuất bỏ phương án ghép đó; Shared Only tìm cặp khác tới deadline, không fallback Exclusive.

## 7. Tài xế có lợi khi nào?

Với commission cố định và không trợ giá, mô hình đơn giản là `W = (1-c) × R`.
Một sàn payout để review là không thấp hơn cuốc thường tương đương tuyến xe chung:

```text
W_floor = (1-c) × Q + b
```

`b >= 0` là phụ phí pickup thứ hai nếu sau này được duyệt; demo không tự chọn b >0.
Để tự cân đối trong mô hình commission này: `R >= Q + b/(1-c)`.
Đây là **đề xuất cho kami**, lấy ý tưởng kiểm tuyến thực sự từ nguồn Uber; không sao chép mức payout Uber.

Ví dụ khách trả tổng 14, c=25%: tài xế nhận 10,5. Nếu một chuyến riêng cước 10 thì nhận 7,5;
shared có thể tốt hơn **một cuốc tương đương**. Nhưng hai cuốc riêng cước tổng 20 trả tài xế tổng 15,
lớn hơn 10,5; không thể khẳng định shared nhận nhiều hơn hai cuốc riêng.

Lợi ích thường cần so trên **thời gian/quãng đường sử dụng nguồn lực**: một shared ngắn có thể hoàn thành nhanh
hơn hai cuốc riêng tuần tự, hoặc giải phóng một xe khác. Cần đo doanh thu/lợi nhuận theo giờ, không chỉ tiền/cuốc.

```text
driver_net = W - driver_operating_cost
driver_net_per_hour = driver_net / total_service_hours
platform_contribution = R - W - platform_operating_cost - other_subsidy
```

Các khoản chi phí phải thuộc đúng bên sở hữu/chi trả, không tính cùng chi phí xe vào cả driver và platform.
Fleet xe hãng sở hữu, tài xế lương/thưởng và tài xế đối tác commission có thể cần accounting khác nhau;
FareModel 25% hiện có không chứng minh cấu trúc thu nhập thật của Green SM.
So với counterfactual cùng demand/seed, kể cả thời gian chạy rỗng, chờ, sạc khi module EV đã có thật.

## 8. Ví dụ số để review

Đơn vị tiền quy ước, chưa commission/chi phí; B_raw là công thức alpha=1,5 chưa đặt trần.

| F_A | F_B | Q | A: giảm 30%, tổng / A / B | B_raw: tổng / A / B | Nhận xét |
|---:|---:|---:|---|---|---|
| 10 | 10 | 10 | 14 / 7 / 7 | 15 / 7,5 / 7,5 | Cả hai rẻ hơn; A khớp ví dụ 10→7 |
| 60 | 40 | 60 | 70 / 42 / 28 | 90 / 54 / 36 | Tỷ lệ 60/40; A giảm 30%, B_raw giảm 10% |
| 10 | 10 | 14 | 14 / 7 / 7 | 21 / 10,5 / 10,5 | B_raw làm khách đắt hơn; A chỉ vừa sàn R>=Q khi b=0 |
| 10 | 10 | 15 | 14 / 7 / 7 | 22,5 / 11,25 / 11,25 | A dưới sàn tuyến chung; cần loại cặp hoặc ghi trợ giá, B_raw cũng không phù hợp cho khách |

Những ca này minh họa cấu trúc công thức, không phải kết quả benchmark/mô phỏng Hà Nội.
Tất cả cận 10 phút đón và 7,5 phút extra ride vẫn phải kiểm độc lập; kinh tế đạt không thay điều kiện tuyến.

## 9. Giá biết trước, hủy và phần cần duyệt trước implement

Phương án A báo giá ngay lúc đặt. Phương án B phụ thuộc đối tác/xe/tuyến nên chưa có giá chính xác khi chỉ
có request A. Cần chọn một trong các semantics rõ trước khi dùng B trong engine:

1. Hiển thị một trần từ cước trực tiếp, chốt giá khi cặp và tuyến đã biết; trả lại phần giảm nếu giá cuối thấp hơn.
2. Chốt giá theo cặp rồi gửi offer và hỏi booking/acceptance lại trước commit.

Phương án 2 thay lifecycle/behavior và lớn hơn thay công thức fare. Không tự dùng book theo giá đi riêng
rồi tăng giá lúc tìm thấy đối tác. Không tái sử dụng slot legacy pool_accept để giải quyết.

Sau khi đã nhận cặp, giá mỗi người nên giữ cố định; đối tác hủy không tự tăng giá của người còn lại.
Nếu chưa ai onboard, giải cặp/tìm lại có thể đổi tổng payout khi commit cặp mới, nhưng không tăng trần đã hứa;
chốt cách lưu quote/pair history nếu chọn B. Đã có người onboard thì giữ chuyến và tính khoản thiếu như
trợ giá/ngoại lệ, không giả rằng có đủ hai cước hoặc tự ghép khách thứ ba.

Làm tròn phải giữ `p_A+p_B=R`, dùng ID ổn định phân bổ phần dư và kiểm lại trần sau làm tròn.
Không áp minimum fare của một chuyến Exclusive lần nữa lên từng phần shared, nếu điều đó phá mức giảm đã hứa.

Các quyết định đã chốt và phần nghiên cứu còn mở:

- **Đã chốt:** A với discount 30% riêng từng cước trực tiếp; không cần chia lại theo km/đoạn hoặc tổng tuyến.
- B/alpha=1,5 chỉ là phương án nghiên cứu; chưa triển khai hoặc thêm control vào V1.
- Sàn payout/chi phí, bonus pickup và cách xử lý thiếu ngân sách; cho trợ giá có giới hạn hay reject cặp?
- Nếu B, semantics quote/acceptance tại lúc đặt và lúc có cặp.

## 10. Kiểm chứng khi công thức được duyệt

- Ca bằng nhau 10→7; ca 60/40; route quá vòng làm B_raw đắt hơn; threshold đúng/sai quanh cận ngân sách.
- Tổng cước bằng hai phần sau rounding; từng phần không vượt trần; một người bị vòng không tự trả thêm.
- Snapshot lưu công thức/discount/alpha/weights và các quote/cost đã dùng; cùng seed/config cho cùng kết quả.
- Hủy trước/sau pickup, traffic đổi và cặp bị giải/tạo lại: không tăng cước đã nhận, không thu tiền khách chưa được phục vụ.
- Payout tính đúng một lần, không cộng thêm tiền shared qua surcharge legacy rồi lại tính payout trên toàn fare.
- GMV, payout, phí, trợ giá và chi phí được tách; lợi nhuận theo giờ và service rate cùng demand/seed;
  không coi giảm km vì hủy nhiều khách hơn là hiệu quả kinh tế tăng.
- Không giả sửa behavior giá bằng cách ghi đè fare sau khi booking đã quyết định với giá khác.

## 11. Lịch sử thay đổi

- 2026-10-09: khảo sát nguồn chính thức Grab/Uber/Green SM và nghiên cứu cost-sharing theo yêu cầu người dùng.
- 2026-10-09: phân biệt discount theo cước riêng với markup 1,5 trên tuyến chung; bổ sung counterexample,
  sàn payout và vấn đề quote trước khi biết đối tác. Chưa thay requirements/AC, chưa viết code V1.
- 2026-10-09: người dùng chọn A: mỗi khách Shared trả 70% cước đi riêng. Cập nhật requirements/plan/sprint
  về giá; chưa duyệt toàn bộ implementation plan, chưa viết code V1.
