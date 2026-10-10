from llm_benchmark.bench.analysis import (
    analyze_steps,
    check_auto_stop,
)

# 基于 GPT 方法论文档中的示例数据表
GPT_STEPS = [
    {"concurrency": 1, "output_tps": 80, "input_tps": 1200, "rps": 0.15,
     "ttft_p95": 95, "e2e_p95": 6200, "tpot_p95": 12, "itl_p95": 13,
     "error_rate": 0.0, "planned": 30, "completed": 30},
    {"concurrency": 2, "output_tps": 150, "input_tps": 2300, "rps": 0.29,
     "ttft_p95": 100, "e2e_p95": 6500, "tpot_p95": 13, "itl_p95": 14,
     "error_rate": 0.0, "planned": 30, "completed": 30},
    {"concurrency": 4, "output_tps": 285, "input_tps": 4400, "rps": 0.55,
     "ttft_p95": 120, "e2e_p95": 6800, "tpot_p95": 14, "itl_p95": 15,
     "error_rate": 0.0, "planned": 30, "completed": 30},
    {"concurrency": 8, "output_tps": 490, "input_tps": 7600, "rps": 0.95,
     "ttft_p95": 150, "e2e_p95": 7100, "tpot_p95": 15, "itl_p95": 16,
     "error_rate": 0.0, "planned": 30, "completed": 30},
    {"concurrency": 16, "output_tps": 780, "input_tps": 12000, "rps": 1.55,
     "ttft_p95": 250, "e2e_p95": 7800, "tpot_p95": 16, "itl_p95": 17,
     "error_rate": 0.0, "planned": 30, "completed": 30},
    {"concurrency": 32, "output_tps": 1020, "input_tps": 16000, "rps": 2.05,
     "ttft_p95": 510, "e2e_p95": 9200, "tpot_p95": 18, "itl_p95": 20,
     "error_rate": 0.0, "planned": 30, "completed": 30},
    {"concurrency": 64, "output_tps": 1050, "input_tps": 17000, "rps": 2.10,
     "ttft_p95": 1800, "e2e_p95": 14000, "tpot_p95": 22, "itl_p95": 25,
     "error_rate": 0.001, "planned": 30, "completed": 30},
    {"concurrency": 128, "output_tps": 1040, "input_tps": 16000, "rps": 2.08,
     "ttft_p95": 7200, "e2e_p95": 32000, "tpot_p95": 28, "itl_p95": 35,
     "error_rate": 0.028, "planned": 30, "completed": 30},
]

SLA = {"ttft_p95_s": 2.0, "e2e_p95_s": 15.0, "error_rate": 0.005}


def test_full_analysis_from_gpt_example():
    r = analyze_steps(GPT_STEPS, sla=SLA)
    assert r["ok"] is True
    assert r["confidence"] == "high"

    # 单请求基线 = 最低并发档
    assert r["single"]["concurrency"] == 1
    assert r["single"]["output_tps"] == 80

    # 最大吞吐在 64 档
    assert r["max_throughput"]["concurrency"] == 64
    assert r["max_throughput"]["output_tps"] == 1050

    # Saturation: 32→64 仅 +2.9% < 5%，平台期起点为 32
    assert r["saturation"]["concurrency"] == 32
    assert r["saturation"]["range"] == [32, 64]

    # Knee: 64 档吞吐停止增长(+2.9%)且 P95 TTFT 恶化 253% -> 64
    assert r["knee"]["concurrency"] == 64

    # SLA Max: 64 档全部满足 (1.8s<2s, 14s<15s, 0.1%<0.5%)，128 档违反
    assert r["sla_max_concurrency"] == 64

    # 推荐 = min(saturation, sla_max) = 32
    assert r["recommended_concurrency"] == 32

    # 最大可持续 RPS 取推荐档
    assert r["max_sustainable_rps"] == 2.05
    assert r["sla"] == SLA
    assert r["stop_reason"] == ""


def test_sla_violation_narrows_sla_max():
    steps = [dict(s) for s in GPT_STEPS[:7]]
    # 64 档 E2E P95 超过 15s SLA
    steps[6]["e2e_p95"] = 16000
    r = analyze_steps(steps, sla=SLA)
    assert r["sla_max_concurrency"] == 32
    assert r["recommended_concurrency"] == 32


def test_error_rate_breaks_sla_max():
    steps = [dict(s) for s in GPT_STEPS[:6]]
    steps[5]["error_rate"] = 0.1
    r = analyze_steps(steps, sla=SLA)
    assert r["sla_max_concurrency"] == 16


def test_empty_and_single_step():
    assert analyze_steps([])["ok"] is False

    single = [GPT_STEPS[0]]
    r = analyze_steps(single, sla=SLA)
    assert r["ok"] is True
    assert r["saturation"]["concurrency"] is None
    assert r["knee"]["concurrency"] is None
    assert r["sla_max_concurrency"] == 1
    assert r["recommended_concurrency"] == 1
    assert r["confidence"] == "low"


def test_throughput_keeps_growing_no_saturation():
    steps = [
        {"concurrency": 1, "output_tps": 100, "rps": 1.0,
         "ttft_p95": 50, "e2e_p95": 100, "error_rate": 0.0,
         "planned": 20, "completed": 20},
        {"concurrency": 2, "output_tps": 200, "rps": 2.0,
         "ttft_p95": 60, "e2e_p95": 120, "error_rate": 0.0,
         "planned": 20, "completed": 20},
        {"concurrency": 4, "output_tps": 400, "rps": 4.0,
         "ttft_p95": 70, "e2e_p95": 140, "error_rate": 0.0,
         "planned": 20, "completed": 20},
    ]
    r = analyze_steps(steps, sla=SLA)
    assert r["saturation"]["concurrency"] is None
    assert r["knee"]["concurrency"] is None
    assert r["sla_max_concurrency"] == 4
    assert r["recommended_concurrency"] == 4


def test_stop_reason_downgrades_confidence():
    r = analyze_steps(GPT_STEPS, sla=SLA, stop_reason="error_rate")
    assert r["stop_reason"] == "error_rate"
    assert r["confidence"] == "medium"


def test_check_auto_stop_error_rate():
    summary = {"completed": 6, "error_rate": 1.0, "output_tps": 0}
    reason, streak = check_auto_stop(summary, None, 0, 0.005)
    assert reason == "error_rate"

    # 请求数太少时以数据完整性优先，不因错误率停止
    summary_small = {"completed": 3, "error_rate": 1.0, "output_tps": 0}
    reason, _ = check_auto_stop(summary_small, None, 0, 0.005)
    assert reason == ""


def test_check_auto_stop_saturation_streak():
    prev = {"completed": 10, "error_rate": 0.0, "output_tps": 100}
    # 增长 < 3% 连续两档 -> 停
    slow = {"completed": 10, "error_rate": 0.0, "output_tps": 101}
    reason, streak = check_auto_stop(slow, prev, 0, 0.005)
    assert reason == "" and streak == 1
    reason, streak = check_auto_stop(slow, prev, streak, 0.005)
    assert reason == "saturation" and streak == 2

    # 增长恢复则计数清零
    fast = {"completed": 10, "error_rate": 0.0, "output_tps": 200}
    reason, streak = check_auto_stop(fast, prev, 1, 0.005)
    assert reason == "" and streak == 0
