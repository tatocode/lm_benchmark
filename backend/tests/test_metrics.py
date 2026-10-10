from llm_benchmark.bench.metrics import (
    Aggregator,
    RecordResult,
    aggregate_records,
    percentile,
    step_summary,
)


def test_percentile():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(vals, 0) == 1.0
    assert percentile(vals, 100) == 5.0
    assert percentile(vals, 50) == 3.0
    assert percentile([], 50) == 0.0
    assert percentile([7.0], 90) == 7.0


def _rec(idx: int, ok: bool = True) -> RecordResult:
    if ok:
        return RecordResult(
            idx=idx,
            status="ok",
            ttft_ms=100.0 + idx,
            e2e_ms=1000.0 + idx,
            tpot_ms=20.0,
            output_tokens=50,
            t_start=float(idx),
            t_end=float(idx) + 1,
        )
    return RecordResult(idx=idx, status="error", error="boom")


def test_aggregator_snapshot():
    agg = Aggregator(planned=3)
    agg.on_start()
    agg.on_end()
    for i in range(3):
        agg.add(_rec(i))
    agg.add(_rec(9, ok=False))
    snap = agg.snapshot()
    assert snap["planned"] == 3
    assert snap["completed"] == 4
    assert snap["errors"] == 1
    assert snap["tokens_total"] == 150
    assert snap["ttft_ms"]["avg"] > 0
    assert snap["error_rate"] == 0.25
    assert snap["in_flight"] == 0


def test_step_summary_keys():
    agg = Aggregator(planned=2)
    agg.add(_rec(0))
    agg.add(_rec(1))
    summary = step_summary(agg.snapshot(), concurrency=4)
    assert summary["concurrency"] == 4
    assert summary["completed"] == 2
    assert "throughput_tps" in summary


def test_aggregate_records_from_dicts():
    records = [
        {"idx": 0, "status": "ok", "ttft_ms": 10.0, "e2e_ms": 100.0, "output_tokens": 10},
        {"idx": 1, "status": "timeout", "error": "timeout"},
    ]
    agg = aggregate_records(records, planned=2)
    snap = agg.snapshot()
    assert snap["completed"] == 2
    assert snap["errors"] == 1


def test_aggregator_input_output_itl_and_breakdown():
    agg = Aggregator(planned=2)
    agg.add(
        RecordResult(
            idx=0,
            status="ok",
            ttft_ms=10.0,
            e2e_ms=100.0,
            tpot_ms=5.0,
            output_tokens=50,
            input_tokens=120,
            itl_p50_ms=4.0,
            itls=[3.0, 4.0, 5.0],
        )
    )
    agg.add(
        RecordResult(idx=1, status="error", error_class="http_5xx", error="HTTP 503")
    )
    snap = agg.snapshot()
    assert snap["input_tokens_total"] == 120
    assert snap["tokens_total"] == 50
    assert snap["output_tps"] > 0
    assert snap["input_tps"] > 0
    assert snap["itl_ms"]["p50"] in (3.0, 4.0, 5.0)
    assert "p95" in snap["ttft_ms"]
    assert snap["error_breakdown"] == {"http_5xx": 1}


def test_record_as_dict_contains_new_fields():
    rec = RecordResult(
        idx=0,
        status="ok",
        input_tokens=7,
        itl_p50_ms=3.5,
        error_class="ok",
        output_tokens=20,
    )
    d = rec.as_dict()
    assert d["input_tokens"] == 7
    assert d["itl_p50_ms"] == 3.5
    assert d["error_class"] == "ok"
    assert "itls" not in d


def test_step_summary_new_fields():
    agg = Aggregator(planned=1)
    agg.add(
        RecordResult(
            idx=0,
            status="ok",
            ttft_ms=120.0,
            e2e_ms=900.0,
            tpot_ms=8.0,
            output_tokens=40,
            input_tokens=80,
            itls=[7.0, 9.0],
        )
    )
    summary = step_summary(agg.snapshot(), concurrency=8)
    assert summary["concurrency"] == 8
    assert summary["ttft_p95"] == 120.0
    assert summary["e2e_p95"] == 900.0
    assert summary["tpot_p95"] == 8.0
    assert summary["itl_p95"] == 8.9  # [7,9] 线性插值 p95
    assert summary["output_tps"] > 0
    assert summary["input_tps"] > 0
    assert summary["error_breakdown"] == {}


def test_aggregate_records_restores_new_fields():
    records = [
        {
            "idx": 0,
            "status": "ok",
            "ttft_ms": 10.0,
            "e2e_ms": 100.0,
            "output_tokens": 10,
            "input_tokens": 64,
            "itl_p50_ms": 4.5,
            "error_class": "ok",
        }
    ]
    agg = aggregate_records(records, planned=1)
    snap = agg.snapshot()
    assert snap["input_tokens_total"] == 64
    assert snap["itl_ms"]["p50"] == 4.5
