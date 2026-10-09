import { visibleMetric } from "./runState";
const nf=new Intl.NumberFormat("vi-VN",{maximumFractionDigits:3});
const metricLabels:Record<string,string>={
  "platform.trips":"Chuyến hoàn thành", "platform.requests":"Yêu cầu đặt xe", "platform.gmv":"Tổng giá trị chuyến xe",
  "platform.revenue":"Doanh thu nền tảng", "rider.wait_mean":"Thời gian chờ trung bình", "rider.wait_p95":"Thời gian chờ P95",
  "rider.pickup_mean":"Thời gian đón trung bình", "rider.cancel_rate":"Tỷ lệ huỷ chuyến", "rider.completion_rate":"Tỷ lệ hoàn thành",
  "driver.utilization":"Hiệu suất sử dụng tài xế", "driver.earnings_per_hour":"Thu nhập tài xế mỗi giờ",
  "driver.online_hours":"Tổng giờ trực tuyến", "ops.vehicle_km":"Tổng quãng đường xe", "ops.empty_km":"Quãng đường xe trống",
  "ops.trips_per_vehicle_hour":"Số chuyến mỗi xe mỗi giờ",
};
const sharedLabels:Record<string,string>={requests:"Yêu cầu",booked:"Đã đặt",served:"Hoàn thành",cancelled:"Đã hủy",unfinished:"Còn dở",completion_rate:"Tỷ lệ hoàn thành",cancel_rate:"Tỷ lệ hủy",timeout:"Hết hạn đón",no_pair:"Hủy chưa từng có cặp",wait_mean:"Chờ trung bình",wait_p50:"Chờ P50",wait_p90:"Chờ P90",wait_p95:"Chờ P95",extra_ride_mean:"Tăng trên xe TB",extra_ride_p90:"Tăng trên xe P90",extra_ride_p95:"Tăng trên xe P95",predicted_extra_ride_mean:"Tăng trên xe dự kiến TB",pickup_violations:"Vi phạm hạn đón thực tế",extra_ride_violations:"Vi phạm tăng trên xe thực tế",gmv:"GMV",payout:"Thu nhập tài xế",platform_fee:"Phí nền tảng",reference_gmv:"Cước tham chiếu đi riêng",savings:"Tiết kiệm cước",partner_lost_served:"Hoàn thành sau mất đối tác"};
Object.assign(metricLabels,{"shared.planned_pairs":"Cặp đã tạo","shared.actual_pairs":"Cặp thực sự đi chung","shared.dissolved_pairs":"Cặp đã giải","shared.overlap_min":"Thời gian có hai khách","shared.predicted_overlap_min":"Thời gian hai khách dự kiến","shared.route_queries":"Truy vấn đường shared","shared.candidate_pairs":"Cặp ứng viên","shared.candidate_plans":"Tuyến ứng viên khả thi","shared.drivers_truncated":"Ứng viên xe bị cắt","shared.waiting_now":"Khách Shared đang chờ"});
export const metricLabel=(key:string)=>{
  const [ns,pref,name]=key.split(".");
  if(ns==="shared"&&(pref==="shared_only"||pref==="exclusive_only"))return (pref==="shared_only"?"Shared Only":"Exclusive Only")+" · "+(sharedLabels[name]??name);
  return metricLabels[key]??key;
};
export function formatMetric(value:number|null|undefined) { return value==null||!Number.isFinite(value)?"—":nf.format(value); }
export function metricUnit(name:string):string {
  if(/wait_(mean|p\d+)|pickup_mean|eta_error|travel_time_p\d+|idle_gap_mean|extra_ride_(mean|p\d+)|overlap_min/.test(name))return "phút";
  if(/gmv|revenue|margin|fare_mean|payout|platform_fee|savings/.test(name))return "VND";
  if(name==="driver.earnings_per_hour")return "VND/giờ";
  if(name==="driver.online_hours")return "giờ";
  if(["ops.vehicle_km","ops.empty_km"].includes(name))return "km";
  if(name==="ops.trips_per_vehicle_hour")return "chuyến/xe-giờ";
  if(/rate|share|utilization|conversion|gini|completion_min/.test(name))return "tỷ lệ";
  return "";
}
export function metricKeys(rows:Record<string,number|null>[]) { return [...new Set(rows.flatMap(r=>Object.keys(r)))].filter(k=>k!=="t"&&visibleMetric(k)).sort(); }
export const warnings:Record<string,string>={
  different_scenario:"Khác cấu hình kịch bản",unpaired_seed:"Seed/CRN không ghép cặp",different_fleet:"Khác cấu hình fleet hoặc loại xe",different_environment:"Khác phiên bản hoặc môi trường chạy",
};
export const verdictLabel={better:"Tốt hơn",worse:"Kém hơn",equal:"Bằng nhau"};
