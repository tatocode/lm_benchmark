"use client";

import * as echarts from "echarts";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

interface EChartProps {
  option: object;
  className?: string;
}

export default function EChart({ option, className }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = echarts.init(el, undefined, { renderer: "canvas" });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option as echarts.EChartsOption, { notMerge: true });
  }, [option]);

  return <div ref={containerRef} className={cn("h-72 w-full", className)} />;
}