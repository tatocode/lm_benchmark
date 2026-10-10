"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertCircle,
  Bookmark,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  Flame,
  Gauge,
  Loader2,
  Plug,
  RefreshCw,
  Rocket,
  Save,
  Trash2,
  Waves,
  XCircle,
} from "lucide-react";

import { InfoTip } from "@/components/info-tip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ImagePicker } from "@/components/image-picker";
import { ModelCombobox } from "@/components/model-combobox";
import { QuestionPicker } from "@/components/question-picker";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TKey } from "@/lib/i18n";
import { loadLastConfig, removeLastConfig } from "@/lib/last-config";
import { cn } from "@/lib/utils";
import type { ProbeResult, Protocol, TaskConfig, TaskMode } from "@/lib/types";

const PRESET_INPUTS = [256, 512, 2048, 8192];

const PARAM_KEYS = new Set<keyof TaskConfig>([
  "mode",
  "concurrency",
  "total_requests",
  "step_levels",
  "step_requests",
  "arrival_rate",
  "fixed_duration_s",
  "step_duration_s",
  "auto_stop",
  "input_tokens",
  "max_output_tokens",
  "with_image",
  "image_id",
  "questions",
]);

const PROTOCOL_META: Record<
  Protocol,
  { labelKey: TKey; defaultBase: string; basePlaceholder: string; keyLabel: string }
> = {
  openai: {
    labelKey: "common.protocol.openai",
    defaultBase: "https://api.openai.com/v1",
    basePlaceholder: "https://api.openai.com/v1",
    keyLabel: "API Key",
  },
  anthropic: {
    labelKey: "common.protocol.anthropic",
    defaultBase: "https://api.anthropic.com",
    basePlaceholder: "https://api.anthropic.com",
    keyLabel: "x-api-key",
  },
  gemini: {
    labelKey: "common.protocol.gemini",
    defaultBase: "https://generativelanguage.googleapis.com",
    basePlaceholder: "https://generativelanguage.googleapis.com",
    keyLabel: "API Key",
  },
};

const MODE_META: Record<
  TaskMode,
  { nameKey: TKey; taglineKey: TKey; goalKey: TKey }
> = {
  fixed: {
    nameKey: "common.mode.fixed.name",
    taglineKey: "common.mode.fixed.tagline",
    goalKey: "common.mode.fixed.goal",
  },
  step: {
    nameKey: "common.mode.step.name",
    taglineKey: "common.mode.step.tagline",
    goalKey: "common.mode.step.goal",
  },
  open: {
    nameKey: "common.mode.open.name",
    taglineKey: "common.mode.open.tagline",
    goalKey: "common.mode.open.goal",
  },
};

interface Scene {
  id: string;
  nameKey: TKey;
  tagKey: TKey;
  descKey: TKey;
  icon: React.ReactNode;
  patch: Partial<TaskConfig>;
}

const SCENES: Scene[] = [
  {
    id: "quick",
    nameKey: "home.scene.quick.name",
    tagKey: "home.scene.quick.tag",
    descKey: "home.scene.quick.desc",
    icon: <Activity className="h-4 w-4" />,
    patch: {
      mode: "fixed",
      concurrency: 1,
      total_requests: 10,
      fixed_duration_s: 0,
      step_levels: [1, 2, 4, 8, 16],
      step_requests: 10,
      step_duration_s: 0,
      arrival_rate: 10,
      auto_stop: true,
      input_tokens: 512,
      max_output_tokens: 256,
    },
  },
  {
    id: "ramp",
    nameKey: "home.scene.ramp.name",
    tagKey: "home.scene.ramp.tag",
    descKey: "home.scene.ramp.desc",
    icon: <Gauge className="h-4 w-4" />,
    patch: {
      mode: "step",
      step_levels: [1, 2, 4, 8, 16],
      step_requests: 10,
      step_duration_s: 0,
      auto_stop: true,
      concurrency: 4,
      total_requests: 20,
      fixed_duration_s: 0,
      arrival_rate: 10,
      input_tokens: 512,
      max_output_tokens: 256,
    },
  },
  {
    id: "peak",
    nameKey: "home.scene.peak.name",
    tagKey: "home.scene.peak.tag",
    descKey: "home.scene.peak.desc",
    icon: <Flame className="h-4 w-4" />,
    patch: {
      mode: "step",
      step_levels: [1, 2, 4, 8, 16, 32, 64],
      step_requests: 8,
      step_duration_s: 0,
      auto_stop: true,
      concurrency: 4,
      total_requests: 20,
      fixed_duration_s: 0,
      arrival_rate: 10,
      input_tokens: 512,
      max_output_tokens: 256,
    },
  },
  {
    id: "flow",
    nameKey: "home.scene.flow.name",
    tagKey: "home.scene.flow.tag",
    descKey: "home.scene.flow.desc",
    icon: <Waves className="h-4 w-4" />,
    patch: {
      mode: "open",
      arrival_rate: 10,
      total_requests: 60,
      fixed_duration_s: 0,
      concurrency: 8,
      step_levels: [1, 2, 4, 8, 16],
      step_requests: 10,
      step_duration_s: 0,
      auto_stop: true,
      input_tokens: 512,
      max_output_tokens: 256,
    },
  },
];

