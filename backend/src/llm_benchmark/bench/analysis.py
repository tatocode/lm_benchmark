from __future__ import annotations

SATURATION_GROWTH = 0.05
KNEE_TTFT_GROWTH = 0.5
MIN_COMPLETION_RATIO = 0.9

DEFAULT_SLA = {
    "ttft_p95_s": 2.0,
    "e2e_p95_s": 15.0,
    "error_rate": 0.005,
}


def _step_violates(s: dict, sla: dict) -> bool:
    if s.get("ttft_p95", 0) / 1000.0 > sla["ttft_p95_s"]:
        return True
    if s.get("e2e_p95", 0) / 1000.0 > sla["e2e_p95_s"]:
        return True
    if s.get("error_rate", 0.0) > sla["error_rate"]:
        return True
    planned = s.get("planned") or 0
    if planned > 0 and s.get("completed", 0) / planned < MIN_COMPLETION_RATIO:
        return True
    return False


def _confident(ordered: list[dict]) -> str:
    n = len(ordered)
    min_done = min((s.get("completed", 0) for s in ordered), default=0)
    if n >= 4 and min_done >= 20:
        return "high"
    if n >= 3 and min_done >= 5:
        return "medium"
    if n >= 2 and min_done >= 1:
        return "medium"
    return "low"


def analyze_steps(
    steps: list[dict], sla: dict | None = None, stop_reason: str = ""
) -> dict:
    """根据并发阶梯结果自动检测 Saturation / Knee / SLA-Max 并给出推荐值。"""
    sla = {**DEFAULT_SLA, **(sla or {})}
    result: dict = {
        "ok": False,
        "stop_reason": stop_reason,
        "sla": sla,
        "single": {},
        "max_throughput": {},
        "saturation": {"concurrency": None, "range": None},
        "knee": {"concurrency": None},
        "sla_max_concurrency": None,
        "recommended_concurrency": None,
        "max_sustainable_rps": None,
        "confidence": "low",
    }
    if not steps:
        return result

    ordered = sorted(steps, key=lambda s: s.get("concurrency", 0))
    result["ok"] = True
    result["confidence"] = _confident(ordered)

    first = ordered[0]
    result["single"] = {
        "concurrency": first.get("concurrency"),
        "output_tps": first.get("output_tps", first.get("throughput_tps", 0)),
        "input_tps": first.get("input_tps", 0),
        "rps": first.get("rps", 0),
        "ttft_p95_ms": first.get("ttft_p95", 0),
        "e2e_p95_ms": first.get("e2e_p95", 0),
        "tpot_p95_ms": first.get("tpot_p95", 0),
        "itl_p95_ms": first.get("itl_p95", 0),
    }

    peak = max(ordered, key=lambda s: s.get("output_tps", 0))
    result["max_throughput"] = {
        "concurrency": peak.get("concurrency"),
        "output_tps": peak.get("output_tps", peak.get("throughput_tps", 0)),
        "input_tps": peak.get("input_tps", 0),
        "rps": peak.get("rps", 0),
    }

    # Saturation: 第一次吞吐相对增幅 < 5% 的位置，取其前一档为平台期起点
    for i in range(1, len(ordered)):
        prev = ordered[i - 1].get("output_tps") or ordered[i - 1].get(
            "throughput_tps", 0
        )
        cur = ordered[i].get("output_tps") or ordered[i].get("throughput_tps", 0)
        base = max(prev, 1e-6)
        if (cur - prev) / base < SATURATION_GROWTH:
            result["saturation"] = {
                "concurrency": ordered[i - 1].get("concurrency"),
                "range": [
                    ordered[i - 1].get("concurrency"),
                    ordered[i].get("concurrency"),
                ],
            }
            break

    # Knee: 吞吐收益递减(<10%) 且 P95 TTFT 恶化(>=50%) 的第一个档
    for i in range(1, len(ordered)):
        prev_tps = ordered[i - 1].get("output_tps") or ordered[i - 1].get(
            "throughput_tps", 0
        )
        cur_tps = ordered[i].get("output_tps") or ordered[i].get("throughput_tps", 0)
        prev = ordered[i - 1].get("ttft_p95", 0) or 0
        cur = ordered[i].get("ttft_p95", 0) or 0
        growth = (cur - prev) / max(prev, 1.0)
        tps_growth = (cur_tps - prev_tps) / max(prev_tps, 1e-6)
        if growth >= KNEE_TTFT_GROWTH and tps_growth < 0.10:
            result["knee"] = {"concurrency": ordered[i].get("concurrency")}
            break

    # SLA Max: 从低到高最后一个未违反任何 SLA 的档
    sla_max = None
    for s in ordered:
        if not _step_violates(s, sla):
            sla_max = s.get("concurrency")
        else:
            break
    result["sla_max_concurrency"] = sla_max

    sat = result["saturation"]["concurrency"]
    candidates = [c for c in (sat, sla_max) if c is not None]
    recommended = min(candidates) if candidates else None
    result["recommended_concurrency"] = recommended

    rps = None
    if recommended is not None:
        target = next(
            (s for s in ordered if s.get("concurrency") == recommended), None
        )
        if target is not None:
            rps = target.get("rps", 0)
    if rps is None:
        rps = max((s.get("rps", 0) for s in ordered), default=None)
    result["max_sustainable_rps"] = rps

    if stop_reason == "error_rate" and result["confidence"] == "high":
        result["confidence"] = "medium"
    return result


def check_auto_stop(
    summary: dict,
    prev: dict | None,
    streak: int,
    error_rate_threshold: float,
) -> tuple[str, int]:
    """阶梯逐档结束时的自动停止判定。返回 (stop_reason, new_sat_streak)。"""
    if summary.get("completed", 0) >= 5 and summary.get("error_rate", 0.0) > error_rate_threshold:
        return "error_rate", streak
    if prev is None:
        return "", streak
    prev_tps = prev.get("output_tps") or prev.get("throughput_tps") or 0
    cur_tps = summary.get("output_tps") or summary.get("throughput_tps") or 0
    growth = (cur_tps - prev_tps) / max(prev_tps, 1e-6)
    streak = streak + 1 if growth < 0.03 else 0
    if streak >= 2:
        return "saturation", streak
    return "", streak
