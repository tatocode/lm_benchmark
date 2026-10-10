"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, BarChart3, ChevronDown, FileQuestion, Gauge, Loader2, RotateCcw, Sparkles, Square, Timer, TrendingUp, Zap } from "lucide-react";

import EChart from "@/components/echart";
import MetricCard from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { useSSE } from "@/hooks/use-sse";
import { api } from "@/lib/api";
import { fmtElapsed, fmtMs, fmtNum, fmtPct, fmtTps, timeAgo } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { TKey } from "@/lib/i18n";
import { saveLastConfig } from "@/lib/last-config";
import type {
  Analysis,
  RecordOut,
  SSEEvent,
  StepSummary,
  TaskConfig,
  TaskStatus,
} from "@/lib/types";
import { useTaskStore } from "@/store/use-task-store";

const TERMINAL: TaskStatus[] = ["done", "failed", "cancelled", "interrupted"];

const STATUS_META: Record<
  TaskStatus,
  { labelKey: TKey; variant: "success" | "warning" | "destructive" | "secondary" }
> = {
  pending: { labelKey: "common.status.pending", variant: "secondary" },
  running: { labelKey: "common.status.running", variant: "warning" },
  done: { labelKey: "common.status.done", variant: "success" },
  failed: { labelKey: "common.status.failed", variant: "destructive" },
  cancelled: { labelKey: "common.status.cancelled", variant: "secondary" },
  interrupted: { labelKey: "common.status.interrupted", variant: "secondary" },
};

function baseChart(extra: object) {
  return {
    grid: { top: 32, left: 44, right: 20, bottom: 28 },
    tooltip: { trigger: "axis" },
    ...extra,
  };
}