function defaultConfig(): TaskConfig {
  return {
    protocol: "openai",
    base_url: PROTOCOL_META.openai.defaultBase,
    api_key: "",
    model: "",
    mode: "fixed",
    concurrency: 4,
    total_requests: 20,
    step_levels: [1, 2, 4, 8, 16],
    step_requests: 10,
    arrival_rate: 10,
    fixed_duration_s: 0,
    step_duration_s: 0,
    auto_stop: true,
    sla_ttft_p95_s: 2,
    sla_e2e_p95_s: 15,
    sla_error_rate: 0.005,
    input_tokens: 512,
    max_output_tokens: 256,
    timeout: 120,
    with_image: false,
    image_id: "",
    questions: [],
  };
}

function StepBadge({ n, done }: { n: number; done?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
        done
          ? "border-transparent bg-primary text-primary-foreground"
          : "border-border bg-background text-muted-foreground",
      )}
    >
      {done ? <Check className="h-3.5 w-3.5" /> : n}
    </span>
  );
}

function StepCard({
  n,
  title,
  desc,
  done,
  action,
  children,
}: {
  n: number;
  title: string;
  desc?: string;
  done?: boolean;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-start gap-3 space-y-0 border-b bg-muted/30 py-3">
        <StepBadge n={n} done={done} />
        <div className="min-w-0 flex-1">
          <CardTitle className="text-base">{title}</CardTitle>
          {desc ? (
            <CardDescription className="mt-0.5 text-xs">{desc}</CardDescription>
          ) : null}
        </div>
        {action}
      </CardHeader>
      <CardContent className="space-y-4 pt-4">{children}</CardContent>
    </Card>
  );
}

function Field({
  label,
  tip,
  hint,
  children,
  className,
}: {
  label: string;
  tip?: React.ReactNode;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center gap-1">
        <Label>{label}</Label>
        {tip ? <InfoTip>{tip}</InfoTip> : null}
      </div>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function SummaryChip({
  label,
  value,
  muted,
  onClick,
  disabled,
}: {
  label: string;
  value: React.ReactNode;
  muted?: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  const inner = (
    <>
      <div className="text-[11px] text-muted-foreground">
        {label}
        {onClick ? <span className="ml-1 text-primary">↻</span> : null}
      </div>
      <div
        className={cn(
          "num mt-0.5 text-sm font-medium",
          muted && "font-normal text-muted-foreground",
        )}
      >
        {value}
      </div>
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className="cursor-pointer rounded-lg border bg-muted/40 px-3 py-2 text-left transition-colors hover:border-primary/50 hover:bg-accent/50 disabled:cursor-default"
      >
        {inner}
      </button>
    );
  }
  return <div className="rounded-lg border bg-muted/40 px-3 py-2">{inner}</div>;
}

function GuideSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="mb-1 text-sm font-medium">{title}</div>
      <div className="text-xs leading-relaxed text-muted-foreground">{children}</div>
    </div>
  );
}

