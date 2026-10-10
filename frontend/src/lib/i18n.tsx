"use client";

import * as React from "react";

export type Lang = "en" | "zh";

type Vars = Record<string, string | number>;

const STORAGE_KEY = "lmb-lang";

const en = {
  "common.lang.en": "EN",
  "common.lang.zh": "中文",
  "common.lang.aria": "Switch language",
  "common.brand.sub": "Inference benchmark console",
  "common.brand.homeAria": "LLM Bench home",
  "common.nav.new": "New run",
  "common.nav.history": "History",
  "common.nav.aria": "Main navigation",
  "common.cancel": "Cancel",
  "common.save": "Save",
  "common.loading": "Loading…",
  "common.tip.aria": "Parameter help",
  "common.status.pending": "Queued",
  "common.status.running": "Running",
  "common.status.done": "Done",
  "common.status.failed": "Failed",
  "common.status.cancelled": "Cancelled",
  "common.status.interrupted": "Interrupted",
  "common.mode.fixed.name": "Fixed concurrency",
  "common.mode.fixed.short": "Fixed",
  "common.mode.fixed.tagline": "One pressure level, one batch",
  "common.mode.fixed.goal":
    "Latency & throughput baseline at a fixed concurrency — ideal for a quick health check",
  "common.mode.step.name": "Concurrency sweep",
  "common.mode.step.short": "Sweep",
  "common.mode.step.tagline": "Ramp up level by level to find the ceiling",
  "common.mode.step.goal":
    "Ramp concurrency from low to high and auto-locate the throughput knee plus a recommended setting",
  "common.mode.open.name": "Open-loop rate",
  "common.mode.open.short": "Open",
  "common.mode.open.tagline": "Fixed-rate injection, watch the queue",
  "common.mode.open.goal":
    "Inject requests at a fixed rate to reproduce real-traffic queuing and saturation",
  "common.protocol.openai": "OpenAI compatible",
  "common.protocol.anthropic": "Anthropic",
  "common.protocol.gemini": "Gemini",

  "home.title": "New run",
  "home.guide": "Quick guide",
  "home.lastConfig":
    "Restored your last run's config (API key cleared). Adjust and run again.",
  "home.clearNew": "Clear & start fresh",
  "home.scenesTitle": "Scenes",
  "home.scenesTip":
    "One click loads recommended settings (your connection stays untouched). Fine-tune afterwards; clicking the same scene again resets to defaults.",
  "home.resetParams": "Reset to defaults",
  "home.scene.quick.name": "Single-stream latency",
  "home.scene.quick.tag": "Fastest",
  "home.scene.quick.desc": "Per-request latency baseline — done in ~15s",
  "home.scene.ramp.name": "Throughput sweep",
  "home.scene.ramp.tag": "Most used",
  "home.scene.ramp.desc":
    "Ramp up level by level to find the recommended concurrency",
  "home.scene.peak.name": "Peak probing",
  "home.scene.peak.tag": "Find saturation",
  "home.scene.peak.desc":
    "Push until saturated to reveal the real ceiling",
  "home.scene.flow.name": "Live traffic",
  "home.scene.flow.tag": "Open-loop",
  "home.scene.flow.desc":
    "Inject at a fixed rate to watch queuing behavior",
  "home.step.connect": "Connect model",
  "home.step.load": "Load pattern",
  "home.step.advanced": "Advanced",
  "home.advancedHint": "Defaults are usually fine",
  "home.field.protocol": "Protocol",
  "home.field.model": "Model",
  "home.field.modelTip":
    "The model under test. Use “Fetch models” to auto-discover, or type the name directly.",
  "home.field.modelPlaceholder": "Select or type a model…",
  "home.field.fetchModels": "Fetch models",
  "home.field.modelsCount": "{n} models available",
  "home.field.baseUrl": "Endpoint Base URL",
  "home.field.baseUrlTip":
    "The inference endpoint. Local Ollama / vLLM is usually http://localhost:11434/v1 or another address ending in /v1.",
  "home.field.apiKeyTip":
    "Local servers usually don't need a key — leave this blank",
  "home.probe.probing": "Checking connectivity…",
  "home.probe.reachable": "Reachable",
  "home.probe.unreachable": "Unreachable",
  "home.probe.ttft": "TTFT {ttft}ms · E2E {lat}ms",
  "home.probe.auto":
    "Reachability is checked automatically once Endpoint & model are set",
  "home.probe.recheck": "Re-check",
  "home.probe.quote": "“{text}”",

  "home.fixed.concurrency": "Concurrency",
  "home.fixed.concurrencyTip":
    "How many requests run at once. 4 means 4 requests are constantly hitting the server. Higher values squeeze out peak throughput but drive latency up.",
  "home.fixed.totalReq": "Total requests",
  "home.fixed.totalReqTip":
    "Total requests in this run. More means more stable results; 20–50 is enough for a first verdict. Mutually exclusive with duration (duration wins when > 0).",
  "home.fixed.duration": "Duration (s)",
  "home.fixed.durationTip":
    "Time-based run: keep hammering for the given seconds to observe stability. 0 means stop by request count.",
  "home.step.levels": "Concurrency sequence",
  "home.step.levelsTip":
    "Concurrency per level, applied in order (e.g. 1→2→4→8→16). Each level is measured separately to draw the concurrency–throughput curve and find the knee and saturation.",
  "home.step.levelsHint": "Comma-separated, e.g. 1,2,4,8,16",
  "home.step.req": "Requests per level",
  "home.step.reqTip":
    "Requests sent per level. ≥10 matters statistically; ≥20 gives more confidence. Mutually exclusive with duration.",
  "home.step.dur": "Duration per level (s)",
  "home.step.durTip":
    "Time-based levels — useful when throughput is stable but request times vary. 0 means stop by request count.",
  "home.step.autoStop": "Auto-stop (saturation pruning)",
  "home.step.autoStopDesc":
    "Skips the remaining levels early when throughput grows less than 3% for two consecutive levels or the error rate breaches the threshold",
  "home.step.preview": "Levels:",
  "home.step.statsDur": "{total} levels · {dur}s each",
  "home.step.statsReq": "{total} levels · {requests} requests",
  "home.open.arrival": "Arrival rate (req/s)",
  "home.open.arrivalTip":
    "Open-loop injection: a fixed number of requests per second, regardless of whether the server can keep up. Reproduces how things behave as real traffic grows.",
  "home.open.totalReqTip":
    "Total requests to inject. Mutually exclusive with duration (duration wins when > 0).",
  "home.open.durationTip":
    "How many seconds to keep injecting at the set rate. 0 means stop by request count.",
  "home.open.note":
    "Open-loop mode reproduces real-traffic saturation and SLA violations: requests are injected at a fixed rate and never throttled, even when the server queues up.",

  "home.adv.inputLen": "Input length (tokens)",
  "home.adv.inputLenVision": ", attached image included",
  "home.adv.inputLenTip":
    "Prompt length per request. Long inputs stress prefill (first-token latency grows); short inputs skew toward decoding speed. Keep it within the model's context window.",
  "home.adv.tokenPreset": "Presets",
  "home.adv.tokenCustom": "Custom",
  "home.adv.tokenCustomPlaceholder": "Custom",
  "home.adv.maxOutput": "Max output tokens",
  "home.adv.maxOutputTip":
    "Caps the answer length per request. Affects per-request time and total token spend; matching real traffic makes results more believable.",
  "home.adv.timeout": "Request timeout (s)",
  "home.adv.timeoutTip":
    "Requests still running past this are counted as timeouts (errors). Keep it slightly above your slowest expected response.",
  "home.adv.slaTitle": "SLA limits (drive auto-analysis)",
  "home.adv.slaTip":
    "The compliance line. After a sweep, the last level that violates no SLA is SLA-Max; recommended concurrency = min(Saturation, SLA-Max).",
  "home.adv.slaTtft": "P95 TTFT ≤ (s)",
  "home.adv.slaTtftTip":
    "95% of requests should get their first token within this (2s ≈ acceptable wait for a conversation).",
  "home.adv.slaE2e": "P95 E2E ≤ (s)",
  "home.adv.slaE2eTip":
    "95% of requests should finish within this. Set it to your business tolerance, e.g. 15s.",
  "home.adv.slaErr": "Error rate ≤ (ratio)",
  "home.adv.slaErrTip":
    "Maximum tolerated failure ratio. 0.005 = 0.5%. Levels above are treated as out of compliance.",
  "home.adv.visionTitle": "Vision model test",
  "home.adv.visionDesc":
    "Attach one image to measure multimodal latency; pick from the gallery or upload your own",

  "home.summary.title": "This run",
  "home.summary.scene": "Scene · {name}",
  "home.summary.custom": "Custom",
  "home.chip.pressure": "Pressure",
  "home.chip.requests": "Requests",
  "home.chip.io": "Input / Out",
  "home.chip.time": "Est. duration",
  "home.chip.pressureStep": "{levels} conn.",
  "home.chip.pressureOpen": "{rate} req/s",
  "home.chip.pressureFixed": "{n} concurrent",
  "home.chip.reqCount": "~{n}",
  "home.chip.reqSustain": "{s}s sustained",
  "home.chip.ioVal": "{in} / {out} tok",
  "home.chip.timeProbing": "Measuring…",
  "home.chip.timePending": "Not measured",
  "home.chip.timeSec": "{n} s",
  "home.chip.timeMin": "{m}m {s}s",
  "home.check.title": "Pre-flight check",
  "home.check.modelOk": "Model is set",
  "home.check.modelHint":
    "Fill it in under ① Connect model, or use “Fetch models”",
  "home.check.qLoading": "Loading question bank…",
  "home.check.qOk": "Questions (built-in {n})",
  "home.check.qEmpty": "No questions yet",
  "home.check.qHint":
    "A built-in bank is preloaded; customize under ③ Advanced",
  "home.check.visionOk": "Vision test image",
  "home.check.visionHint":
    "Pick or upload one under ③ Advanced",
  "home.startHint": "Fill in a model name under ① Connect model first",
  "home.notReady": "{n} item(s) still missing — complete the checklist to start",
  "home.start": "Start run",
  "home.creating": "Creating…",

  "home.presets.title": "Presets",
  "home.presets.count": "({n})",
  "home.presets.manage": "Manage",
  "home.presets.done": "Done",
  "home.presets.desc": "Save the full config as a reusable template",
  "home.presets.placeholder": "Load a preset",
  "home.presets.empty": "No presets yet",
  "home.presets.save": "Save preset",
  "home.presets.saved": "Saved ✓",
  "home.presets.delete": "Delete",
  "home.presetDialog.title": "Save preset",
  "home.presetDialog.desc":
    "Everything — connection, load pattern and advanced options — will be saved for one-click reuse.",
  "home.presetDialog.placeholder": "Preset name",

  "home.err.model": "Please enter a model name",
  "home.err.baseUrl": "Please fill in the Endpoint Base URL first",
  "home.err.fetchModels": "Failed to fetch models",
  "home.err.questions": "Pick or type at least 1 question (the bank can't be empty)",
  "home.err.vision": "Vision testing is on — select or upload an image",
  "home.err.tokens": "Input length must be a number ≥ 1",
  "home.err.arrival": "Open-loop mode requires an arrival rate > 0",
  "home.err.openCount": "Open-loop mode needs either total requests or a duration",
  "home.err.fixedCount": "Set either total requests or a duration",
  "home.err.stepCount": "Sweep mode needs either requests per level or a duration",

  "home.guide.title": "Quick guide: concurrency load testing in 3 minutes",
  "home.guide.close": "Got it — let's configure this",
  "home.guide.s1.title": "What exactly are we measuring?",
  "home.guide.s1.body":
    "Four metrics matter: **TTFT** (time to first token) decides how long a conversation seems to wait before replying; **TPOT** (time between tokens) decides whether streaming feels smooth; **throughput tokens/s** is the total output per second — the server's production capacity; **error rate** shows whether the service can still answer under pressure.",
  "home.guide.s2.title": "What problem does concurrency testing solve?",
  "home.guide.s2.body":
    "The core question is: **how many parallel connections should this model get?** Too few and the machine idles; too many and requests queue — latency spikes, throughput plateaus, and the service can even crash. This tool's **Concurrency sweep** ramps from 1 connection upward automatically, plots the throughput curve, marks the saturation point and gives a **recommended concurrency**: enough capacity without leaving users waiting.",
  "home.guide.s3.title": "Which load pattern should you pick?",
  "home.guide.s3.body":
    "**Fixed concurrency** = a single-point health check; start here to confirm connectivity and baseline performance. **Concurrency sweep** = finding the ceiling (most common), answering “how many connections?”. **Open-loop rate** = simulating real traffic by injecting at a fixed rate and watching the server queue.",
  "home.guide.s4.title": "How should you read the metrics?",
  "home.guide.s4.body":
    "Focus on **P95**: it reflects the worst 5% of users and is far more honest than an average. On the sweep chart, find the level where “throughput stops rising and TTFT starts soaring” — that's the knee; the green line marks the **recommended concurrency**; start your production config there.",
  "home.guide.s5.title": "What do the SLA limits mean?",
  "home.guide.s5.body":
    "SLAs are your **performance promises**, three by default: 95% of requests get their first token within 2s, complete within 15s, and fewer than 0.5% fail. During a sweep, any level that breaks a promise is “in violation” — the last compliant level is called **SLA-Max**. **Recommended concurrency = min(saturation, SLA-Max)**: maximize capacity without breaking your promises. Keep the defaults for local debugging; for production, set them to the latency you actually promise.",
  "home.guide.s6.title": "Your first run",
  "home.guide.s6.body":
    "Pick the **“Throughput sweep”** scene at the top → fill in the model endpoint under ① — connectivity is checked automatically and you'll see “Reachable” on the right when it works → hit **Start run**. In about 2–3 minutes the monitor page shows a summary card: recommended concurrency, saturation point and per-level latency.",

  "monitor.missingId": "Missing run ID",
  "monitor.missingIdHint":
    "Open one from History, or start a new run to see live results.",
  "monitor.newRun": "New run",
  "monitor.viewHistory": "View history",
  "monitor.back": "Back",
  "monitor.created": "{base} · created {time}",
  "monitor.retest": "Re-run",
  "monitor.cancel": "Cancel run",
  "monitor.config": "Config",
  "monitor.chip.mode": "Pattern",
  "monitor.chip.pressure": "Pressure",
  "monitor.chip.load": "Load",
  "monitor.chip.io": "IO",
  "monitor.chip.timeout": "Timeout",
  "monitor.chip.autoStop": "Auto-stop",
  "monitor.on": "On",
  "monitor.off": "Off",
  "monitor.pressureStep": "{levels} conn.",
  "monitor.pressureOpen": "{rate} req/s",
  "monitor.pressureFixed": "{n} concurrent",
  "monitor.qtyStepDur": "{dur}s × {n}",
  "monitor.qtyStepReq": "{req} req × {n}",
  "monitor.qtyFixed": "{dur}s run",
  "monitor.qtyTotal": "{n} requests",
  "monitor.progressCount": "requests done",
  "monitor.progressDone": "completed",
  "monitor.progressDoneN": "{n} requests",
  "monitor.progressPlanned": " · planned {dur}s",
  "monitor.progressFlight": " · {n} in flight",
  "monitor.stepBadge": "Level {cur}/{total} · conn. {c}",
  "monitor.elapsed": "Elapsed",
  "monitor.liveTps": "Live tps",
  "monitor.autoStopSat":
    "Auto-stopped: throughput grew less than 3% for two consecutive levels, so the rest were skipped.",
  "monitor.autoStop": "Auto-stopped: {reason}",
  "monitor.st0": "Queueing",
  "monitor.st1": "Running",
  "monitor.st2": "Done",
  "monitor.st3": "Failed",
  "monitor.st4": "Cancelled",
  "monitor.st5": "Interrupted",
  "monitor.metric.outTps": "Output throughput",
  "monitor.metric.outTpsHint": "cumulative {v} t/s · input {i} t/s",
  "monitor.metric.ttft": "TTFT P95",
  "monitor.metric.ttftHint": "avg {v} · P99 {p}",
  "monitor.metric.err": "Error rate",
  "monitor.metric.errHint": "{n} failed",
  "monitor.metric.rps": "Request rate",
  "monitor.metric.rpsHint": "cumulative {v} r/s",
  "monitor.metric.tpot": "Avg TPOT",
  "monitor.metric.tpotHint": "P95 {v} · P99 {p}",
  "monitor.metric.e2e": "Avg E2E",
  "monitor.metric.e2eHint": "P95 {v} · P99 {p}",
  "monitor.metric.itl": "ITL P50",
  "monitor.metric.itlHint": "P95 {v} · inter-token jitter",
  "monitor.metric.tokens": "Tokens",
  "monitor.metric.tokensHint": "output cumulative · input {i}",
  "monitor.metric.live": "Live throughput (5s window)",
  "monitor.metric.liveHint": "Rolling throughput over the last 5 seconds",
  "monitor.more": "More metrics",
  "monitor.analysis.title": "Performance profile",
  "monitor.conf.high": "High confidence",
  "monitor.conf.medium": "Medium confidence",
  "monitor.conf.low": "Low confidence",
  "monitor.analysis.rec": "Recommended concurrency",
  "monitor.analysis.recHint": "min(Saturation, SLA-Max)",
  "monitor.analysis.recUnit": "conn.",
  "monitor.analysis.maxRps": "Max sustainable RPS",
  "monitor.analysis.maxRpsHint": "req/s at the recommended level",
  "monitor.analysis.stops.all": "Ran all levels",
  "monitor.analysis.stops.saturation": "Auto-stopped: throughput plateau",
  "monitor.analysis.stops.error_rate": "Auto-stopped: error rate too high",
  "monitor.analysis.slaLine":
    "SLA: P95 TTFT ≤ {ttft}s · P95 E2E ≤ {e2e}s · error rate ≤ {rate}%",
  "monitor.analysis.single": "Single-connection baseline",
  "monitor.analysis.maxTp": "Peak throughput level",
  "monitor.analysis.sat": "Saturation",
  "monitor.analysis.satNone": "n/a",
  "monitor.analysis.satHint": "throughput gain < 5% between {a} → {b}",
  "monitor.analysis.satRising": "throughput kept growing at every level",
  "monitor.analysis.knee": "Knee",
  "monitor.analysis.kneeNone": "not found",
  "monitor.analysis.kneeHint":
    "diminishing throughput returns with clearly worse P95 TTFT",
  "monitor.analysis.slaMax": "SLA-Max conforming concurrency",
  "monitor.analysis.slaMaxNone": "none",
  "monitor.analysis.slaMaxHint": "last level that broke no SLA",
  "monitor.analysis.levels": "Levels run",
  "monitor.analysis.levelsHint": "SLA-compliant up to {n} conn.",
  "monitor.analysis.footer":
    "Auto-detected from throughput growth, P95 TTFT and SLA limits",
  "monitor.analysis.retest": "Re-test at recommended concurrency",
  "monitor.conn": "conn.",
  "monitor.chart.stepTitle": "Concurrency sweep · Throughput / RPS",
  "monitor.chart.latencyTitle": "Latency trend (TTFT / E2E / TPOT)",
  "monitor.chart.liveTitle": "Live throughput (5s window)",
  "monitor.chart.histTitle": "TTFT histogram",
  "monitor.chart.timeS": "Time (s)",
  "monitor.chart.sec": "Seconds",
  "monitor.chart.count": "Count",
  "monitor.chart.windowTps": "Window tps",
  "monitor.chart.throughput": "Throughput",
  "monitor.chart.ttftDist": "TTFT distribution",
  "monitor.chart.markRec": "Rec {n}",
  "monitor.chart.markSat": "Sat {n}",
  "monitor.chart.markKnee": "Knee {n}",
  "monitor.chart.markSla": "SLA {n}",
  "monitor.chart.empty1": "Waiting for the first level…",
  "monitor.chart.empty0": "No data yet",
  "monitor.table.stepsTitle": "Sweep results",
  "monitor.table.rec": "Rec",
  "monitor.table.logTitle": "Request log",
  "monitor.table.logRecent": "latest {a} / {b} total",
  "monitor.table.level": "Level",
  "monitor.table.status": "Status",
  "monitor.table.out": "Out",
  "monitor.table.in": "In",
  "monitor.table.err": "Error",
  "monitor.table.conc": "Concurrency",
  "monitor.table.req": "Requests",
  "monitor.table.done": "Done",
  "monitor.table.tpsThr": "Throughput t/s",
  "monitor.table.tpsOut": "Output t/s",
  "monitor.table.tpsIn": "Input t/s",
  "monitor.table.errRate": "Error rate",

  "history.title": "History",
  "history.refresh": "Refresh",
  "history.filterModel": "Filter by model…",
  "history.filterStatusAll": "All statuses",
  "history.filterModeAll": "All patterns",
  "history.selected": "{n} selected",
  "history.compare": "Compare ↓",
  "history.clear": "Clear",
  "history.stats.total": "Total runs",
  "history.stats.done": "Completed",
  "history.stats.running": "{n} running",
  "history.stats.avgTps": "Avg throughput",
  "history.stats.maxTps": "Max throughput",
  "history.emptyNone": "No runs yet",
  "history.emptyFilter": "No runs match the filters",
  "history.newRun": "New run",
  "history.col.model": "Model",
  "history.col.protoMode": "Protocol / Pattern",
  "history.col.status": "Status",
  "history.col.done": "Done",
  "history.col.throughput": "Throughput t/s",
  "history.col.ttftAvg": "Avg TTFT",
  "history.col.tpotAvg": "Avg TPOT",
  "history.col.rps": "RPS",
  "history.col.errRate": "Error rate",
  "history.col.created": "Created",
  "history.col.actions": "Actions",
  "history.row.retest": "Re-run with this config",
  "history.row.delete": "Delete",
  "history.row.view": "Click to view results",
  "history.toggle.deselect": "Deselect all",
  "history.toggle.select": "Select all completed",
  "history.compareTitle": "Comparison ({n} selected)",
  "history.col.pattern": "Pattern",
  "history.col.tpsOut": "Output t/s",
  "history.col.ttftAvgP95": "Avg TTFT / P95",
  "history.col.itl": "ITL P50",
  "history.col.e2eAvg": "Avg E2E",
  "history.col.recConc": "Rec concurrency",
  "history.legendThroughput": "Throughput t/s",
  "history.legendTtft": "Avg TTFT ms",

  "picker.title": "Question bank",
  "picker.none": "None",
  "picker.selected": "Selected {n}",
  "picker.all": "Select all",
  "picker.unselect": "None",
  "picker.custom": "Custom questions",
  "picker.customHint": " (one per line, rotated with your selection)",
  "picker.placeholder":
    "For example:\nGive a one-sentence summary of the key takeaway in this document.\nExplain the trade-off between cost and latency.",
  "picker.invalid":
    "Pick at least 1 question (or write a custom one) before starting a run.",
  "picker.valid":
    "Will rotate {total} questions ({bank} from the bank + {custom} custom).",

  "image.title": "Image gallery",
  "image.count": "{n}",
  "image.upload": "Upload",
  "image.uploading": "Uploading…",
  "image.none": "No image selected",
  "image.builtin": "Built-in",
  "image.mine": "My uploads",
  "image.delete": "Delete this image",
  "image.errType": "Only image files are allowed (png / jpg / webp…)",
  "image.errSize": "Image too large — upload something under 8MB",

  "model.placeholder": "Select or type a model…",
  "model.search": "Search or type a model name",
  "model.use": "Use “{name}”",
  "model.empty": "No models yet — type a name and press Enter",
} as const;

