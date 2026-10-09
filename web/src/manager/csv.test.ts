import { describe, expect, it } from "vitest";
import { comparisonCsv, csvCell, summaryCsv, timeseriesCsv } from "./csv";
import { formatMetric, metricUnit } from "./metricFormat";
describe("metric export",()=>{
  it("escapes CSV text and formulas while keeping real negative numbers numeric",()=>{
    expect(csvCell('Hà Nội,"A"\nB')).toBe('"Hà Nội,""A""\nB"');
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");expect(csvCell(-2)).toBe("-2");expect(csvCell(null)).toBe("");
  });
  it("exports raw precision, nulls, Unicode and omits legacy metrics",()=>{
    const text=summaryCsv({"rider.wait_mean":1.23456789,"rider.pool_rate":0,"x":null});
    expect(text.startsWith("\uFEFF")).toBe(true);expect(text).toContain("1.23456789");expect(text).not.toContain("pool_rate");
    expect(timeseriesCsv([{t:10,a:null},{t:20,a:2}])).toContain("10,\r\n20,2");
  });
  it("exports API comparison verdict and missing percent without recalculating",()=>{
    const text=comparisonCsv({baseline_id:1,comparisons:[{run_id:2,warnings:["unpaired_seed"],metrics:[{metric:"x",baseline:0,candidate:2,delta:2,delta_percent:null,direction:0,verdict:null}]}]});
    expect(text).toContain("1,2,unpaired_seed,x,0,2,2,,0,");
  });
  it("formats null as unavailable and labels existing engine units",()=>{
    expect(formatMetric(null)).toBe("—");expect(metricUnit("rider.wait_p90")).toBe("phút");expect(metricUnit("ops.vehicle_km")).toBe("km");expect(metricUnit("driver.earnings_per_hour")).toBe("VND/giờ");
  });
});