export default function NewTestPage() {
  const router = useRouter();
  const { t, tr } = useI18n();
  const [cfg, setCfg] = React.useState<TaskConfig>(defaultConfig);
  const [samples, setSamples] = React.useState<{ text: string[]; vision: string[] } | null>(null);
  const defaultQuestions = (withImage: boolean) =>
    samples ? (withImage ? samples.vision : samples.text) : [];
  const [probe, setProbe] = React.useState<ProbeResult | null>(null);
  const [probing, setProbing] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState("");
  const [presets, setPresets] = React.useState<Awaited<ReturnType<typeof api.listPresets>>>([]);
  const [presetDialog, setPresetDialog] = React.useState(false);
  const [presetName, setPresetName] = React.useState("");
  const [presetSaved, setPresetSaved] = React.useState(false);
  const [selectedPreset, setSelectedPreset] = React.useState("");
  const [managingPresets, setManagingPresets] = React.useState(false);
  const [deletingPreset, setDeletingPreset] = React.useState<string | null>(null);
  const [customTokens, setCustomTokens] = React.useState("");
  const [tokenCustomMode, setTokenCustomMode] = React.useState(false);
  const [models, setModels] = React.useState<string[]>([]);
  const [loadingModels, setLoadingModels] = React.useState(false);
  const [modelsError, setModelsError] = React.useState("");
  const [hasLastConfig, setHasLastConfig] = React.useState(false);
  const [guideOpen, setGuideOpen] = React.useState(false);
  const [sceneId, setSceneId] = React.useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = React.useState(false);
  const probeSigRef = React.useRef("");

  React.useEffect(() => {
    api.listPresets().then(setPresets).catch(() => {});
    api.samples().then(setSamples).catch(() => {});
    let savedBase = "";
    let savedProtocol: Protocol | undefined;
    const saved = loadLastConfig();
    if (
      saved &&
      (saved.protocol === "openai" ||
        saved.protocol === "anthropic" ||
        saved.protocol === "gemini") &&
      typeof saved.model === "string" &&
      saved.model
    ) {
      const merged = { ...defaultConfig(), ...saved, api_key: "" };
      setCfg(merged);
      setHasLastConfig(true);
      savedBase = merged.base_url;
      savedProtocol = merged.protocol;
    }
    if (savedBase) {
      api
        .listModels({ protocol: savedProtocol as Protocol, base_url: savedBase, api_key: "" })
        .then((r) => {
          if (r.ok) setModels(r.models);
          else if (r.error) setModelsError(r.error);
        })
        .catch((e) => setModelsError(String(e)));
    }
  }, []);

  React.useEffect(() => {
    if (!samples) return;
    const library = cfg.with_image ? samples.vision : samples.text;
    setCfg((c) => (c.questions.length === 0 ? { ...c, questions: library } : c));
  }, [samples, cfg.with_image]);

  React.useEffect(() => {
    const base = cfg.base_url.trim();
    const model = cfg.model.trim();
    if (!/^https?:\/\//.test(base) || !model) return;
    const sig = `${cfg.protocol}|${base}|${model}|${cfg.api_key}`;
    if (probeSigRef.current === sig) return;
    const handle = setTimeout(() => {
      void runProbe(true);
    }, 700);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cfg.protocol, cfg.base_url, cfg.model, cfg.api_key]);

  const loadModels = async () => {
    const target = cfg.base_url.trim();
    if (!target) {
      setModelsError(t("home.err.baseUrl"));
      return;
    }
    const protocol = cfg.protocol;
    const key = cfg.api_key;
    setLoadingModels(true);
    setModelsError("");
    try {
      const r = await api.listModels({ protocol, base_url: target, api_key: key });
      if (!r.ok) {
        setModelsError(r.error || t("home.err.fetchModels"));
        return;
      }
      setModels(r.models);
      setCfg((c) => {
        if (c.base_url.trim() !== target) return c;
        if (!r.models.length) return c;
        const keep = c.model && r.models.includes(c.model);
        return keep ? c : { ...c, model: r.models[0] };
      });
    } catch (e) {
      setModelsError(String(e));
    } finally {
      setLoadingModels(false);
    }
  };

  const clearLastConfig = () => {
    removeLastConfig();
    setHasLastConfig(false);
    setCfg({ ...defaultConfig(), questions: defaultQuestions(false) });
    setSceneId(null);
    setModels([]);
    setModelsError("");
  };

  const meta = PROTOCOL_META[cfg.protocol];

  const set = <K extends keyof TaskConfig>(key: K, value: TaskConfig[K]) => {
    if (PARAM_KEYS.has(key)) setSceneId(null);
    setCfg((c) => ({ ...c, [key]: value }));
  };

  const changeProtocol = (protocol: Protocol) =>
    setCfg((c) => ({
      ...c,
      protocol,
      base_url:
        c.base_url && c.base_url !== PROTOCOL_META.openai.defaultBase && c.base_url !== PROTOCOL_META.anthropic.defaultBase && c.base_url !== PROTOCOL_META.gemini.defaultBase
          ? c.base_url
          : PROTOCOL_META[protocol].defaultBase,
    }));

  const runProbe = async (silent = false) => {
    const base = cfg.base_url.trim();
    const model = cfg.model.trim();
    if (!base || !model) return;
    probeSigRef.current = `${cfg.protocol}|${base}|${model}|${cfg.api_key}`;
    setProbing(true);
    if (!silent) setProbe(null);
    try {
      setProbe(await api.probe(cfg));
    } catch (e) {
      setProbe({ ok: false, ttft_ms: null, latency_ms: null, error: String(e), text: "" });
    } finally {
      setProbing(false);
    }
  };

  const applyScene = (scene: Scene) => {
    const next = sceneId === scene.id ? null : scene.id;
    setSceneId(next);
    if (next === null) {
      setCfg((c) => ({
        ...defaultConfig(),
        protocol: c.protocol,
        base_url: c.base_url,
        api_key: c.api_key,
        model: c.model,
        questions: defaultQuestions(false),
      }));
      return;
    }
    setHasLastConfig(false);
    removeLastConfig();
    setCfg((c) => ({ ...c, ...scene.patch }));
  };

  const resetParams = () => {
    setSceneId(null);
    setCfg((c) => ({
      ...defaultConfig(),
      protocol: c.protocol,
      base_url: c.base_url,
      api_key: c.api_key,
      model: c.model,
    }));
  };

  const estimate = React.useMemo(() => {
    const sec = probe?.ok && probe.latency_ms ? probe.latency_ms / 1000 : null;
    let reqs: number | null = 0;
    let seconds: number | null = null;
    if (cfg.mode === "fixed") {
      if (cfg.fixed_duration_s > 0) {
        reqs = null;
        seconds = cfg.fixed_duration_s;
      } else {
        reqs = cfg.total_requests;
        seconds =
          sec != null
            ? Math.ceil(cfg.total_requests / Math.max(1, cfg.concurrency)) * sec
            : null;
      }
    } else if (cfg.mode === "open") {
      if (cfg.fixed_duration_s > 0) {
        reqs = null;
        seconds = cfg.fixed_duration_s;
      } else {
        reqs = cfg.total_requests;
        seconds =
          cfg.arrival_rate > 0 ? cfg.total_requests / cfg.arrival_rate + (sec ?? 0.5) : null;
      }
    } else {
      const levels = cfg.step_levels;
      if (cfg.step_duration_s > 0) {
        reqs = null;
        seconds = levels.length * cfg.step_duration_s;
      } else {
        reqs = levels.length * cfg.step_requests;
        seconds =
          sec != null
            ? levels.reduce(
                (acc, l) => acc + Math.ceil(cfg.step_requests / Math.max(1, l)) * sec,
                0,
              )
            : null;
      }
    }
    return { reqs, seconds };
  }, [cfg, probe]);

  const submit = async () => {
    setError("");
    if (!cfg.model.trim()) {
      setError(t("home.err.model"));
      return;
    }
    if (cfg.questions.length < 1) {
      setError(t("home.err.questions"));
      return;
    }
    if (cfg.with_image && !cfg.image_id) {
      setError(t("home.err.vision"));
      return;
    }
    if (tokenCustomMode) {
      const n = parseInt(customTokens, 10);
      if (!n || n < 1) {
        setError(t("home.err.tokens"));
        return;
      }
      cfg.input_tokens = n;
    }
    if (cfg.mode === "open" && !(cfg.arrival_rate > 0)) {
      setError(t("home.err.arrival"));
      return;
    }
    if (cfg.mode === "open" && !(cfg.total_requests > 0) && !(cfg.fixed_duration_s > 0)) {
      setError(t("home.err.openCount"));
      return;
    }
    if (cfg.mode === "fixed" && !(cfg.total_requests > 0) && !(cfg.fixed_duration_s > 0)) {
      setError(t("home.err.fixedCount"));
      return;
    }
    if (cfg.mode === "step" && !(cfg.step_requests > 0) && !(cfg.step_duration_s > 0)) {
      setError(t("home.err.stepCount"));
      return;
    }
    setSubmitting(true);
    try {
      const task = await api.createTask("", cfg);
      router.push(`/monitor?id=${task.id}`);
    } catch (e) {
      setError(String(e));
      setSubmitting(false);
    }
  };

  const savePreset = async () => {
    if (!presetName.trim()) return;
    await api.savePreset(presetName.trim(), cfg);
    setPresetDialog(false);
    const next = await api.listPresets();
    setPresets(next);
    setSelectedPreset("");
    setPresetSaved(true);
    window.setTimeout(() => setPresetSaved(false), 2000);
  };

  const deletePreset = async (id: string) => {
    setDeletingPreset(id);
    try {
      await api.deletePreset(id);
      setPresets((prev) => prev.filter((p) => p.id !== id));
      setSelectedPreset((cur) => (cur === id ? "" : cur));
    } catch (e) {
      setError(String(e));
    } finally {
      setDeletingPreset(null);
    }
  };

  const loadPreset = (id: string) => {
    const p = presets.find((x) => x.id === id);
    if (p) {
      setCfg({
        ...defaultConfig(),
        ...p.config,
        questions: p.config.questions?.length ? p.config.questions : defaultQuestions(Boolean(p.config.with_image)),
        api_key: cfg.api_key,
        base_url: p.config.base_url || cfg.base_url,
      });
      setSelectedPreset("");
      setSceneId(null);
    }
  };

  const modeMeta = MODE_META[cfg.mode];
  const needsModel = !cfg.model.trim();

  const samplesReady = samples != null;
  const checks: { id: string; ok: boolean; pending?: boolean; label: string; hint: string }[] = [
    {
      id: "model",
      ok: !!cfg.model.trim(),
      label: t("home.check.modelOk"),
      hint: t("home.check.modelHint"),
    },
    {
      id: "questions",
      ok: cfg.questions.length >= 1,
      pending: !samplesReady,
      label: !samplesReady
        ? t("home.check.qLoading")
        : cfg.questions.length >= 1
          ? t("home.check.qOk", { n: cfg.questions.length })
          : t("home.check.qEmpty"),
      hint: t("home.check.qHint"),
    },
  ];
  if (cfg.with_image) {
    checks.push({
      id: "image",
      ok: !!cfg.image_id,
      label: t("home.check.visionOk"),
      hint: t("home.check.visionHint"),
    });
  }
  const pendingCount = checks.filter((c) => !c.ok && !c.pending).length;
  const ready = pendingCount === 0;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t("home.title")}</h1>
        <Button variant="outline" size="sm" onClick={() => setGuideOpen(true)}>
          <BookOpen />
          {t("home.guide")}
        </Button>
      </header>

      {hasLastConfig ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          <span className="text-muted-foreground">{t("home.lastConfig")}</span>
          <Button variant="outline" size="sm" onClick={clearLastConfig}>
            {t("home.clearNew")}
          </Button>
        </div>
      ) : null}

      <section className="space-y-2.5" aria-labelledby="scene-heading">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <h2 id="scene-heading" className="text-sm font-medium">
              {t("home.scenesTitle")}
            </h2>
            <InfoTip>{t("home.scenesTip")}</InfoTip>
          </div>
          {sceneId || hasLastConfig ? (
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={resetParams}>
              {t("home.resetParams")}
            </Button>
          ) : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {SCENES.map((scene) => {
            const active = sceneId === scene.id;
            return (
              <button
                key={scene.id}
                type="button"
                onClick={() => applyScene(scene)}
                aria-pressed={active}
                className={cn(
                  "flex cursor-pointer items-start gap-2.5 rounded-xl border bg-card p-3 text-left shadow-sm transition-all",
                  active
                    ? "border-primary bg-primary/5 ring-1 ring-primary"
                    : "hover:border-primary/50 hover:bg-accent/40",
                )}
              >
                <span
                  className={cn(
                    "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
                    active ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                  )}
                >
                  {scene.icon}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="text-sm font-medium">{t(scene.nameKey)}</span>
                    {active ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                    ) : (
                      <Badge variant="secondary" className="text-[10px] font-normal">
                        {t(scene.tagKey)}
                      </Badge>
                    )}
                  </span>
                  <span className="mt-0.5 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                    {t(scene.descKey)}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7 xl:col-span-8">
          <StepCard n={1} title={t("home.step.connect")} done={!!cfg.model.trim()}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("home.field.protocol")}>
                <Select value={cfg.protocol} onValueChange={(v) => changeProtocol(v as Protocol)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(PROTOCOL_META) as Protocol[]).map((p) => (
                      <SelectItem key={p} value={p}>
                        {t(PROTOCOL_META[p].labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("home.field.model")} tip={t("home.field.modelTip")}>
                <ModelCombobox
                  value={cfg.model}
                  options={models}
                  onSelect={(v) => set("model", v)}
                  placeholder={t("home.field.modelPlaceholder")}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-1.5 text-xs"
                    onClick={loadModels}
                    disabled={loadingModels}
                  >
                    {loadingModels ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3 w-3" />
                    )}
                    {t("home.field.fetchModels")}
                  </Button>
                  {modelsError ? (
                    <span className="text-xs text-destructive">{modelsError}</span>
                  ) : models.length ? (
                    <span className="text-xs text-muted-foreground">
                      {t("home.field.modelsCount", { n: models.length })}
                    </span>
                  ) : null}
                </div>
              </Field>
              <Field
                label={t("home.field.baseUrl")}
                tip={t("home.field.baseUrlTip")}
              >
                <Input
                  placeholder={meta.basePlaceholder}
                  value={cfg.base_url}
                  onChange={(e) => set("base_url", e.target.value)}
                  onBlur={loadModels}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void loadModels();
                    }
                  }}
                />
              </Field>
              <Field label={meta.keyLabel} tip={t("home.field.apiKeyTip")}>
                <Input
                  type="password"
                  autoComplete="off"
                  placeholder="sk-..."
                  value={cfg.api_key}
                  onChange={(e) => set("api_key", e.target.value)}
                />
              </Field>
            </div>
            <Separator />
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 text-sm">
                {probing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    <span className="text-muted-foreground">{t("home.probe.probing")}</span>
                  </>
                ) : probe ? (
                  probe.ok ? (
                    <>
                      <span className="h-2 w-2 shrink-0 rounded-full bg-success" aria-hidden />
                      <span className="font-medium text-success">{t("home.probe.reachable")}</span>
                      <span className="num text-xs text-muted-foreground">
                        {t("home.probe.ttft", {
                          ttft: probe.ttft_ms?.toFixed(1) ?? "-",
                          lat: probe.latency_ms?.toFixed(0) ?? "-",
                        })}
                      </span>
                      {probe.text ? (
                        <span className="max-w-48 truncate text-xs text-muted-foreground">
                          {t("home.probe.quote", { text: probe.text })}
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <span className="h-2 w-2 shrink-0 rounded-full bg-destructive" aria-hidden />
                      <span className="font-medium text-destructive">
                        {t("home.probe.unreachable")}
                      </span>
                      <span
                        className="max-w-72 truncate text-xs text-muted-foreground"
                        title={probe.error ?? ""}
                      >
                        {probe.error}
                      </span>
                    </>
                  )
                ) : (
                  <>
                    <Plug className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs text-muted-foreground">{t("home.probe.auto")}</span>
                  </>
                )}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => runProbe()}
                disabled={probing || !cfg.model.trim()}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", probing && "animate-spin")} />
                {t("home.probe.recheck")}
              </Button>
            </div>
          </StepCard>

          <StepCard n={2} title={t("home.step.load")}>
            <Tabs value={cfg.mode} onValueChange={(v) => set("mode", v as TaskMode)}>
              <TabsList className="grid h-auto w-full grid-cols-3">
                {(Object.keys(MODE_META) as TaskMode[]).map((m) => (
                  <TabsTrigger
                    key={m}
                    value={m}
                    className="flex-col items-start gap-0.5 px-3 py-2"
                  >
                    <span className="text-sm font-medium">{t(MODE_META[m].nameKey)}</span>
                    <span className="text-[11px] font-normal text-muted-foreground">
                      {t(MODE_META[m].taglineKey)}
                    </span>
                  </TabsTrigger>
                ))}
              </TabsList>
              <TabsContent value="fixed" className="space-y-4">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Field
                    label={t("home.fixed.concurrency")}
                    tip={t("home.fixed.concurrencyTip")}
                  >
                    <Input
                      type="number"
                      min={1}
                      max={512}
                      value={cfg.concurrency}
                      onChange={(e) => set("concurrency", parseInt(e.target.value || "1", 10))}
                    />
                  </Field>
                  <Field
                    label={t("home.fixed.totalReq")}
                    tip={t("home.fixed.totalReqTip")}
                  >
                    <Input
                      type="number"
                      min={1}
                      value={cfg.total_requests}
                      onChange={(e) => set("total_requests", parseInt(e.target.value || "1", 10))}
                    />
                  </Field>
                  <Field
                    label={t("home.fixed.duration")}
                    tip={t("home.fixed.durationTip")}
                  >
                    <Input
                      type="number"
                      min={0}
                      value={cfg.fixed_duration_s}
                      onChange={(e) =>
                        set("fixed_duration_s", parseFloat(e.target.value || "0"))
                      }
                    />
                  </Field>
                </div>
              </TabsContent>
              <TabsContent value="step" className="space-y-4">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Field
                    label={t("home.step.levels")}
                    tip={t("home.step.levelsTip")}
                    hint={t("home.step.levelsHint")}
                  >
                    <Input
                      value={cfg.step_levels.join(",")}
                      onChange={(e) =>
                        set(
                          "step_levels",
                          e.target.value
                            .split(",")
                            .map((x) => parseInt(x.trim(), 10))
                            .filter((n) => Number.isFinite(n) && n >= 1)
                            .slice(0, 12),
                        )
                      }
                    />
                  </Field>
                  <Field
                    label={t("home.step.req")}
                    tip={t("home.step.reqTip")}
                  >
                    <Input
                      type="number"
                      min={1}
                      value={cfg.step_requests}
                      onChange={(e) => set("step_requests", parseInt(e.target.value || "1", 10))}
                    />
                  </Field>
                  <Field
                    label={t("home.step.dur")}
                    tip={t("home.step.durTip")}
                  >
                    <Input
                      type="number"
                      min={0}
                      value={cfg.step_duration_s}
                      onChange={(e) =>
                        set("step_duration_s", parseFloat(e.target.value || "0"))
                      }
                    />
                  </Field>
                </div>
                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <div className="text-sm font-medium">{t("home.step.autoStop")}</div>
                    <div className="text-xs text-muted-foreground">
                      {t("home.step.autoStopDesc")}
                    </div>
                  </div>
                  <Switch
                    checked={cfg.auto_stop}
                    onCheckedChange={(v) => set("auto_stop", v)}
                  />
                </div>
                {cfg.step_levels.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    {t("home.step.preview")}
                    {cfg.step_levels.map((l) => (
                      <Badge key={l} variant="secondary" className="num">
                        {l}
                      </Badge>
                    ))}
                    <span className="ml-1">
                      {cfg.step_duration_s > 0
                        ? t("home.step.statsDur", {
                            total: cfg.step_levels.length,
                            dur: String(cfg.step_duration_s),
                          })
                        : t("home.step.statsReq", {
                            total: cfg.step_levels.length,
                            requests: cfg.step_levels.length * cfg.step_requests,
                          })}
                    </span>
                  </div>
                )}
              </TabsContent>
              <TabsContent value="open" className="space-y-4">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  <Field
                    label={t("home.open.arrival")}
                    tip={t("home.open.arrivalTip")}
                  >
                    <Input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={cfg.arrival_rate}
                      onChange={(e) =>
                        set("arrival_rate", parseFloat(e.target.value || "1"))
                      }
                    />
                  </Field>
                  <Field
                    label={t("home.fixed.totalReq")}
                    tip={t("home.open.totalReqTip")}
                  >
                    <Input
                      type="number"
                      min={1}
                      value={cfg.total_requests}
                      onChange={(e) => set("total_requests", parseInt(e.target.value || "1", 10))}
                    />
                  </Field>
                  <Field
                    label={t("home.fixed.duration")}
                    tip={t("home.open.durationTip")}
                  >
                    <Input
                      type="number"
                      min={0}
                      value={cfg.fixed_duration_s}
                      onChange={(e) =>
                        set("fixed_duration_s", parseFloat(e.target.value || "0"))
                      }
                    />
                  </Field>
                </div>
                <p className="text-xs text-muted-foreground">{t("home.open.note")}</p>
              </TabsContent>
            </Tabs>
          </StepCard>

          <Card className="overflow-hidden">
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="flex w-full cursor-pointer items-center gap-3 border-b bg-muted/30 px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              aria-expanded={advancedOpen}
            >
              <StepBadge n={3} />
              <div className="min-w-0 flex-1">
                <CardTitle className="text-base">{t("home.step.advanced")}</CardTitle>
                <CardDescription className="mt-0.5 text-xs">{t("home.advancedHint")}</CardDescription>
              </div>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                  advancedOpen && "rotate-180",
                )}
              />
            </button>
            {advancedOpen ? (
              <CardContent className="space-y-4 pt-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    label={`${t("home.adv.inputLen")}${cfg.with_image ? t("home.adv.inputLenVision") : ""}`}
                    tip={t("home.adv.inputLenTip")}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      {tokenCustomMode ? (
                        <Input
                          className="w-32"
                          type="number"
                          min={1}
                          placeholder={t("home.adv.tokenCustomPlaceholder")}
                          value={customTokens}
                          onChange={(e) => setCustomTokens(e.target.value)}
                        />
                      ) : (
                        PRESET_INPUTS.map((n) => (
                          <button
                            key={n}
                            type="button"
                            onClick={() => set("input_tokens", n)}
                            className={cn(
                              "num cursor-pointer rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                              cfg.input_tokens === n
                                ? "border-primary bg-primary/10 text-primary"
                                : "hover:bg-accent",
                            )}
                          >
                            {n}
                          </button>
                        ))
                      )}
                      <button
                        type="button"
                        onClick={() => setTokenCustomMode((v) => !v)}
                        className="cursor-pointer rounded-md border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent"
                      >
                        {tokenCustomMode ? t("home.adv.tokenPreset") : t("home.adv.tokenCustom")}
                      </button>
                    </div>
                  </Field>
                  <div className="grid grid-cols-2 gap-4">
                    <Field
                      label={t("home.adv.maxOutput")}
                      tip={t("home.adv.maxOutputTip")}
                    >
                      <Input
                        type="number"
                        min={1}
                        value={cfg.max_output_tokens}
                        onChange={(e) => set("max_output_tokens", parseInt(e.target.value || "1", 10))}
                      />
                    </Field>
                    <Field
                      label={t("home.adv.timeout")}
                      tip={t("home.adv.timeoutTip")}
                    >
                      <Input
                        type="number"
                        min={1}
                        value={cfg.timeout}
                        onChange={(e) => set("timeout", parseFloat(e.target.value || "10"))}
                      />
                    </Field>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-1.5">
                    <div className="text-sm font-medium">{t("home.adv.slaTitle")}</div>
                    <InfoTip>{t("home.adv.slaTip")}</InfoTip>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <Field
                      label={t("home.adv.slaTtft")}
                      tip={t("home.adv.slaTtftTip")}
                    >
                      <Input
                        type="number"
                        min={0.1}
                        step={0.1}
                        value={cfg.sla_ttft_p95_s}
                        onChange={(e) =>
                          set("sla_ttft_p95_s", parseFloat(e.target.value || "2"))
                        }
                      />
                    </Field>
                    <Field
                      label={t("home.adv.slaE2e")}
                      tip={t("home.adv.slaE2eTip")}
                    >
                      <Input
                        type="number"
                        min={0.5}
                        step={0.5}
                        value={cfg.sla_e2e_p95_s}
                        onChange={(e) =>
                          set("sla_e2e_p95_s", parseFloat(e.target.value || "15"))
                        }
                      />
                    </Field>
                    <Field
                      label={t("home.adv.slaErr")}
                      tip={t("home.adv.slaErrTip")}
                    >
                      <Input
                        type="number"
                        min={0}
                        step={0.001}
                        value={cfg.sla_error_rate}
                        onChange={(e) =>
                          set("sla_error_rate", parseFloat(e.target.value || "0.005"))
                        }
                      />
                    </Field>
                  </div>
                </div>

                <div className="flex items-center justify-between rounded-lg border p-3">
                  <div>
                    <div className="text-sm font-medium">{t("home.adv.visionTitle")}</div>
                    <div className="text-xs text-muted-foreground">{t("home.adv.visionDesc")}</div>
                  </div>
                  <Switch
                    checked={cfg.with_image}
                    onCheckedChange={(v) => {
                      set("with_image", v);
                      set("questions", []);
                      if (!v) set("image_id", "");
                    }}
                  />
                </div>

                {cfg.with_image ? (
                  <ImagePicker
                    key="image-picker"
                    value={cfg.image_id}
                    onChange={(id) => set("image_id", id)}
                  />
                ) : null}

                {samples ? (
                  <QuestionPicker
                    key={cfg.with_image ? "q-vision" : "q-text"}
                    library={cfg.with_image ? samples.vision : samples.text}
                    value={cfg.questions}
                    onChange={(q) => set("questions", q)}
                  />
                ) : null}
              </CardContent>
            ) : null}
          </Card>
        </div>

        <aside className="lg:col-span-5 xl:col-span-4">
          <div className="space-y-4 lg:sticky lg:top-[4.5rem]">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{t("home.summary.title")}</CardTitle>
                  <div className="flex items-center gap-1.5">
                    <Badge variant="secondary" className="font-normal">
                      {sceneId
                        ? t("home.summary.scene", {
                            name: t(SCENES.find((s) => s.id === sceneId)?.nameKey ?? "home.scene.quick.name"),
                          })
                        : t("home.summary.custom")}
                    </Badge>
                    <Badge variant="outline">{t(modeMeta.nameKey)}</Badge>
                  </div>
                </div>
                <CardDescription className="text-xs">{t(modeMeta.goalKey)}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <SummaryChip
                    label={t("home.chip.pressure")}
                    value={
                      cfg.mode === "step"
                        ? t("home.chip.pressureStep", { levels: cfg.step_levels.join(" → ") })
                        : cfg.mode === "open"
                          ? t("home.chip.pressureOpen", { rate: cfg.arrival_rate })
                          : t("home.chip.pressureFixed", { n: cfg.concurrency })
                    }
                  />
                  <SummaryChip
                    label={t("home.chip.requests")}
                    value={
                      estimate.reqs != null
                        ? t("home.chip.reqCount", { n: estimate.reqs })
                        : t("home.chip.reqSustain", {
                            s: cfg.fixed_duration_s || cfg.step_duration_s * cfg.step_levels.length,
                          })
                    }
                  />
                  <SummaryChip
                    label={t("home.chip.io")}
                    value={t("home.chip.ioVal", {
                      in: cfg.input_tokens,
                      out: cfg.max_output_tokens,
                    })}
                  />
                  <SummaryChip
                    label={t("home.chip.time")}
                    muted={estimate.seconds == null}
                    onClick={estimate.seconds == null && !probing ? () => runProbe() : undefined}
                    disabled={probing}
                    value={
                      estimate.seconds != null
                        ? estimate.seconds < 60
                          ? t("home.chip.timeSec", { n: estimate.seconds.toFixed(0) })
                          : t("home.chip.timeMin", {
                              m: Math.floor(estimate.seconds / 60),
                              s: Math.round(estimate.seconds % 60),
                            })
                        : probing
                          ? t("home.chip.timeProbing")
                          : t("home.chip.timePending")
                    }
                  />
                </div>

                <div className="rounded-lg border bg-muted/30 p-3">
                  <div className="mb-2 text-xs font-medium text-muted-foreground">
                    {t("home.check.title")}
                  </div>
                  <ul className="space-y-1.5">
                    {checks.map((c) => (
                      <li key={c.id} className="flex items-start gap-2 text-xs">
                        {c.pending ? (
                          <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />
                        ) : c.ok ? (
                          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                        ) : (
                          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                        )}
                        <span className="flex-1">
                          <span
                            className={
                              c.ok && !c.pending ? "text-foreground" : "text-muted-foreground"
                            }
                          >
                            {c.label}
                          </span>
                          {!c.ok && !c.pending ? (
                            <span className="mt-0.5 block text-[11px] text-muted-foreground">
                              {c.hint}
                            </span>
                          ) : null}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                <Separator />

                <div className="rounded-lg border bg-muted/30 p-3">
                  <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    <Bookmark className="h-3.5 w-3.5" />
                    {t("home.presets.title")}
                    <span className="font-normal">{t("home.presets.count", { n: presets.length })}</span>
                    {presets.length > 0 ? (
                      <button
                        type="button"
                        onClick={() => setManagingPresets((v) => !v)}
                        className="ml-auto cursor-pointer font-normal underline-offset-2 hover:text-foreground hover:underline"
                      >
                        {managingPresets ? t("home.presets.done") : t("home.presets.manage")}
                      </button>
                    ) : null}
                  </div>
                  <p className="mb-2 text-[11px] text-muted-foreground">{t("home.presets.desc")}</p>
                  <div className="flex items-center gap-2">
                    <Select value={selectedPreset} onValueChange={loadPreset}>
                      <SelectTrigger className="h-8 flex-1 text-xs">
                        <SelectValue
                          placeholder={
                            presets.length
                              ? t("home.presets.placeholder")
                              : t("home.presets.empty")
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {presets.map((p) => (
                          <SelectItem key={p.id} value={p.id}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 shrink-0 px-3 text-xs"
                      onClick={() => setPresetDialog(true)}
                    >
                      <Save className="h-3.5 w-3.5" />
                      {presetSaved ? t("home.presets.saved") : t("home.presets.save")}
                    </Button>
                  </div>
                  {managingPresets && presets.length > 0 ? (
                    <div className="mt-2 space-y-1">
                      {presets.map((p) => (
                        <div
                          key={p.id}
                          className="flex items-center justify-between gap-2 rounded-md border bg-background px-2 py-1.5 text-xs"
                        >
                          <span className="truncate">{p.name}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-6 shrink-0 px-1.5 text-destructive hover:text-destructive"
                            onClick={() => deletePreset(p.id)}
                            disabled={deletingPreset === p.id}
                          >
                            {deletingPreset === p.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                            {t("home.presets.delete")}
                          </Button>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>

                <div className="space-y-2">
                  {error && !needsModel ? (
                    <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-2.5 text-xs text-destructive">
                      <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                      <span>{error}</span>
                    </div>
                  ) : null}
                  <Button
                    className="w-full"
                    size="lg"
                    disabled={submitting || needsModel}
                    onClick={submit}
                  >
                    {submitting ? <Loader2 className="animate-spin" /> : <Rocket />}
                    {submitting ? t("home.creating") : t("home.start")}
                  </Button>
                  {needsModel ? (
                    <p className="text-center text-xs text-muted-foreground">
                      {t("home.startHint")}
                    </p>
                  ) : !ready ? (
                    <p className="text-center text-xs text-warning">
                      {t("home.notReady", { n: pendingCount })}
                    </p>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          </div>
        </aside>
      </div>

      <Dialog open={presetDialog} onOpenChange={setPresetDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("home.presetDialog.title")}</DialogTitle>
            <DialogDescription>{t("home.presetDialog.desc")}</DialogDescription>
          </DialogHeader>
          <Input
            placeholder={t("home.presetDialog.placeholder")}
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setPresetDialog(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={savePreset} disabled={!presetName.trim()}>
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={guideOpen} onOpenChange={setGuideOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{t("home.guide.title")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <GuideSection title={t("home.guide.s1.title")}>{tr("home.guide.s1.body")}</GuideSection>
            <GuideSection title={t("home.guide.s2.title")}>{tr("home.guide.s2.body")}</GuideSection>
            <GuideSection title={t("home.guide.s3.title")}>{tr("home.guide.s3.body")}</GuideSection>
            <GuideSection title={t("home.guide.s4.title")}>{tr("home.guide.s4.body")}</GuideSection>
            <GuideSection title={t("home.guide.s5.title")}>{tr("home.guide.s5.body")}</GuideSection>
            <GuideSection title={t("home.guide.s6.title")}>{tr("home.guide.s6.body")}</GuideSection>
          </div>
          <DialogFooter>
            <Button onClick={() => setGuideOpen(false)}>{t("home.guide.close")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
