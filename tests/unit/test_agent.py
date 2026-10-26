"""cp1 agentic rows (overview Figure 2): tools wrapped, checks read-only, runs logged."""
import json
import sys

import pytest

from dd2.paths import ROOT

sys.path.insert(0, str(ROOT / "agent"))
from dd2_agent import audit, policy, tools  # noqa: E402


def test_every_tool_has_a_strict_schema():
    for name, t in tools.TOOLS.items():
        s = t.schema
        assert s["type"] == "object" and s["additionalProperties"] is False, name
        assert set(s["required"]) <= set(s["properties"]), name


@pytest.mark.parametrize("args, fragment", [
    ({"design": "cpu8", "extra": 1}, "unexpected"),
    ({"design": "nope"}, "not in"),
    ({}, "missing"),
    ({"design": 3}, "expected"),
])
def test_invalid_arguments_refused(args, fragment):
    errs = policy.validate_args(tools.TOOLS["run_baseline"].schema, args)
    assert errs and any(fragment in e for e in errs)


@pytest.mark.parametrize("target", ["tests/broken/x.json", "given/hd_reduced.lib", "pdk/x",
                                    "src/dd2/cutcheck.py", "results/m1/table1.csv",
                                    "runs/OTHER-RUN/x", "../outside", "/tmp/x"])
def test_writes_outside_the_run_are_refused(target):
    assert not policy.may_write(ROOT / target, "A-1026-99")


def test_writes_inside_the_run_allowed():
    assert policy.may_write(ROOT / "runs" / "A-1026-99" / "baseline" / "x.json", "A-1026-99")


def test_protected_digest_detects_change(tmp_path, monkeypatch):
    f = tmp_path / "check.py"
    f.write_text("a")
    monkeypatch.setattr(policy, "PROTECTED_TREES", [tmp_path])
    d = policy.protected_digest()
    f.write_text("b")
    assert policy.protected_digest() != d


def test_audit_lines_follow_appendix_b(tmp_path):
    log = audit.RunLog("A-1026-98", tmp_path)
    log.tool("fixed", "classify", {"tt": "0x077F", "arity": 4}, tmp_path / "r.json")
    log.policy("fixed", "write_file", {"path": "tests/broken/x"}, "refused: protected path")
    checks = tmp_path / "checks.json"
    checks.write_text("{}")
    log.result("pass", checks)
    lines = [json.loads(l) for l in (tmp_path / "A-1026-98.jsonl").read_text().splitlines()]
    assert [l["step"] for l in lines] == [1, 2, 3]
    assert {"run", "step", "agent", "kind", "tool", "args", "result"} <= set(lines[0])
    assert lines[-1]["kind"] == "result" and lines[-1]["status"] == "pass"
    assert audit.verify(tmp_path / "A-1026-98.jsonl") == []


def test_pass_without_check_file_is_a_failure(tmp_path):
    log = audit.RunLog("A-1026-97", tmp_path)
    log.result("pass", tmp_path / "missing.json")
    assert audit.verify(tmp_path / "A-1026-97.jsonl")