const zh: Record<keyof typeof en, string> = {
  "common.lang.en": "EN",
  "common.lang.zh": "中文",
  "common.lang.aria": "切换语言",
  "common.brand.sub": "推理性能压测台",
  "common.brand.homeAria": "LLM Bench 首页",
  "common.nav.new": "新建压测",
  "common.nav.history": "历史记录",
  "common.nav.aria": "主导航",
  "common.cancel": "取消",
  "common.save": "保存",
  "common.loading": "加载中…",
  "common.tip.aria": "参数说明",
  "common.status.pending": "排队中",
  "common.status.running": "运行中",
  "common.status.done": "完成",
  "common.status.failed": "失败",
  "common.status.cancelled": "已取消",
  "common.status.interrupted": "已中断",
  "common.mode.fixed.name": "固定并发",
  "common.mode.fixed.short": "固定",
  "common.mode.fixed.tagline": "单档压力跑一批请求",
  "common.mode.fixed.goal": "固定并发下测量时延与吞吐基线，适合快速健康检查",
  "common.mode.step.name": "阶梯压测",
  "common.mode.step.short": "阶梯",
  "common.mode.step.tagline": "并发逐档加压找拐点",
  "common.mode.step.goal": "并发从低到高逐档加压，自动找出吞吐拐点与推荐并发",
  "common.mode.open.name": "开环速率",
  "common.mode.open.short": "开环",
  "common.mode.open.tagline": "固定速率注入看排队",
  "common.mode.open.goal": "按固定速率注入请求，复现真实流量下的排队与饱和",
  "common.protocol.openai": "OpenAI 兼容",
  "common.protocol.anthropic": "Anthropic",
  "common.protocol.gemini": "Gemini",

  "home.title": "新建压测",
  "home.guide": "新手指引",
  "home.lastConfig": "已载入上次压测配置（API Key 已清空），可直接调整参数重新压测。",
  "home.clearNew": "清除并新建",
  "home.scenesTitle": "推荐场景",
  "home.scenesTip":
    "一键填好推荐参数（不改动模型连接），点选后可再微调；再次点选同一场景可恢复默认。",
  "home.resetParams": "恢复默认参数",
  "home.scene.quick.name": "单流延迟",
  "home.scene.quick.tag": "最快",
  "home.scene.quick.desc": "单用户时延基线，十几秒完成",
  "home.scene.ramp.name": "吞吐摸底",
  "home.scene.ramp.tag": "最常用",
  "home.scene.ramp.desc": "逐档加压，找出推荐并发",
  "home.scene.peak.name": "极限探测",
  "home.scene.peak.tag": "找饱和",
  "home.scene.peak.desc": "加压到饱和，探出真实上限",
  "home.scene.flow.name": "真实流量",
  "home.scene.flow.tag": "开环",
  "home.scene.flow.desc": "固定速率注入，看排队表现",
  "home.step.connect": "连接模型",
  "home.step.load": "压测方式",
  "home.step.advanced": "高级设置",
  "home.advancedHint": "通常保持默认即可",
  "home.field.protocol": "协议",
  "home.field.model": "模型名称",
  "home.field.modelTip":
    "要压测的目标模型。可点「获取模型列表」自动发现，也可直接输入名称。",
  "home.field.modelPlaceholder": "选择或输入模型…",
  "home.field.fetchModels": "获取模型列表",
  "home.field.modelsCount": "{n} 个可用模型",
  "home.field.baseUrl": "Endpoint Base URL",
  "home.field.baseUrlTip":
    "推理服务地址。本地 Ollama / vLLM 一般为 http://localhost:11434/v1 或 /v1 结尾的地址。",
  "home.field.apiKeyTip": "本地服务通常无需 API Key，可留空",
  "home.probe.probing": "正在检测连通性…",
  "home.probe.reachable": "服务可达",
  "home.probe.unreachable": "服务不可达",
  "home.probe.ttft": "TTFT {ttft}ms · 响应 {lat}ms",
  "home.probe.auto": "填写 Endpoint 与模型后自动检测连通性",
  "home.probe.recheck": "重新检测",
  "home.probe.quote": "“{text}”",

  "home.fixed.concurrency": "并发数",
  "home.fixed.concurrencyTip":
    "同时进行的请求数量（压力档位）。并发 4 表示任意时刻都有 4 个请求在同时打服务端。数值越大越能压出吞吐上限，但时延也会上升。",
  "home.fixed.totalReq": "总请求数",
  "home.fixed.totalReqTip":
    "本轮测试发送的请求总数。越多结果越稳定，20~50 个足够得出初步结论。与时长二选一，时长 > 0 时时长优先。",
  "home.fixed.duration": "运行时长（秒）",
  "home.fixed.durationTip":
    "改用时间控制测试长度：持续压满指定秒数后结束，用于观察吞吐稳定性。填 0 表示按请求数结束。",
  "home.step.levels": "并发序列",
  "home.step.levelsTip":
    "每个档位的并发数，按顺序逐档加压（如 1→2→4→8→16）。每档独立统计，最终画出并发-吞吐曲线，用于寻找拐点与饱和点。",
  "home.step.levelsHint": "英文逗号分隔，如 1,2,4,8,16",
  "home.step.req": "每档请求数",
  "home.step.reqTip": "每个档位发送的请求数。≥10 才有统计意义，≥20 结论置信度更高。与时长二选一。",
  "home.step.dur": "每档时长（秒）",
  "home.step.durTip": "改用时间控制每档长度，适合吞吐稳定但请求耗时差异大的场景。填 0 表示按请求数结束。",
  "home.step.autoStop": "自动停止（Saturation 剪枝）",
  "home.step.autoStopDesc":
    "连续两档吞吐增幅 < 3% 或错误率超阈值时提前结束剩余档位，节省时间",
  "home.step.preview": "档位预览：",
  "home.step.statsDur": "共 {total} 个档位 · 每档 {dur}s",
  "home.step.statsReq": "共 {total} 个档位 · {requests} 请求",
  "home.open.arrival": "到达速率（请求/秒）",
  "home.open.arrivalTip":
    "开环注入：每秒按固定节奏发出多少请求，即使服务端来不及处理也不会放慢。用于复现真实流量下用户变多时的表现。",
  "home.open.totalReqTip": "本轮注入的请求总数。与时长二选一，时长 > 0 时时长优先。",
  "home.open.durationTip": "持续按设定速率注入的秒数。填 0 表示按请求数结束。",
  "home.open.note":
    "开环模式用于复现真实流量下的饱和与 SLA 违反：请求按设定速率注入，即使服务端已排队也不节流。",

  "home.adv.inputLen": "输入长度（Token）",
  "home.adv.inputLenVision": "，附随所选图片",
  "home.adv.inputLenTip":
    "每条请求提示词的长度。长输入考验 prefill（首字延迟更明显），短输入更偏解码速度。数值需与模型上下文窗口匹配。",
  "home.adv.tokenPreset": "常用档位",
  "home.adv.tokenCustom": "自定义",
  "home.adv.tokenCustomPlaceholder": "自定义",
  "home.adv.maxOutput": "Max 输出 Tokens",
  "home.adv.maxOutputTip":
    "限制单个回答的最大长度。影响单请求耗时与总 token 消耗，保持与真实业务相近更可信。",
  "home.adv.timeout": "单请求超时（秒）",
  "home.adv.timeoutTip": "超过该时间未完成的请求记为 timeout 失败，计入错误率。应略大于预期最慢响应。",
  "home.adv.slaTitle": "SLA 阈值（自动分析判定）",
  "home.adv.slaTip":
    "合规判定线。阶梯压测后，最后一个未违反任何一条 SLA 的档位就是 SLA-Max；推荐并发 = min(Saturation, SLA-Max)。",
  "home.adv.slaTtft": "P95 TTFT ≤（秒）",
  "home.adv.slaTtftTip": "95% 的请求首字延迟应低于该值（2 秒 ≈ 对话可接受的等待上限）。",
  "home.adv.slaE2e": "P95 E2E ≤（秒）",
  "home.adv.slaE2eTip": "95% 的请求应在该时间内完整返回。按业务容忍度设定，如 15 秒。",
  "home.adv.slaErr": "错误率 ≤（比例）",
  "home.adv.slaErrTip": "允许的最大失败比例。0.005 = 0.5%。超阈值的档位视为不合规。",
  "home.adv.visionTitle": "视觉模型测试",
  "home.adv.visionDesc": "附带一张图片，测量多模态输入的时延表现；可从图片库选用或上传",

  "home.summary.title": "本次测试",
  "home.summary.scene": "场景 · {name}",
  "home.summary.custom": "自定义",
  "home.chip.pressure": "压力",
  "home.chip.requests": "请求量",
  "home.chip.io": "输入 / 输出",
  "home.chip.time": "预计耗时",
  "home.chip.pressureStep": "{levels} 并发",
  "home.chip.pressureOpen": "{rate} 请求/秒",
  "home.chip.pressureFixed": "{n} 并发",
  "home.chip.reqCount": "约 {n} 个",
  "home.chip.reqSustain": "持续 {s}s",
  "home.chip.ioVal": "{in} / {out} tok",
  "home.chip.timeProbing": "检测中…",
  "home.chip.timePending": "待检测",
  "home.chip.timeSec": "{n} 秒",
  "home.chip.timeMin": "{m} 分 {s} 秒",
  "home.check.title": "启动前检查",
  "home.check.modelOk": "模型名称已填写",
  "home.check.modelHint": "在 ① 连接模型中填写，或点「获取模型列表」选择",
  "home.check.qLoading": "问题库加载中…",
  "home.check.qOk": "问题库（默认题库 {n} 个）",
  "home.check.qEmpty": "问题库为空",
  "home.check.qHint": "默认已载入内置题库，可在 ③ 高级设置中自定义",
  "home.check.visionOk": "视觉测试图片",
  "home.check.visionHint": "在 ③ 高级设置中选择或上传图片",
  "home.startHint": "请先在 ① 连接模型 中填写模型名称",
  "home.notReady": "还有 {n} 项未就绪，请按提示补全后再开始",
  "home.start": "开始压测",
  "home.creating": "创建中…",

  "home.presets.title": "预设模板",
  "home.presets.count": "（{n} 个）",
  "home.presets.manage": "管理",
  "home.presets.done": "完成",
  "home.presets.desc": "把整套参数存成模板，下次一键恢复",
  "home.presets.placeholder": "选择预设载入",
  "home.presets.empty": "还没有预设",
  "home.presets.save": "存为预设",
  "home.presets.saved": "已保存 ✓",
  "home.presets.delete": "删除",
  "home.presetDialog.title": "保存预设",
  "home.presetDialog.desc": "将保存当前整套参数（连接、压测方式与高级选项），下次可一键恢复。",
  "home.presetDialog.placeholder": "预设名称",

  "home.err.model": "请填写模型名称",
  "home.err.baseUrl": "请先填写 Endpoint Base URL",
  "home.err.fetchModels": "获取模型列表失败",
  "home.err.questions": "请至少选择或填写 1 个问题（问题库不能为空）",
  "home.err.vision": "视觉测试已开启，请选择或上传一张图片",
  "home.err.tokens": "输入长度需为 ≥1 的数字",
  "home.err.arrival": "开环模式需填写 > 0 的到达速率",
  "home.err.openCount": "开环模式需设置总请求数或运行时长之一",
  "home.err.fixedCount": "请设置总请求数或运行时长之一",
  "home.err.stepCount": "阶梯模式需设置每档请求数或每档时长之一",

  "home.guide.title": "新手指引：三分钟看懂并发压测",
  "home.guide.close": "明白了，开始配置",
  "home.guide.s1.title": "压测到底在测什么？",
  "home.guide.s1.body":
    "四个核心指标：**TTFT**（首字延迟）决定“打开对话要等多久”的体感；**TPOT**（每字间隔）决定回答像不像打字机一样流畅；**吞吐 tokens/s** 是单位时间产出的 token 总量，代表服务端的产能；**错误率** 反映高压下服务还能不能正常响应。",
  "home.guide.s2.title": "“并发压测”解决什么问题？",
  "home.guide.s2.body":
    "核心问题是：**该给这个模型开几路并发？** 并发太低，机器闲着浪费产能；并发太高，请求开始排队——时延飙升、吞吐不再增长，甚至把服务打挂。本工具的「阶梯压测」会自动从 1 路逐档加压，画出吞吐曲线，标出饱和点并给出**推荐并发**：既不浪费产能，又不至于让用户等太久。",
  "home.guide.s3.title": "三种模式怎么选？",
  "home.guide.s3.body":
    "**固定并发** = 单点体检，先用它确认连接和基础性能；**阶梯压测** = 找上限（最常用），回答“该开几路”；**开环速率** = 模拟真实流量，按固定速率灌请求，观察服务端排队后的表现。",
  "home.guide.s4.title": "指标怎么读？",
  "home.guide.s4.body":
    "重点看 **P95**：它代表最差 5% 用户的体验，比平均值更真实。看阶梯图时，找“吞吐不再涨、TTFT 开始飙”的那一档——那就是性价比分界（Knee）；绿色竖线是系统给出的**推荐并发**，生产配置建议从它起步。",
  "home.guide.s5.title": "SLA 阈值是什么意思？",
  "home.guide.s5.body":
    "SLA 就是你的**性能承诺**，默认三条：95% 的请求 2 秒内出首字、15 秒内完整返回、错误率低于 0.5%。阶梯压测里，任何一个指标跌破承诺，该档就算“违约”——最后一个合规的档位叫 **SLA-Max**。**推荐并发 = min(饱和点, SLA-Max)**：既要拼产能，又不破坏承诺。纯本地调试可保持默认；接生产时，把阈值改成你们对外承诺的延迟要求。",
  "home.guide.s6.title": "第一次怎么跑？",
  "home.guide.s6.body":
    "顶部选**「吞吐摸底」**场景 → 在 ① 里填模型地址，填完会自动检测连通性，右侧显示“服务可达”即可 →「开始压测」。约 2~3 分钟后，监控页会给出结论卡：推荐并发、饱和点与每档时延对比。",

  "monitor.missingId": "缺少任务 ID",
  "monitor.missingIdHint": "请从历史记录进入，或新建一次压测查看实时结果。",
  "monitor.newRun": "新建压测",
  "monitor.viewHistory": "查看历史",
  "monitor.back": "返回",
  "monitor.created": "{base} · 创建于 {time}",
  "monitor.retest": "重新压测",
  "monitor.cancel": "取消测试",
  "monitor.config": "测试配置",
  "monitor.chip.mode": "模式",
  "monitor.chip.pressure": "压力",
  "monitor.chip.load": "请求量",
  "monitor.chip.io": "输入/输出",
  "monitor.chip.timeout": "超时",
  "monitor.chip.autoStop": "自动停止",
  "monitor.on": "开",
  "monitor.off": "关",
  "monitor.pressureStep": "{levels} 并发",
  "monitor.pressureOpen": "{rate} 请求/秒",
  "monitor.pressureFixed": "{n} 并发",
  "monitor.qtyStepDur": "每档 {dur}s × {n}",
  "monitor.qtyStepReq": "每档 {req} 请求 × {n}",
  "monitor.qtyFixed": "运行 {dur}s",
  "monitor.qtyTotal": "{n} 个请求",
  "monitor.progressCount": "请求完成",
  "monitor.progressDone": "已完成",
  "monitor.progressDoneN": "个请求",
  "monitor.progressPlanned": " · 计划运行 {dur}s",
  "monitor.progressFlight": " · {n} 进行中",
  "monitor.stepBadge": "第 {cur}/{total} 档 · 并发 {c}",
  "monitor.elapsed": "已耗时",
  "monitor.liveTps": "实时吞吐",
  "monitor.autoStopSat": "已触发自动停止：连续两档吞吐增幅低于 3%，提前结束剩余档位。",
  "monitor.autoStop": "已触发自动停止：{reason}",
  "monitor.st0": "排队中",
  "monitor.st1": "运行中",
  "monitor.st2": "完成",
  "monitor.st3": "失败",
  "monitor.st4": "已取消",
  "monitor.st5": "已中断",
  "monitor.metric.outTps": "输出吞吐",
  "monitor.metric.outTpsHint": "累计 {v} t/s · 输入 {i} t/s",
  "monitor.metric.ttft": "TTFT P95",
  "monitor.metric.ttftHint": "平均 {v} · P99 {p}",
  "monitor.metric.err": "错误率",
  "monitor.metric.errHint": "{n} 个失败",
  "monitor.metric.rps": "请求速率",
  "monitor.metric.rpsHint": "累计 {v} r/s",
  "monitor.metric.tpot": "平均 TPOT",
  "monitor.metric.tpotHint": "P95 {v} · P99 {p}",
  "monitor.metric.e2e": "平均 E2E",
  "monitor.metric.e2eHint": "P95 {v} · P99 {p}",
  "monitor.metric.itl": "ITL P50",
  "monitor.metric.itlHint": "P95 {v} · 出字间隔抖动",
  "monitor.metric.tokens": "Tokens",
  "monitor.metric.tokensHint": "输出累计 · 输入 {i}",
  "monitor.metric.live": "实时吞吐（5s 窗口）",
  "monitor.metric.liveHint": "最近 5 秒的滚动吞吐",
  "monitor.more": "更多指标",
  "monitor.analysis.title": "性能特征结论",
  "monitor.conf.high": "置信度 高",
  "monitor.conf.medium": "置信度 中",
  "monitor.conf.low": "置信度 低",
  "monitor.analysis.rec": "推荐并发（生产起步值）",
  "monitor.analysis.recHint": "取 Saturation 与 SLA-Max 的较小值",
  "monitor.analysis.recUnit": "路",
  "monitor.analysis.maxRps": "最大可持续 RPS",
  "monitor.analysis.maxRpsHint": "推荐档位对应的请求速率",
  "monitor.analysis.stops.all": "跑完全部档位",
  "monitor.analysis.stops.saturation": "自动停止：吞吐进入平台期",
  "monitor.analysis.stops.error_rate": "自动停止：错误率超阈值",
  "monitor.analysis.slaLine":
    "SLA：P95 TTFT ≤ {ttft}s · P95 E2E ≤ {e2e}s · 错误率 ≤ {rate}%",
  "monitor.analysis.single": "单并发基线",
  "monitor.analysis.maxTp": "最大吞吐档",
  "monitor.analysis.sat": "Saturation 饱和点",
  "monitor.analysis.satNone": "未出现",
  "monitor.analysis.satHint": "吞吐增幅 < 5% 出现在 {a} → {b} 之间",
  "monitor.analysis.satRising": "各档吞吐持续增长",
  "monitor.analysis.knee": "Knee 拐点",
  "monitor.analysis.kneeNone": "未检出",
  "monitor.analysis.kneeHint": "吞吐收益递减且 P95 TTFT 明显恶化",
  "monitor.analysis.slaMax": "SLA-Max 最大合规并发",
  "monitor.analysis.slaMaxNone": "无合规档",
  "monitor.analysis.slaMaxHint": "最后一条未违反任何 SLA 的档位",
  "monitor.analysis.levels": "测试档位",
  "monitor.analysis.levelsHint": "SLA 合规至 {n} 并发",
  "monitor.analysis.footer": "自动基于吞吐增幅、P95 TTFT 与 SLA 阈值判定",
  "monitor.analysis.retest": "用推荐并发复测",
  "monitor.conn": "并发",
  "monitor.chart.stepTitle": "并发阶梯 · 吞吐 / RPS",
  "monitor.chart.latencyTitle": "时延趋势（TTFT / E2E / TPOT）",
  "monitor.chart.liveTitle": "实时吞吐（窗口 5s）",
  "monitor.chart.histTitle": "TTFT 分布直方图",
  "monitor.chart.timeS": "时间(s)",
  "monitor.chart.sec": "秒",
  "monitor.chart.count": "数量",
  "monitor.chart.windowTps": "窗口吞吐",
  "monitor.chart.throughput": "吞吐",
  "monitor.chart.ttftDist": "TTFT 分布",
  "monitor.chart.markRec": "推荐 {n}",
  "monitor.chart.markSat": "饱和 {n}",
  "monitor.chart.markKnee": "拐点 {n}",
  "monitor.chart.markSla": "SLA {n}",
  "monitor.chart.empty1": "等待第一档完成…",
  "monitor.chart.empty0": "暂无数据",
  "monitor.table.stepsTitle": "阶梯压测结果",
  "monitor.table.rec": "推荐",
  "monitor.table.logTitle": "请求明细",
  "monitor.table.logRecent": "最近 {a} / 共 {b} 条",
  "monitor.table.level": "档位",
  "monitor.table.status": "状态",
  "monitor.table.out": "输出",
  "monitor.table.in": "输入",
  "monitor.table.err": "错误",
  "monitor.table.conc": "并发",
  "monitor.table.req": "请求数",
  "monitor.table.done": "完成",
  "monitor.table.tpsThr": "吞吐 t/s",
  "monitor.table.tpsOut": "输出 t/s",
  "monitor.table.tpsIn": "输入 t/s",
  "monitor.table.errRate": "错误率",

  "history.title": "历史记录",
  "history.refresh": "刷新",
  "history.filterModel": "按模型筛选…",
  "history.filterStatusAll": "全部状态",
  "history.filterModeAll": "全部模式",
  "history.selected": "已选 {n} 个任务",
  "history.compare": "查看对比 ↓",
  "history.clear": "清空",
  "history.stats.total": "任务总数",
  "history.stats.done": "已完成",
  "history.stats.running": "{n} 个进行中",
  "history.stats.avgTps": "平均吞吐",
  "history.stats.maxTps": "最高吞吐",
  "history.emptyNone": "暂无测试记录",
  "history.emptyFilter": "没有符合筛选条件的记录",
  "history.newRun": "新建压测",
  "history.col.model": "模型",
  "history.col.protoMode": "协议 / 模式",
  "history.col.status": "状态",
  "history.col.done": "完成",
  "history.col.throughput": "吞吐 t/s",
  "history.col.ttftAvg": "TTFT 均",
  "history.col.tpotAvg": "TPOT 均",
  "history.col.rps": "RPS",
  "history.col.errRate": "错误率",
  "history.col.created": "创建时间",
  "history.col.actions": "操作",
  "history.row.retest": "以此配置重新压测",
  "history.row.delete": "删除",
  "history.row.view": "点击查看测试结果",
  "history.toggle.deselect": "取消全选",
  "history.toggle.select": "全选已完成任务",
  "history.compareTitle": "结果对比（已选 {n} 个任务）",
  "history.col.pattern": "模式",
  "history.col.tpsOut": "输出 t/s",
  "history.col.ttftAvgP95": "TTFT 均/P95",
  "history.col.itl": "ITL P50",
  "history.col.e2eAvg": "E2E 均",
  "history.col.recConc": "推荐并发",
  "history.legendThroughput": "吞吐 t/s",
  "history.legendTtft": "平均 TTFT ms",

  "picker.title": "问题库",
  "picker.none": "未选择",
  "picker.selected": "已选 {n}",
  "picker.all": "全选",
  "picker.unselect": "全不选",
  "picker.custom": "自定义问题",
  "picker.customHint": "（每行一个，将与所选问题一起轮流使用）",
  "picker.placeholder":
    "例如：\n请用一句话总结这份文档的核心结论。\nExplain the trade-off between cost and latency.",
  "picker.invalid": "至少需要选择 1 个问题（或填写 1 个自定义问题），否则无法开始压测。",
  "picker.valid": "本次将轮流使用 {total} 个问题（题库 {bank} + 自定义 {custom}）。",

  "image.title": "图片库",
  "image.count": "{n} 张",
  "image.upload": "上传图片",
  "image.uploading": "上传中…",
  "image.none": "未选择图片",
  "image.builtin": "内置图片",
  "image.mine": "我的上传",
  "image.delete": "删除这张图片",
  "image.errType": "仅支持图片文件（png / jpg / webp 等）",
  "image.errSize": "图片过大，请上传小于 8MB 的图片",

  "model.placeholder": "选择或输入模型…",
  "model.search": "搜索或直接输入模型名",
  "model.use": "使用“{name}”",
  "model.empty": "暂无模型，输入名称后回车提交",
};

