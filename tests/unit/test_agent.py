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


@pytest.mark.parametrize("bad_id", ["../tests/broken", "A-1026-01/../../src", "", "x", "A-1026-1"])
def test_malformed_run_ids_cannot_write(bad_id):
    # verifier finding 5: may_write(runs/../tests/broken/..., "../tests/broken") used to pass
    assert not policy.may_write(ROOT / "runs" / bad_id / "x.json", bad_id)


def test_protected_set_covers_pdk_tests_and_agent():
    roots = {str(p) for p in policy.PROTECTED_TREES}
    for must in ("tests", "agent", "pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"):
        assert str(ROOT / must) in roots, must


def test_every_tool_writes_only_inside_its_run(tmp_path):
    for name, t in tools.TOOLS.items():
        args = {"design": "cpu8"} if "design" in t.schema["properties"] else \
               {"tt": "0x7", "arity": 2} if name == "classify" else {}
        argv = [str(a) for a in t.argv(args, ROOT / "runs" / "A-1026-99")]
        paths_in_argv = [a for a in argv if a.startswith(str(ROOT))]
        assert all(policy.may_write(a, "A-1026-99") for a in paths_in_argv), (name, argv)
    # extract_aig must get a run-local scratch directory, not build/
    argv = tools.TOOLS["extract_aig"].argv({"design": "cpu8"}, ROOT / "runs" / "A-1026-99")
    assert "--scratch" in [str(a) for a in argv]
