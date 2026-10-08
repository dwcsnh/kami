"use client";
// Thin ECharts wrapper (modular import of echarts/core) with a theme from the design tokens.
import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";
import { tokens } from "@/design/tokens";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer]);

const c = tokens.color;
export const chartBase = {
  animation: false,
  textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: c["text-muted"], fontSize: 11 },
  grid: { left: 36, right: 10, top: 28, bottom: 22 },
  tooltip: {
    trigger: "axis" as const,
    backgroundColor: c.surface,
    borderColor: c.border,
    textStyle: { color: c.text, fontSize: 12 },
    extraCssText: "box-shadow: 0 4px 12px rgba(31,41,51,.08); border-radius: 8px;",
  },
  legend: { top: 0, left: 0, itemWidth: 10, itemHeight: 10, icon: "roundRect",
            textStyle: { color: c["text-muted"], fontSize: 11 } },
};
export const axisStyle = {
  axisLine: { lineStyle: { color: c.neutral["300"] } },
  axisTick: { show: false },
  axisLabel: { color: c["text-muted"], fontSize: 11 },
  splitLine: { lineStyle: { color: c.neutral["100"] } },
};

export function Chart({ option, height = 150, ariaLabel }: { option: echarts.EChartsCoreOption; height?: number; ariaLabel: string }) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    const inst = echarts.init(el.current!, undefined, { renderer: "canvas" });
    chart.current = inst;
    const ro = new ResizeObserver(() => inst.resize());
    ro.observe(el.current!);
    return () => {
      ro.disconnect();
      inst.dispose();
      chart.current = null;
    };
  }, []);
  useEffect(() => {
    chart.current?.setOption(option, { notMerge: false, lazyUpdate: true });
  }, [option]);
  return <div ref={el} role="img" aria-label={ariaLabel} style={{ width: "100%", height }} />;
}
