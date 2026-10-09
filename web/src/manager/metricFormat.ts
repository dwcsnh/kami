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
export const metricLabel=(key:string)=>metricLabels[key]??key;
export function formatMetric(value:number|null|undefined) { return value==null||!Number.isFinite(value)?"—":nf.format(value); }
export function metricUnit(name:string):string {
  if(/wait_(mean|p\d+)|pickup_mean|eta_error|travel_time_p\d+|idle_gap_mean/.test(name))return "phút";
  if(/gmv|revenue|margin|fare_mean/.test(name))return "VND";
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
