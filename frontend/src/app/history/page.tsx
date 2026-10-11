"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  CheckSquare2,
  Inbox,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
} from "lucide-react";

import EChart from "@/components/echart";
import MetricCard from "@/components/metric-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { api } from "@/lib/api";
import { fmtMs, fmtNum, fmtPct, fmtTps, timeAgo } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { saveLastConfig } from "@/lib/last-config";
import { STATUS_META } from "@/lib/task-status";
import type { TaskSummary } from "@/lib/types";

const PROTOCOL_LABEL: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Gemini",
};

export default function HistoryPage() {
  const router = useRouter();
  const { t: i18n, lang } = useI18n();
  const [tasks, setTasks] = React.useState<TaskSummary[]>([]);
  const [selected, setSelected] = React.useState<string[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  const [modeFilter, setModeFilter] = React.useState("all");
  const [modelQuery, setModelQuery] = React.useState("");
  const compareRef = React.useRef<HTMLDivElement>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setTasks(await api.listTasks());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const filtered = tasks.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (modeFilter !== "all" && t.config.mode !== modeFilter) return false;
    if (modelQuery && !t.model.toLowerCase().includes(modelQuery.toLowerCase())) return false;
    return true;
  });
  const selTasks = tasks.filter((t) => selected.includes(t.id));
  const allSelected =
    filtered.length > 0 &&
    filtered.every((t) => selected.includes(t.id));

  const toggle = (id: string) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : (s.length >= 6 ? s : [...s, id]),
    );

  const toggleAll = () =>
    setSelected((prev) => {
      const filteredIds = filtered.map((t) => t.id);
      const allIn = filteredIds.length > 0 && filteredIds.every((id) => prev.includes(id));
      if (allIn) return prev.filter((id) => !filteredIds.includes(id));
      const addable = filteredIds.filter((id) => !prev.includes(id)).slice(0, 6);
      return [...prev.filter((id) => !filteredIds.includes(id)), ...addable].slice(0, 6);
    });

  const remove = async (t: TaskSummary) => {
    try {
      await api.deleteTask(t.id);
      setTasks((ts) => ts.filter((x) => x.id !== t.id));
      setSelected((s) => s.filter((x) => x !== t.id));
    } catch (e) {
      setError(String(e));
    }
  };

  const retest = (t: TaskSummary) => {
    saveLastConfig(t.config);
    router.push("/");
  };

  const stats = React.useMemo(() => {
    const done = tasks.filter((t) => t.status === "done");
    const tps = done
      .map((t) => t.summary.throughput_tps)
      .filter((v): v is number => v != null && v > 0);
    return {
      total: tasks.length,
      done: done.length,
      running: tasks.filter((t) => t.status === "running" || t.status === "pending").length,
      avg: tps.length ? tps.reduce((a, b) => a + b, 0) / tps.length : null,
      max: tps.length ? Math.max(...tps) : null,
    };
  }, [tasks]);

  const compareOption = React.useMemo(() => {
    if (selTasks.length === 0) return null;
    const labels = selTasks.map((t, i) => `${t.model}${selTasks.length > 1 ? ` #${i + 1}` : ""}`);
    return {
      grid: { top: 36, left: 48, right: 48, bottom: 36 },
      tooltip: { trigger: "axis" },
      legend: { data: [i18n("history.legendThroughput"), i18n("history.legendTtft")], top: 0 },
      xAxis: { type: "category", data: labels },
      yAxis: [
        { type: "value", name: "tokens/s" },
        { type: "value", name: "ms" },
      ],
      series: [
        {
          name: i18n("history.legendThroughput"),
          type: "bar",
          data: selTasks.map((task) => task.summary.throughput_tps ?? 0),
          barWidth: "40%",
        },
        {
          name: i18n("history.legendTtft"),
          type: "line",
          yAxisIndex: 1,
          data: selTasks.map((task) => task.summary.ttft_ms?.avg ?? 0),
          symbol: "circle",
        },
      ],
    } as object;
  }, [selTasks, i18n]);

  const modeLabel = (mode: string) =>
    mode === "step"
      ? i18n("common.mode.step.short")
      : mode === "open"
        ? i18n("common.mode.open.short")
        : i18n("common.mode.fixed.short");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{i18n("history.title")}</h1>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className={loading ? "animate-spin" : ""} />
          {i18n("history.refresh")}
        </Button>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Input
            className="h-8 w-40"
            placeholder={i18n("history.filterModel")}
            value={modelQuery}
            onChange={(e) => setModelQuery(e.target.value)}
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-8 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{i18n("history.filterStatusAll")}</SelectItem>
              <SelectItem value="done">{i18n("common.status.done")}</SelectItem>
              <SelectItem value="running">{i18n("common.status.running")}</SelectItem>
              <SelectItem value="failed">{i18n("common.status.failed")}</SelectItem>
              <SelectItem value="cancelled">{i18n("common.status.cancelled")}</SelectItem>
              <SelectItem value="interrupted">{i18n("common.status.interrupted")}</SelectItem>
            </SelectContent>
          </Select>
          <Select value={modeFilter} onValueChange={setModeFilter}>
            <SelectTrigger className="h-8 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{i18n("history.filterModeAll")}</SelectItem>
              <SelectItem value="fixed">{i18n("common.mode.fixed.name")}</SelectItem>
              <SelectItem value="step">{i18n("common.mode.step.name")}</SelectItem>
              <SelectItem value="open">{i18n("common.mode.open.name")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {selected.length > 0 && (
          <span className="flex w-full items-center gap-2 text-xs text-muted-foreground sm:w-auto">
            {i18n("history.selected", { n: selected.length })}
            <button
              className="cursor-pointer font-medium text-primary hover:underline"
              onClick={() =>
                compareRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
              }
            >
              {i18n("history.compare")}
            </button>
            <button
              className="cursor-pointer hover:text-foreground hover:underline"
              onClick={() => setSelected([])}
            >
              {i18n("history.clear")}
            </button>
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label={i18n("history.stats.total")} value={String(stats.total)} />
        <MetricCard
          label={i18n("history.stats.done")}
          value={String(stats.done)}
          hint={stats.running ? i18n("history.stats.running", { n: stats.running }) : undefined}
          tone="success"
        />
        <MetricCard
          label={i18n("history.stats.avgTps")}
          value={stats.avg != null ? `${fmtTps(stats.avg)} t/s` : "—"}
        />
        <MetricCard
          label={i18n("history.stats.maxTps")}
          value={stats.max != null ? `${fmtTps(stats.max)} t/s` : "—"}
        />
      </div>

      {error ? (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <button
                    className="cursor-pointer text-muted-foreground hover:text-foreground"
                    onClick={toggleAll}
                    title={allSelected ? i18n("history.toggle.deselect") : i18n("history.toggle.select")}
                  >
                    {allSelected ? <CheckSquare2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                  </button>
                </TableHead>
                <TableHead>{i18n("history.col.model")}</TableHead>
                <TableHead>{i18n("history.col.protoMode")}</TableHead>
                <TableHead>{i18n("history.col.status")}</TableHead>
                <TableHead>{i18n("history.col.done")}</TableHead>
                <TableHead>{i18n("history.col.throughput")}</TableHead>
                <TableHead>{i18n("history.col.ttftAvg")}</TableHead>
                <TableHead>{i18n("history.col.tpotAvg")}</TableHead>
                <TableHead>{i18n("history.col.rps")}</TableHead>
                <TableHead>{i18n("history.col.errRate")}</TableHead>
                <TableHead>{i18n("history.col.created")}</TableHead>
                <TableHead className="w-24">{i18n("history.col.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 && !loading ? (
                <TableRow>
                  <TableCell colSpan={12} className="py-12">
                    <div className="flex flex-col items-center gap-3 text-center text-muted-foreground">
                      <Inbox className="h-8 w-8 text-muted-foreground/40" />
                      <div className="text-sm">
                        {tasks.length === 0
                          ? i18n("history.emptyNone")
                          : i18n("history.emptyFilter")}
                      </div>
                      {tasks.length === 0 ? (
                        <Button size="sm" onClick={() => router.push("/")}>
                          {i18n("history.newRun")}
                        </Button>
                      ) : null}
                    </div>
                  </TableCell>
                </TableRow>
              ) : null}
              {filtered.map((t) => {
                const done = t.summary.planned ? ((t.summary.completed ?? 0) / t.summary.planned) * 100 : 0;
                return (
                  <TableRow
                  key={t.id}
                  data-state={selected.includes(t.id) ? "selected" : undefined}
                  className="cursor-pointer"
                  title={i18n("history.row.view")}
                  onClick={() => router.push(`/monitor?id=${t.id}`)}
                >
                    <TableCell>
                      <button
                        className="cursor-pointer text-muted-foreground hover:text-foreground"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggle(t.id);
                        }}
                      >
                        {selected.includes(t.id) ? (
                          <CheckSquare2 className="h-4 w-4 text-primary" />
                        ) : (
                          <Square className="h-4 w-4" />
                        )}
                      </button>
                    </TableCell>
                    <TableCell className="max-w-44 truncate font-medium" title={t.model}>
                      {t.model}
                    </TableCell>
                    <TableCell>
                      <span className="text-xs text-muted-foreground">
                        {PROTOCOL_LABEL[t.protocol] ?? t.protocol} · {modeLabel(t.config.mode)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_META[t.status].variant}>
                        {i18n(STATUS_META[t.status].labelKey)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={done} className="h-1.5 w-16" />
                        <span className="text-xs tabular-nums text-muted-foreground">
                          {t.summary.completed ?? 0}/{t.summary.planned ?? 0}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>{fmtTps(t.summary.throughput_tps)}</TableCell>
                    <TableCell>{fmtMs(t.summary.ttft_ms?.avg)}</TableCell>
                    <TableCell>{fmtMs(t.summary.tpot_ms?.avg)}</TableCell>
                    <TableCell>{fmtNum(t.summary.rps)}</TableCell>
                    <TableCell>{fmtPct(t.summary.error_rate)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{timeAgo(t.created_at, lang)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <button
                          className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
                          onClick={(e) => {
                            e.stopPropagation();
                            retest(t);
                          }}
                          title={i18n("history.row.retest")}
                        >
                          <RotateCcw className="h-4 w-4" />
                        </button>
                        <button
                          className="inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                          onClick={(e) => {
                            e.stopPropagation();
                            void remove(t);
                          }}
                          title={i18n("history.row.delete")}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {selTasks.length > 0 && (
        <div ref={compareRef}>
          <Card>
          <CardHeader>
            <CardTitle className="text-sm">{i18n("history.compareTitle", { n: selTasks.length })}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-2">
              {compareOption ? <EChart option={compareOption} className="h-64" /> : null}
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{i18n("history.col.model")}</TableHead>
                      <TableHead>{i18n("history.col.pattern")}</TableHead>
                      <TableHead>{i18n("history.col.throughput")}</TableHead>
                      <TableHead>{i18n("history.col.tpsOut")}</TableHead>
                      <TableHead>{i18n("history.col.rps")}</TableHead>
                      <TableHead>{i18n("history.col.ttftAvgP95")}</TableHead>
                      <TableHead>{i18n("history.col.itl")}</TableHead>
                      <TableHead>{i18n("history.col.tpotAvg")}</TableHead>
                      <TableHead>{i18n("history.col.e2eAvg")}</TableHead>
                      <TableHead>{i18n("history.col.errRate")}</TableHead>
                      <TableHead>{i18n("history.col.recConc")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selTasks.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell className="max-w-40 truncate font-medium" title={t.model}>
                          {t.model}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {modeLabel(t.config.mode)}
                        </TableCell>
                        <TableCell>{fmtTps(t.summary.throughput_tps)}</TableCell>
                        <TableCell>{fmtTps(t.summary.output_tps)}</TableCell>
                        <TableCell>{fmtNum(t.summary.rps)}</TableCell>
                        <TableCell>
                          {fmtMs(t.summary.ttft_ms?.avg)} / {fmtMs(t.summary.ttft_ms?.p95)}
                        </TableCell>
                        <TableCell>{fmtMs(t.summary.itl_ms?.p50)}</TableCell>
                        <TableCell>{fmtMs(t.summary.tpot_ms?.avg)}</TableCell>
                        <TableCell>{fmtMs(t.summary.e2e_ms?.avg)}</TableCell>
                        <TableCell>{fmtPct(t.summary.error_rate)}</TableCell>
                        <TableCell>
                          {t.analysis?.recommended_concurrency != null ? (
                            <Badge variant="outline">
                              {t.analysis.recommended_concurrency}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </CardContent>
        </Card>
        </div>
      )}
    </div>
  );
}