export default function MonitorInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { t } = useI18n();
  const taskId = searchParams.get("id") ?? "";
  const store = useTaskStore();
  const [taskMeta, setTaskMeta] = React.useState<{
    name: string;
    model: string;
    base_url: string;
    created_at: string;
  } | null>(null);
  const [lastConfig, setLastConfig] = React.useState<TaskConfig | null>(null);
  const [moreOpen, setMoreOpen] = React.useState(false);

  React.useEffect(() => {
    if (!taskId) return;
    store.reset(taskId);
    api
      .getTask(taskId)
      .then((t) => {
        setTaskMeta({
          name: t.name,
          model: t.model,
          base_url: t.base_url,
          created_at: t.created_at,
        });
        setLastConfig(t.config);
        store.mergeInitial({
          status: t.status,
          error: t.error,
          records: t.records,
          snapshot: t.summary as never,
          steps: t.steps,
          analysis: t.analysis,
        });
      })
      .catch((e) => store.setStatus("failed", String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId]);

  useSSE(
    taskId || null,
    (event: SSEEvent) => store.apply(event),
    taskId !== "" && !TERMINAL.includes(store.status),
  );

  const { status, error, records, snapshot, steps, throughput, analysis, autoStopReason } =
    store;
  const planned = snapshot?.planned ?? 0;
  const durationS = lastConfig
    ? lastConfig.mode === "step"
      ? lastConfig.step_duration_s * lastConfig.step_levels.length
      : lastConfig.fixed_duration_s
    : 0;
  const progress =
    planned > 0
      ? Math.round(((snapshot?.completed ?? 0) / planned) * 100)
      : durationS > 0
        ? Math.min(
            100,
            Math.round(((snapshot?.elapsed_s ?? 0) / durationS) * 100),
          )
        : 0;
  const isTerminal = TERMINAL.includes(status);
  const stepMode = steps.length > 0;

  const onCancel = async () => {
    if (!taskId || isTerminal) return;
    try {
      await api.cancelTask(taskId);
    } catch {
      /* ignore */
    }
  };

  const onRetest = () => {
    if (!lastConfig || !isTerminal) return;
    saveLastConfig(lastConfig);
    router.push("/");
  };

  const retestAtRecommended = () => {
    if (!lastConfig) return;
    const rec = analysis.ok ? analysis.recommended_concurrency ?? null : null;
    saveLastConfig({
      ...lastConfig,
      mode: "fixed",
      concurrency: rec ?? lastConfig.concurrency,
      fixed_duration_s: 0,
      total_requests: Math.max(20, lastConfig.total_requests || 20),
    });
    router.push("/");
  };

  const latencyOption = React.useMemo(() => {
    const ok = records.filter((r) => r.ttft_ms != null);
    const step = Math.max(1, Math.ceil(ok.length / 800));
    const taken = ok.filter((_, i) => i % step === 0);
    return baseChart({
      legend: { data: ["TTFT", "E2E", "TPOT"], top: 0 },
      xAxis: {
        type: "category",
        name: t("monitor.chart.timeS"),
        data: taken.map((r) => (r.t_end - (records[0]?.t_start ?? 0)).toFixed(1)),
        boundaryGap: false,
      },
      yAxis: { type: "value", name: "ms" },
      series: [
        {
          name: "TTFT",
          type: "line",
          data: taken.map((r) => r.ttft_ms as number),
          showSymbol: false,
          lineStyle: { width: 1.5 },
        },
        {
          name: "E2E",
          type: "line",
          data: taken.map((r) => r.e2e_ms as number),
          showSymbol: false,
          lineStyle: { width: 1.5 },
        },
        {
          name: "TPOT",
          type: "line",
          data: taken.map((r) => r.tpot_ms ?? 0),
          showSymbol: false,
          lineStyle: { width: 1.5 },
        },
      ],
    });
  }, [records, t]);

  const tpsOption = React.useMemo(
    () =>
      baseChart({
        legend: { data: [t("monitor.chart.windowTps")], top: 0 },
        xAxis: { type: "value", name: t("monitor.chart.sec") },
        yAxis: { type: "value", name: "tokens/s" },
        series: [
          {
            name: t("monitor.chart.windowTps"),
            type: "line",
            smooth: true,
            data: throughput.map((p) => [p.t, p.v]),
            symbol: "none",
            areaStyle: { opacity: 0.15 },
          },
        ],
      }),
    [throughput, t],
  );

  const histOption = React.useMemo(() => {
    const vals = records
      .filter((r) => r.status === "ok" && r.ttft_ms != null)
      .map((r) => r.ttft_ms as number);
    const bins = 30;
    const max = vals.length ? Math.max(...vals) : 1;
    if (max <= 0) return null;
    const counts = new Array(bins).fill(0);
    for (const v of vals)
      counts[Math.min(bins - 1, Math.floor((v / max) * bins))] += 1;
    const labels = counts.map((_, i) =>
      Math.round((max / bins) * (i + 0.5)),
    );
    return baseChart({
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value", name: t("monitor.chart.count") },
      series: [
        { name: t("monitor.chart.ttftDist"), type: "bar", data: counts, barWidth: "90%" },
      ],
    });
  }, [records, t]);

  const stepOption = React.useMemo(() => {
    if (!steps.length) return null;
    const rec = analysis.ok ? analysis.recommended_concurrency : null;
    const sat = analysis.ok ? analysis.saturation?.concurrency : null;
    const knee = analysis.ok ? analysis.knee?.concurrency : null;
    const slaMax = analysis.ok ? analysis.sla_max_concurrency : null;
    const marks: object[] = [];
    if (rec != null) {
      marks.push({
        xAxis: String(rec),
        label: {
          formatter: t("monitor.chart.markRec", { n: rec }),
          position: "insideEndTop",
          color: "#16a34a",
        },
        lineStyle: { color: "#16a34a", type: "solid" },
      });
    }
    if (sat != null && sat !== rec) {
      marks.push({
        xAxis: String(sat),
        label: {
          formatter: t("monitor.chart.markSat", { n: sat }),
          position: "insideEndTop",
          color: "#d97706",
        },
        lineStyle: { color: "#d97706", type: "dashed" },
      });
    }
    if (knee != null && knee !== rec && knee !== sat) {
      marks.push({
        xAxis: String(knee),
        label: {
          formatter: t("monitor.chart.markKnee", { n: knee }),
          position: "insideEndTop",
          color: "#dc2626",
        },
        lineStyle: { color: "#dc2626", type: "dashed" },
      });
    }
    if (slaMax != null && slaMax !== rec && slaMax !== sat && slaMax !== knee) {
      marks.push({
        xAxis: String(slaMax),
        label: {
          formatter: t("monitor.chart.markSla", { n: slaMax }),
          position: "insideEndBottom",
          color: "#2563eb",
        },
        lineStyle: { color: "#2563eb", type: "dotted" },
      });
    }
    return {
      grid: { top: 32, left: 44, right: 44, bottom: 28 },
      tooltip: { trigger: "axis" },
      legend: { data: [t("monitor.chart.throughput"), "RPS"], top: 0 },
      xAxis: {
        type: "category",
        data: steps.map((s) => String(s.concurrency)),
      },
      yAxis: [
        { type: "value", name: "tokens/s" },
        { type: "value", name: "req/s" },
      ],
      series: [
        {
          name: t("monitor.chart.throughput"),
          type: "bar",
          data: steps.map((s) => ({
            value: s.throughput_tps,
            itemStyle:
              rec != null && s.concurrency === rec
                ? { color: "#16a34a" }
                : sat != null && s.concurrency === sat
                  ? { color: "#d97706" }
                  : undefined,
          })),
          barWidth: "50%",
          markLine: marks.length ? { symbol: "none", data: marks } : undefined,
        },
        {
          name: "RPS",
          type: "line",
          yAxisIndex: 1,
          data: steps.map((s) => s.rps),
          symbol: "circle",
        },
      ],
    };
  }, [steps, analysis, t]);

  const recent = React.useMemo(() => records.slice(-300).reverse(), [records]);

  const chips = React.useMemo<[string, string][]>(() => {
    const c = lastConfig;
    if (!c) return [];
    const modeLabel =
      c.mode === "step"
        ? t("common.mode.step.short")
        : c.mode === "open"
          ? t("common.mode.open.short")
          : t("common.mode.fixed.short");
    const pressure =
      c.mode === "step"
        ? t("monitor.pressureStep", { levels: c.step_levels.join("→") })
        : c.mode === "open"
          ? t("monitor.pressureOpen", { rate: c.arrival_rate })
          : t("monitor.pressureFixed", { n: c.concurrency });
    const quantity =
      c.mode === "step"
        ? c.step_duration_s > 0
          ? t("monitor.qtyStepDur", { dur: c.step_duration_s, n: c.step_levels.length })
          : t("monitor.qtyStepReq", { req: c.step_requests, n: c.step_levels.length })
        : c.fixed_duration_s > 0
          ? t("monitor.qtyFixed", { dur: c.fixed_duration_s })
          : t("monitor.qtyTotal", { n: c.total_requests });
    return [
      [t("monitor.chip.mode"), modeLabel],
      [t("monitor.chip.pressure"), pressure],
      [t("monitor.chip.load"), quantity],
      [t("monitor.chip.io"), `${c.input_tokens}/${c.max_output_tokens} tok`],
      [t("monitor.chip.timeout"), `${c.timeout}s`],
      [t("monitor.chip.autoStop"), c.auto_stop ? t("monitor.on") : t("monitor.off")],
    ];
  }, [lastConfig, t]);

  if (!taskId) {
    return (
      <Card className="mx-auto max-w-md">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <FileQuestion className="h-9 w-9 text-muted-foreground/50" />
          <div className="space-y-1">
            <div className="text-sm font-medium">{t("monitor.missingId")}</div>
            <p className="text-xs text-muted-foreground">{t("monitor.missingIdHint")}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => router.push("/")}>
              {t("monitor.newRun")}
            </Button>
            <Button variant="outline" size="sm" onClick={() => router.push("/history")}>
              {t("monitor.viewHistory")}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Link
            href="/history"
            className="mt-1 inline-flex shrink-0 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("monitor.back")}
          </Link>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-xl font-semibold tracking-tight">
                {taskMeta?.model ?? (taskId ? "…" : t("monitor.missingId"))}
              </h1>
              <Badge variant={STATUS_META[status].variant}>
                {t(STATUS_META[status].labelKey)}
              </Badge>
              {status === "running" ? (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              ) : null}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {t("monitor.created", {
                base: taskMeta?.base_url || "",
                time: timeAgo(taskMeta?.created_at ?? ""),
              })}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isTerminal && lastConfig ? (
            <Button variant="outline" size="sm" onClick={onRetest}>
              <RotateCcw />
              {t("monitor.retest")}
            </Button>
          ) : null}
          {!isTerminal && (
            <Button variant="destructive" size="sm" onClick={onCancel}>
              <Square />
              {t("monitor.cancel")}
            </Button>
          )}
        </div>
      </div>

      {chips.length ? (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">{t("monitor.config")}</span>
          {chips.map(([k, v]) => (
            <span
              key={k}
              className="inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-1 shadow-sm"
            >
              <span className="text-muted-foreground">{k}</span>
              <span className="num font-medium text-foreground">{v}</span>
            </span>
          ))}
        </div>
      ) : null}

      {error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">
            {error}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="text-muted-foreground">
                  {planned > 0 ? (
                    <>
                      <span className="num font-medium text-foreground">
                        {snapshot?.completed ?? 0}
                      </span>{" "}
                      / <span className="num">{planned}</span> {t("monitor.progressCount")}
                    </>
                  ) : (
                    <>
                      {t("monitor.progressDone")}{" "}
                      <span className="num font-medium text-foreground">
                        {snapshot?.completed ?? 0}
                      </span>{" "}
                      {t("monitor.progressDoneN")}
                      {durationS > 0 ? t("monitor.progressPlanned", { dur: durationS }) : ""}
                    </>
                  )}
                  {snapshot?.in_flight
                    ? t("monitor.progressFlight", { n: snapshot.in_flight })
                    : null}
                </span>
                <div className="flex items-center gap-2">
                  {stepMode && snapshot?.current_step ? (
                    <Badge variant="warning" className="num">
                      {t("monitor.stepBadge", {
                        cur: snapshot.current_step.index + 1,
                        total: lastConfig?.step_levels.length || steps.length,
                        c: snapshot.current_step.concurrency,
                      })}
                    </Badge>
                  ) : null}
                  <span className="num text-sm font-medium text-muted-foreground">
                    {progress}%
                  </span>
                </div>
              </div>
              <Progress value={progress} className="mt-2 h-2.5" />
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <div className="text-xs text-muted-foreground">{t("monitor.elapsed")}</div>
                <div className="num text-sm font-semibold">
                  {fmtElapsed(snapshot?.elapsed_s)}
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-muted-foreground">{t("monitor.liveTps")}</div>
                <div className="num text-sm font-semibold">
                  {fmtTps(snapshot?.window_tps)}{" "}
                  <span className="text-xs font-normal text-muted-foreground">t/s</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {autoStopReason ? (
        <Card className="border-warning/40 bg-warning/5">
          <CardContent className="p-3 text-sm">
            {autoStopReason === "saturation"
              ? t("monitor.autoStopSat")
              : t("monitor.autoStop", { reason: autoStopReason })}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard
          label={t("monitor.metric.outTps")}
          value={`${fmtTps(snapshot?.output_tps)} t/s`}
          icon={<Zap className="h-4 w-4 text-chart-1" />}
          hint={t("monitor.metric.outTpsHint", {
            v: fmtTps(snapshot?.throughput_tps),
            i: fmtTps(snapshot?.input_tps),
          })}
        />
        <MetricCard
          label={t("monitor.metric.ttft")}
          value={fmtMs(snapshot?.ttft_ms?.p95)}
          hint={t("monitor.metric.ttftHint", {
            v: fmtMs(snapshot?.ttft_ms?.avg),
            p: fmtMs(snapshot?.ttft_ms?.p99),
          })}
        />
        <MetricCard
          label={t("monitor.metric.err")}
          value={fmtPct(snapshot?.error_rate)}
          hint={
            snapshot?.error_breakdown &&
            Object.keys(snapshot.error_breakdown).length
              ? Object.entries(snapshot.error_breakdown)
                  .map(([k, v]) => `${k}:${v}`)
                  .join(" · ")
              : t("monitor.metric.errHint", { n: snapshot?.errors ?? 0 })
          }
          tone={snapshot?.errors ? "danger" : "success"}
        />
        <MetricCard
          label={t("monitor.metric.rps")}
          value={`${fmtNum(snapshot?.window_rps)} r/s`}
          icon={<Gauge className="h-4 w-4 text-chart-2" />}
          hint={t("monitor.metric.rpsHint", { v: fmtNum(snapshot?.rps) })}
        />
      </div>

      <div>
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground shadow-sm transition-colors hover:bg-accent hover:text-foreground"
          aria-expanded={moreOpen}
        >
          <ChevronDown
            className={`h-3.5 w-3.5 transition-transform ${moreOpen ? "rotate-180" : ""}`}
          />
          {t("monitor.more")}
        </button>
        {moreOpen ? (
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <MetricCard
              label={t("monitor.metric.tpot")}
              value={fmtMs(snapshot?.tpot_ms?.avg)}
              hint={t("monitor.metric.tpotHint", {
                v: fmtMs(snapshot?.tpot_ms?.p95),
                p: fmtMs(snapshot?.tpot_ms?.p99),
              })}
            />
            <MetricCard
              label={t("monitor.metric.e2e")}
              value={fmtMs(snapshot?.e2e_ms?.avg)}
              hint={t("monitor.metric.e2eHint", {
                v: fmtMs(snapshot?.e2e_ms?.p95),
                p: fmtMs(snapshot?.e2e_ms?.p99),
              })}
            />
            <MetricCard
              label={t("monitor.metric.itl")}
              value={fmtMs(snapshot?.itl_ms?.p50)}
              hint={t("monitor.metric.itlHint", { v: fmtMs(snapshot?.itl_ms?.p95) })}
            />
            <MetricCard
              label={t("monitor.metric.tokens")}
              value={fmtNum(snapshot?.tokens_total)}
              hint={t("monitor.metric.tokensHint", {
                i: fmtNum(snapshot?.input_tokens_total),
              })}
            />
            <MetricCard
              label={t("monitor.metric.live")}
              value={`${fmtTps(snapshot?.window_tps)} t/s`}
              hint={t("monitor.metric.liveHint")}
            />
          </div>
        ) : null}
      </div>

      {analysis.ok && isTerminal ? (
        <AnalysisReport a={analysis} onRetest={retestAtRecommended} />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {stepMode ? (
          <Card className="border-primary/30">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <TrendingUp className="h-4 w-4 text-primary" />
                {t("monitor.chart.stepTitle")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {stepOption ? (
                <EChart option={stepOption} />
              ) : (
                <EmptyChart text={t("monitor.chart.empty1")} />
              )}
            </CardContent>
          </Card>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Timer className="h-4 w-4 text-muted-foreground" />
              {t("monitor.chart.latencyTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <EChart option={latencyOption} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Zap className="h-4 w-4 text-muted-foreground" />
              {t("monitor.chart.liveTitle")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <EChart option={tpsOption} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("monitor.chart.histTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            {histOption ? (
              <EChart option={histOption} />
            ) : (
              <EmptyChart text={t("monitor.chart.empty0")} />
            )}
          </CardContent>
        </Card>
      </div>

      {stepMode && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{t("monitor.table.stepsTitle")}</CardTitle>
          </CardHeader>
          <CardContent>
            <StepsTable
              steps={steps}
              recommended={analysis.ok ? (analysis.recommended_concurrency ?? null) : null}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            {t("monitor.table.logTitle")}{" "}
            <span className="ml-1 font-normal text-muted-foreground">
              {t("monitor.table.logRecent", { a: recent.length, b: records.length })}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="max-h-96 overflow-y-auto">
          <RecordTable records={recent} />
        </CardContent>
      </Card>
    </div>
  );
}

const CONF_META: Record<
  Analysis["confidence"],
  { labelKey: TKey; variant: "success" | "warning" | "secondary" }
> = {
  high: { labelKey: "monitor.conf.high", variant: "success" },
  medium: { labelKey: "monitor.conf.medium", variant: "warning" },
  low: { labelKey: "monitor.conf.low", variant: "secondary" },
};

function AnalysisStat({
  label,
  value,
  hint,
  strong,
}: {
  label: string;
  value: string;
  hint?: string;
  strong?: boolean;
}) {
  return (
    <div className="rounded-lg border bg-background/60 p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          strong
            ? "num mt-1 text-2xl font-semibold text-primary"
            : "num mt-1 text-lg font-semibold"
        }
      >
        {value}
      </div>
      {hint ? <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div> : null}
    </div>
  );
}

function AnalysisReport({
  a,
  onRetest,
}: {
  a: Partial<Analysis>;
  onRetest: () => void;
}) {
  const { t } = useI18n();
  if (!a.ok || !a.single || !a.max_throughput) return null;
  const stopLabel = !a.stop_reason
    ? t("monitor.analysis.stops.all")
    : a.stop_reason === "saturation"
      ? t("monitor.analysis.stops.saturation")
      : a.stop_reason === "error_rate"
        ? t("monitor.analysis.stops.error_rate")
        : a.stop_reason;
  const sat = a.saturation;
  return (
    <Card className="border-primary/40 bg-primary/5">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
          <Sparkles className="h-4 w-4 text-primary" />
          {t("monitor.analysis.title")}
          <Badge variant={CONF_META[a.confidence ?? "low"].variant}>
            {t(CONF_META[a.confidence ?? "low"].labelKey)}
          </Badge>
          <Badge variant="secondary">{stopLabel}</Badge>
          <span className="ml-auto font-normal text-muted-foreground">
            {t("monitor.analysis.slaLine", {
              ttft: a.sla?.ttft_p95_s ?? "",
              e2e: a.sla?.e2e_p95_s ?? "",
              rate: (100 * (a.sla?.error_rate ?? 0.005)).toFixed(2),
            })}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-primary/30 bg-background/70 p-4">
            <div className="text-xs text-muted-foreground">{t("monitor.analysis.rec")}</div>
            <div className="num mt-1 text-3xl font-semibold text-primary">
              {a.recommended_concurrency != null ? a.recommended_concurrency : "—"}
              <span className="ml-1 text-base font-normal text-muted-foreground">
                {t("monitor.analysis.recUnit")}
              </span>
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {t("monitor.analysis.recHint")}
            </div>
          </div>
          <div className="rounded-xl border bg-background/70 p-4">
            <div className="text-xs text-muted-foreground">{t("monitor.analysis.maxRps")}</div>
            <div className="num mt-1 text-3xl font-semibold">
              {a.max_sustainable_rps != null ? fmtNum(a.max_sustainable_rps) : "—"}
              <span className="ml-1 text-base font-normal text-muted-foreground">req/s</span>
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              {t("monitor.analysis.maxRpsHint")}
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <AnalysisStat
            label={t("monitor.analysis.single")}
            value={`${fmtTps(a.single.output_tps)} t/s`}
            hint={`${a.single.concurrency} ${t("monitor.conn")} · TTFT P95 ${fmtMs(a.single.ttft_p95_ms)}`}
          />
          <AnalysisStat
            label={t("monitor.analysis.maxTp")}
            value={`${fmtTps(a.max_throughput.output_tps)} t/s`}
            hint={`${a.max_throughput.concurrency} ${t("monitor.conn")} · ${fmtNum(a.max_throughput.rps)} r/s`}
          />
          <AnalysisStat
            label={t("monitor.analysis.sat")}
            value={
              sat?.concurrency != null
                ? `${sat.concurrency} ${t("monitor.conn")}`
                : t("monitor.analysis.satNone")
            }
            hint={
              sat?.range
                ? t("monitor.analysis.satHint", { a: sat.range[0], b: sat.range[1] })
                : t("monitor.analysis.satRising")
            }
          />
          <AnalysisStat
            label={t("monitor.analysis.knee")}
            value={
              a.knee?.concurrency != null
                ? `${a.knee.concurrency} ${t("monitor.conn")}`
                : t("monitor.analysis.kneeNone")
            }
            hint={t("monitor.analysis.kneeHint")}
          />
          <AnalysisStat
            label={t("monitor.analysis.slaMax")}
            value={
              a.sla_max_concurrency != null
                ? `${a.sla_max_concurrency} ${t("monitor.conn")}`
                : t("monitor.analysis.slaMaxNone")
            }
            hint={t("monitor.analysis.slaMaxHint")}
          />
          <AnalysisStat
            label={t("monitor.analysis.levels")}
            value={`${a.single.concurrency ?? "-"} → ${a.max_throughput.concurrency ?? "-"} ${t("monitor.conn")}`}
            hint={t("monitor.analysis.levelsHint", { n: a.sla_max_concurrency ?? "—" })}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">{t("monitor.analysis.footer")}</p>
          <Button variant="outline" size="sm" onClick={onRetest}>
            <RotateCcw className="h-3.5 w-3.5" />
            {t("monitor.analysis.retest")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyChart({ text }: { text: string }) {
  return (
    <div className="flex h-72 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
      <BarChart3 className="h-8 w-8 text-muted-foreground/40" />
      {text}
    </div>
  );
}

function StatusDot({ status }: { status: RecordOut["status"] }) {
  const map: Record<RecordOut["status"], string> = {
    ok: "bg-success",
    error: "bg-destructive",
    timeout: "bg-warning",
    cancelled: "bg-muted-foreground",
  };
  return (
    <span className={`inline-block h-2 w-2 rounded-full ${map[status]}`} />
  );
}

function RecordTable({ records }: { records: RecordOut[] }) {
  const { t } = useI18n();
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">#</TableHead>
          <TableHead className="w-14">{t("monitor.table.level")}</TableHead>
          <TableHead className="w-16">{t("monitor.table.status")}</TableHead>
          <TableHead>TTFT</TableHead>
          <TableHead>E2E</TableHead>
          <TableHead>TPOT</TableHead>
          <TableHead>ITL P50</TableHead>
          <TableHead>Tok/s</TableHead>
          <TableHead>{t("monitor.table.out")}</TableHead>
          <TableHead>{t("monitor.table.in")}</TableHead>
          <TableHead className="min-w-40">{t("monitor.table.err")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {records.map((r) => (
          <TableRow key={r.idx}>
            <TableCell className="text-muted-foreground">{r.idx}</TableCell>
            <TableCell>{r.step >= 0 ? r.step : "-"}</TableCell>
            <TableCell>
              <span className="inline-flex items-center gap-1.5">
                <StatusDot status={r.status} />
                {r.status}
              </span>
            </TableCell>
            <TableCell>{fmtMs(r.ttft_ms)}</TableCell>
            <TableCell>{fmtMs(r.e2e_ms)}</TableCell>
            <TableCell>{fmtMs(r.tpot_ms)}</TableCell>
            <TableCell>{fmtMs(r.itl_p50_ms)}</TableCell>
            <TableCell>{fmtNum(r.tok_per_s)}</TableCell>
            <TableCell>{r.output_tokens}</TableCell>
            <TableCell>{r.input_tokens || "-"}</TableCell>
            <TableCell
              className="max-w-56 truncate text-muted-foreground"
              title={r.error}
            >
              {r.error_class && r.error_class !== "ok"
                ? r.error_class
                : r.error}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function StepsTable({
  steps,
  recommended,
}: {
  steps: StepSummary[];
  recommended: number | null;
}) {
  const { t } = useI18n();
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("monitor.table.conc")}</TableHead>
            <TableHead>{t("monitor.table.req")}</TableHead>
            <TableHead>{t("monitor.table.done")}</TableHead>
            <TableHead>{t("monitor.table.tpsThr")}</TableHead>
            <TableHead>{t("monitor.table.tpsOut")}</TableHead>
            <TableHead>{t("monitor.table.tpsIn")}</TableHead>
            <TableHead>RPS</TableHead>
            <TableHead>TTFT P95</TableHead>
            <TableHead>E2E P95</TableHead>
            <TableHead>TPOT P95</TableHead>
            <TableHead>ITL P50</TableHead>
            <TableHead>{t("monitor.table.errRate")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {steps.map((s) => {
            const isRec = recommended != null && s.concurrency === recommended;
            return (
              <TableRow
                key={s.concurrency}
                className={isRec ? "bg-primary/5 font-medium" : undefined}
              >
                <TableCell>
                  <span className="inline-flex items-center gap-1.5">
                    {s.concurrency}
                    {isRec ? (
                      <Badge variant="outline" className="border-primary/50 text-primary">
                        {t("monitor.table.rec")}
                      </Badge>
                    ) : null}
                  </span>
                </TableCell>
                <TableCell>{s.planned}</TableCell>
                <TableCell>{s.completed}</TableCell>
                <TableCell>{fmtTps(s.throughput_tps)}</TableCell>
                <TableCell>{fmtTps(s.output_tps)}</TableCell>
                <TableCell>{fmtTps(s.input_tps)}</TableCell>
                <TableCell>{fmtNum(s.rps)}</TableCell>
                <TableCell>{fmtMs(s.ttft_p95)}</TableCell>
                <TableCell>{fmtMs(s.e2e_p95)}</TableCell>
                <TableCell>{fmtMs(s.tpot_p95)}</TableCell>
                <TableCell>{fmtMs(s.itl_p50)}</TableCell>
                <TableCell
                  className={
                    s.error_breakdown && Object.keys(s.error_breakdown).length
                      ? "text-destructive"
                      : undefined
                  }
                >
                  {fmtPct(s.error_rate)}
                  {s.error_breakdown && Object.keys(s.error_breakdown).length
                    ? ` (${
                        Object.entries(s.error_breakdown)
                          .map(([k, v]) => `${k}:${v}`)
                          .join(", ") || s.errors
                      })`
                    : ""}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}