"""Time estimates come only from recorded runs."""
import pytest

pytest.importorskip("langgraph", reason="make setup installs the agent extra")
from dd2_agent import timings


def test_estimate_is_the_median_of_past_runs_per_group(tmp_path):
    p = tmp_path / "t.jsonl"
    timings.record(p, "single", {"drc": 4.0, "spice": 10.0})
    timings.record(p, "single", {"drc": 6.0, "spice": 12.0})
    timings.record(p, "single", {"drc": 50.0})
    timings.record(p, "multi", {"drc": 8.0})
    e = timings.estimates(p)
    assert e["single"]["drc"] == {"seconds": 6.0, "runs": 3}
    assert e["single"]["spice"] == {"seconds": 11.0, "runs": 2}
    assert e["multi"]["drc"] == {"seconds": 8.0, "runs": 1}


def test_no_history_gives_no_estimate(tmp_path):
    assert timings.estimates(tmp_path / "none.jsonl") == {}


def test_only_recent_runs_count(tmp_path):
    p = tmp_path / "t.jsonl"
    for _ in range(timings.KEEP):
        timings.record(p, "single", {"drc": 1.0})
    timings.record(p, "single", {"drc": 1.0})
    for _ in range(timings.KEEP):
        timings.record(p, "single", {"drc": 9.0})
    assert timings.estimates(p)["single"]["drc"]["seconds"] == 9.0


def test_spans_merge_stage_names_and_keep_first_to_last():
    s = timings.Spans()
    s.seen("rc", "r0", "x", 1.0)
    s.seen("rc_lvs", "r0", "y", 3.5)
    s.seen("drc", "r1", "z", 9.0)                # only the first build is a fair estimate
    assert s.seconds() == {"rc": 2.5}


def test_model_time_is_per_call():
    s = timings.Spans()
    s.seen("diagnostician", "", "model1", 10.0)
    s.seen("diagnostician", "", "model1", 12.0)
    s.seen("explainer", "", "model2", 20.0)
    s.seen("explainer", "", "model2", 33.0)
    assert s.seconds() == {"model": 2.0, "report": 13.0}
