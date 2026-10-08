"use client";
// S03-10: KPIs and charts synchronised with the displayed time. Values come from the engine's time series
// (metrics.json): the last row with t_row ≤ t. Vehicle-state shares come from the replay's state timeline.
import { useMemo } from "react";
import { bucketCounts, formatClock, type Replay } from "@/data/replay";
import { tokens } from "@/design/tokens";
import { usePlayback } from "@/store/playback";
import { useThrottledT } from "@/store/useClock";
import { IconButton, KpiCard, Panel } from "@/ui";
import { IconChart, IconChevronRight } from "@/ui/icons";
import { Chart, axisStyle, chartBase } from "./Chart";
import s from "./panels.module.css";

const nf = new Intl.NumberFormat("vi-VN");
const nf1 = new Intl.NumberFormat("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt1 = (x: number | null | undefined) => (x === null || x === undefined || Number.isNaN(x) ? "—" : nf1.format(x));
const BUCKET_S = 900;

export function MetricsPanel({ replay, colors }: { replay: Replay; colors: string[] }) {
  const open = usePlayback((x) => x.panelOpen);
  const setOpen = usePlayback((x) => x.setPanelOpen);
  const t = useThrottledT(250);
  const m = replay.metrics;

  const shareTimes = m.t;
  const shares = useMemo(() => replay.stateCounts(shareTimes), [replay, shareTimes]);
  const allBuckets = useMemo(() => bucketCounts(m, BUCKET_S).start, [m]);
  const row = replay.metricsAt(t);
  const r = replay.metricsRowAt(t);

  const barOption = useMemo(() => {
    const b = bucketCounts(m, BUCKET_S, t);
    const byStart = new Map(b.start.map((x, i) => [x, i]));
    const pick = (arr: number[]) => allBuckets.map((x) => (byStart.has(x) ? arr[byStart.get(x)!] : null));
    return {
      ...chartBase,
      xAxis: { type: "category", data: allBuckets.map((x) => formatClock(x, false)), ...axisStyle,
               splitLine: { show: false } },
      yAxis: { type: "value", minInterval: 1, ...axisStyle },
      series: [
        { name: "Hoàn thành", type: "bar", stack: "n", data: pick(b.completed), barMaxWidth: 18,
          itemStyle: { color: tokens.color.success, borderRadius: [0, 0, 0, 0] } },
        { name: "Hủy", type: "bar", stack: "n", data: pick(b.cancelled), barMaxWidth: 18,
          itemStyle: { color: tokens.color.danger, borderRadius: [3, 3, 0, 0] } },
      ],
      legend: { ...chartBase.legend, data: ["Hoàn thành", "Hủy"] },
    };
  }, [m, t, allBuckets]);

  const shareOption = useMemo(() => {
    const upto = r < 0 ? 0 : r + 1;
    const series = replay.states.map((st, i) => ({
      name: st.label, type: "line", stack: "share", symbol: "none", lineStyle: { width: 0 },
      areaStyle: { color: colors[i], opacity: 0.85 }, color: colors[i],
      data: shares.slice(0, upto).map((c, k) => {
        const tot = c.reduce((a, x) => a + x, 0);
        return [m.t[k], tot ? Math.round((1000 * c[i]) / tot) / 10 : 0];
      }),
    }));
    return {
      ...chartBase,
      legend: { show: false },
      tooltip: { ...chartBase.tooltip, valueFormatter: (v: number) => `${v}%` },
      xAxis: timeAxis(replay),
      yAxis: { type: "value", max: 100, ...axisStyle, axisLabel: { ...axisStyle.axisLabel, formatter: "{value}%" } },
      series: [...series, cursor(t)],
    };
  }, [replay, shares, colors, r, t, m]);

  const waitOption = useMemo(() => {
    const upto = r < 0 ? 0 : r + 1;
    const line = (name: string, key: string, color: string, dashed = false) => ({
      name, type: "line", symbol: "none", connectNulls: false, color,
      lineStyle: { width: 2, color, type: dashed ? "dashed" : "solid" },
      data: m.t.slice(0, upto).map((x, k) => [x, m.series[key]?.[k] ?? null]),
    });
    return {
      ...chartBase,
      tooltip: { ...chartBase.tooltip, valueFormatter: (v: number) => (v == null ? "—" : `${nf1.format(v)} phút`) },
      xAxis: timeAxis(replay),
      yAxis: { type: "value", ...axisStyle },
      series: [
        line("Chờ TB (đặt → đón)", "rider.wait_mean", tokens.color.primary),
        line("Đón TB (nhận → đón)", "rider.pickup_mean", tokens.color.neutral["600"], true),
        cursor(t),
      ],
      legend: { ...chartBase.legend, data: ["Chờ TB (đặt → đón)", "Đón TB (nhận → đón)"] },
    };
  }, [m, r, t, replay]);

  if (!open) {
    return (
      <div className={s.metricsCollapsed}>
        <IconButton label="Mở bảng metric" tooltipSide="top" onClick={() => setOpen(true)}><IconChart /></IconButton>
      </div>
    );
  }
  const val = (k: string) => (row ? row[k] : null);
  const win = `${(m.interval_s ?? 60) / 60} phút qua`;
  return (
    <Panel className={s.metrics} title="Chỉ số vận hành" aria-label="Chỉ số vận hành"
      actions={<IconButton label="Thu gọn bảng metric" variant="bare" onClick={() => setOpen(false)}><IconChevronRight /></IconButton>}>
      <div className={s.kpiGrid} data-testid="kpis">
        <KpiCard label="Đơn hoàn thành" value={<span data-kpi="completed">{nf.format(val("rider.completed_cum") ?? 0)}</span>}
          hint="luỹ kế" accent={tokens.color.success} />
        <KpiCard label="Đơn hủy" value={<span data-kpi="cancelled">{nf.format(val("rider.cancelled_cum") ?? 0)}</span>}
          hint="luỹ kế" accent={tokens.color.danger} />
        <KpiCard label="Thời gian đón TB" value={<span data-kpi="pickup">{fmt1(val("rider.pickup_mean"))}</span>} unit="phút"
          hint="nhận chuyến → đón" accent={tokens.color.neutral["600"]} />
        <KpiCard label="Thời gian chờ TB" value={<span data-kpi="wait">{fmt1(val("rider.wait_mean"))}</span>} unit="phút"
          hint="đặt xe → đón" accent={tokens.color.primary} />
      </div>
      <p className={s.kpiNote}>Thời gian TB của các lượt đón trong {win} (chuỗi metric của engine).</p>
      <div className={s.miniStats}>
        <span>Yêu cầu<b>{nf.format(val("rider.requests_cum") ?? 0)}</b></span>
        <span>Khách đang chờ<b>{nf.format(val("rider.waiting_now") ?? 0)}</b></span>
        <span>Xe bận<b>{val("driver.utilization_now") == null ? "—" : `${Math.round(100 * (val("driver.utilization_now") as number))}%`}</b></span>
      </div>
      <h3 className={s.chartTitle}>Đơn theo khung 15 phút <small>hoàn thành · hủy</small></h3>
      <Chart option={barOption} height={130} ariaLabel="Biểu đồ cột số đơn hoàn thành và hủy theo khung 15 phút" />
      <h3 className={s.chartTitle}>Tỷ lệ xe theo trạng thái <small>% xe đang hoạt động</small></h3>
      <Chart option={shareOption} height={120} ariaLabel="Biểu đồ miền tỷ lệ xe theo trạng thái theo thời gian" />
      <h3 className={s.chartTitle}>Thời gian chờ / đón của khách <small>phút, TB mỗi phút</small></h3>
      <Chart option={waitOption} height={140} ariaLabel="Biểu đồ đường thời gian chờ và đón trung bình" />
      <p style={{ fontSize: 11, color: tokens.color["text-muted"], margin: "8px 0 0" }}>
        Số liệu: chuỗi metric của engine tại {row ? formatClock(row.t as number) : "—"} (mốc gần nhất ≤ thời điểm đang xem).
      </p>
    </Panel>
  );
}

function timeAxis(replay: Replay) {
  const step = replay.end - replay.start > 3 * 3600 ? 3600 : 1800;
  return {
    type: "value", min: Math.floor(replay.start / step) * step, max: Math.ceil(replay.end / step) * step, interval: step,
    ...axisStyle, splitLine: { show: false },
    axisLabel: { ...axisStyle.axisLabel, formatter: (v: number) => formatClock(v, false) },
  };
}

function cursor(t: number) {
  return {
    name: "now", type: "line", data: [], silent: true, tooltip: { show: false },
    markLine: { symbol: "none", silent: true, animation: false, label: { show: false },
                lineStyle: { color: tokens.color.accent, width: 1.5, type: "solid" }, data: [{ xAxis: t }] },
  };
}