export type TKey = keyof typeof en;

export interface I18nCtx {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: TKey, vars?: Vars) => string;
  tr: (key: TKey, vars?: Vars) => React.ReactNode;
}

const LangContext = React.createContext<I18nCtx | null>(null);

function getInitialLang(): Lang {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "zh" || v === "en" ? v : "en";
  } catch {
    return "en";
  }
}

const dicts: Record<Lang, Record<TKey, string>> = {
  en,
  zh,
};

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = React.useState<Lang>(getInitialLang);

  const applyLang = React.useCallback((l: Lang) => {
    document.documentElement.lang = l === "zh" ? "zh-CN" : "en";
  }, []);

  React.useEffect(() => {
    applyLang(lang);
  }, [lang, applyLang]);

  const setLang = React.useCallback(
    (l: Lang) => {
      setLangState(l);
      try {
        window.localStorage.setItem(STORAGE_KEY, l);
      } catch {
        /* ignore */
      }
      applyLang(l);
    },
    [applyLang],
  );

  const t = React.useCallback(
    (key: TKey, vars?: Vars) => {
      let s: string = dicts[lang][key] ?? en[key] ?? key;
      if (vars) {
        for (const [k, v] of Object.entries(vars)) {
          s = s.split(`{${k}}`).join(String(v));
        }
      }
      return s;
    },
    [lang],
  );

  const tr = React.useCallback(
    (key: TKey, vars?: Vars) => {
      const s = t(key, vars);
      const parts = s.split("**");
      if (parts.length === 1) return s;
      return parts.map((p, i) =>
        i % 2 === 1 ? (
          <b key={i}>{p}</b>
        ) : (
          <React.Fragment key={i}>{p}</React.Fragment>
        ),
      );
    },
    [t],
  );

  const value = React.useMemo<I18nCtx>(
    () => ({ lang, setLang, t, tr }),
    [lang, setLang, t, tr],
  );

  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export function useI18n(): I18nCtx {
  const ctx = React.useContext(LangContext);
  if (!ctx) throw new Error("useI18n must be used within a LangProvider");
  return ctx;
}

export function LangToggle() {
  const { lang, setLang, t } = useI18n();
  const base =
    "inline-flex h-7 cursor-pointer items-center rounded px-2.5 font-medium transition-colors";
  return (
    <div
      className="ml-auto flex w-fit items-center gap-0.5 rounded-md bg-muted p-0.5 text-xs"
      role="group"
      aria-label={t("common.lang.aria")}
    >
      <button
        type="button"
        onClick={() => setLang("en")}
        aria-pressed={lang === "en"}
        className={`${base} ${
          lang === "en" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {t("common.lang.en")}
      </button>
      <button
        type="button"
        onClick={() => setLang("zh")}
        aria-pressed={lang === "zh"}
        className={`${base} ${
          lang === "zh" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {t("common.lang.zh")}
      </button>
    </div>
  );
}