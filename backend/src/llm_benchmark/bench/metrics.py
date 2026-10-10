import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from time import perf_counter

WINDOW_S = 5.0


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _stats(values: list[float]) -> dict:
    if not values:
        return {
            "avg": 0.0,
            "p50": 0.0,
            "p90": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "max": 0.0,
        }
    sv = sorted(values)
    return {
        "avg": round(statistics.fmean(values), 2),
        "p50": round(percentile(sv, 50), 2),
        "p90": round(percentile(sv, 90), 2),
        "p95": round(percentile(sv, 95), 2),
        "p99": round(percentile(sv, 99), 2),
        "max": round(sv[-1], 2),
    }


@dataclass
class RecordResult:
    idx: int
    step: int = -1
    status: str = "ok"
    ttft_ms: float | None = None
    e2e_ms: float | None = None
    tpot_ms: float | None = None
    output_tokens: int = 0
    input_tokens: int = 0
    tok_per_s: float | None = None
    itl_p50_ms: float | None = None
    error_class: str = "ok"
    error: str = ""
    t_start: float = 0.0
    t_end: float = 0.0
    token_source: str = "api"
    itls: list[float] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "idx": self.idx,
            "step": self.step,
            "status": self.status,
            "ttft_ms": self.ttft_ms,
            "e2e_ms": self.e2e_ms,
            "tpot_ms": self.tpot_ms,
            "output_tokens": self.output_tokens,
            "input_tokens": self.input_tokens,
            "tok_per_s": self.tok_per_s,
            "itl_p50_ms": self.itl_p50_ms,
            "error_class": self.error_class,
            "error": self.error,
            "t_start": round(self.t_start, 3),
            "t_end": round(self.t_end, 3),
        }


MAX_ITL_SAMPLES = 50000


@dataclass
class Aggregator:
    planned: int
    completed: int = 0
    errors: int = 0
    in_flight: int = 0
    tokens_total: int = 0
    input_tokens_total: int = 0
    ttfts: list[float] = field(default_factory=list)
    e2es: list[float] = field(default_factory=list)
    tpots: list[float] = field(default_factory=list)
    itls: list[float] = field(default_factory=list)
    error_breakdown: dict = field(default_factory=dict)
    window: deque = field(default_factory=deque)
    t_start: float = field(default_factory=perf_counter)

    def on_start(self) -> None:
        self.in_flight += 1

    def on_end(self) -> None:
        self.in_flight = max(0, self.in_flight - 1)

    def add(self, rec: RecordResult) -> None:
        self.completed += 1
        self.tokens_total += rec.output_tokens
        self.input_tokens_total += rec.input_tokens
        now = perf_counter()
        self.window.append((now, rec.output_tokens))
        if rec.status == "ok":
            if rec.ttft_ms is not None:
                self.ttfts.append(rec.ttft_ms)
            if rec.e2e_ms is not None:
                self.e2es.append(rec.e2e_ms)
            if rec.tpot_ms is not None:
                self.tpots.append(rec.tpot_ms)
            if rec.itls:
                if len(self.itls) < MAX_ITL_SAMPLES:
                    self.itls.extend(rec.itls)
                    del self.itls[MAX_ITL_SAMPLES:]
            elif rec.itl_p50_ms is not None:
                self.itls.append(rec.itl_p50_ms)
        else:
            self.errors += 1
            cls = rec.error_class if rec.error_class not in ("", "ok") else "other"
            self.error_breakdown[cls] = self.error_breakdown.get(cls, 0) + 1

    def _prune(self, now: float) -> None:
        while self.window and now - self.window[0][0] > WINDOW_S:
            self.window.popleft()

    def snapshot(self) -> dict:
        now = perf_counter()
        self._prune(now)
        elapsed = max(1e-6, now - self.t_start)
        win_tokens = sum(t for _, t in self.window)
        win_span = min(elapsed, WINDOW_S)
        return {
            "elapsed_s": round(elapsed, 2),
            "planned": self.planned,
            "completed": self.completed,
            "errors": self.errors,
            "in_flight": self.in_flight,
            "tokens_total": self.tokens_total,
            "input_tokens_total": self.input_tokens_total,
            "throughput_tps": round(self.tokens_total / elapsed, 2),
            "output_tps": round(self.tokens_total / elapsed, 2),
            "input_tps": round(self.input_tokens_total / elapsed, 2),
            "window_tps": round(win_tokens / win_span, 2),
            "rps": round(self.completed / elapsed, 3),
            "window_rps": round(len(self.window) / win_span, 3),
            "ttft_ms": _stats(self.ttfts),
            "e2e_ms": _stats(self.e2es),
            "tpot_ms": _stats(self.tpots),
            "itl_ms": _stats(self.itls),
            "error_rate": round(self.errors / self.completed, 4) if self.completed else 0.0,
            "error_breakdown": dict(self.error_breakdown),
        }


def step_summary(snapshot: dict, concurrency: int) -> dict:
    return {
        "concurrency": concurrency,
        "planned": snapshot["planned"],
        "completed": snapshot["completed"],
        "errors": snapshot["errors"],
        "ttft_avg": snapshot["ttft_ms"]["avg"],
        "ttft_p50": snapshot["ttft_ms"]["p50"],
        "ttft_p95": snapshot["ttft_ms"]["p95"],
        "ttft_p99": snapshot["ttft_ms"]["p99"],
        "e2e_avg": snapshot["e2e_ms"]["avg"],
        "e2e_p50": snapshot["e2e_ms"]["p50"],
        "e2e_p95": snapshot["e2e_ms"]["p95"],
        "e2e_p99": snapshot["e2e_ms"]["p99"],
        "tpot_avg": snapshot["tpot_ms"]["avg"],
        "tpot_p50": snapshot["tpot_ms"]["p50"],
        "tpot_p95": snapshot["tpot_ms"]["p95"],
        "itl_p50": snapshot["itl_ms"]["p50"],
        "itl_p95": snapshot["itl_ms"]["p95"],
        "throughput_tps": snapshot["throughput_tps"],
        "output_tps": snapshot["output_tps"],
        "input_tps": snapshot["input_tps"],
        "rps": snapshot["rps"],
        "error_rate": snapshot["error_rate"],
        "error_breakdown": snapshot["error_breakdown"],
    }


def aggregate_records(records: list[dict], planned: int = 0) -> Aggregator:
    agg = Aggregator(planned=planned or len(records))
    for r in records:
        rec = RecordResult(
            idx=r.get("idx", 0),
            step=r.get("step", -1),
            status=r.get("status", "ok"),
            ttft_ms=r.get("ttft_ms"),
            e2e_ms=r.get("e2e_ms"),
            tpot_ms=r.get("tpot_ms"),
            output_tokens=r.get("output_tokens", 0),
            input_tokens=r.get("input_tokens", 0),
            tok_per_s=r.get("tok_per_s"),
            itl_p50_ms=r.get("itl_p50_ms"),
            error_class=r.get("error_class", "ok"),
            error=r.get("error", ""),
            t_start=r.get("t_start", 0.0),
            t_end=r.get("t_end", 0.0),
        )
        if rec.itl_p50_ms is not None and not rec.itls:
            rec.itls = [rec.itl_p50_ms]
        agg.add(rec)
    agg.t_start = perf_counter() - 1.0
    return agg
