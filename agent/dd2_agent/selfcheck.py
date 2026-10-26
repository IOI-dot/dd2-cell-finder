"""make agent-check: the cp1 agentic rows without a model (overview Figure 2, week 1).

A scripted fixed-choice run calls the wrapped tools on cpu8, then tries three things the policy
must refuse. It writes ai/runs/<run>.jsonl and ai/runs/<run>.checks.json; the verdict comes from
these checks, never from a model.
"""
import csv
import json
import sys

from dd2 import paths, provenance

from . import audit, policy, tools


def main() -> int:
    run_id = audit.new_run_id()
    log = audit.RunLog(run_id)
    digest = policy.protected_digest()
    calls = [("run_baseline", {"design": "cpu8"}), ("extract_aig", {"design": "cpu8"}),
             ("enumerate_cuts", {"design": "cpu8"}), ("classify", {"tt": "0x077F", "arity": 4}),
             ("build_reference_cell", {"cell": "inv_1"})]
    results = {}
    for name, args in calls:
        code, out = tools.call(name, args, run_id, log)
        results[name] = {"exit_code": code, "result": paths.rel(out) if out else None}
    refusals = [("run_baseline", {"design": "cpu8", "out": "tests/broken"}),   # extra field
                ("classify", {"tt": "0x1", "arity": 5}),                       # outside the enum
                ("delete_file", {"path": "tests/broken/SHA256SUMS"})]          # unknown tool
    refused = [tools.call(n, a, run_id, log) == (None, None) for n, a in refusals]
    write_guard = not policy.may_write(paths.ROOT / "tests" / "broken" / "x", run_id)
    log.policy("fixed", "write_file", {"path": "tests/broken/x"},
               "refused: write outside runs/<run_id>/" if write_guard else "ALLOWED (bug)")

    cut_rows = list(csv.DictReader(open(policy.run_dir(run_id) / "cuts" / "summary.csv")))
    classified = json.loads((policy.run_dir(run_id) / "classify_0x077F_4.json").read_text())
    cell_report = policy.run_dir(run_id) / "cells" / "dd2_ref__inv_1" / "report.json"
    cell_ok = cell_report.exists() and json.loads(cell_report.read_text())["status"] == "pass"
    checks = {
        "tools_exit_zero": all(r["exit_code"] == 0 for r in results.values()),
        "cut_failures_zero": all(r["failures"] == "0" for r in cut_rows) and len(cut_rows) == 2,
        "maj4n_is_new": classified["class"] == "New",
        "option1_cell_passes_every_check": cell_ok,
        "invalid_calls_refused": all(refused),
        "protected_write_refused": write_guard,
        "protected_files_unchanged": policy.protected_digest() == digest,
    }
    status = "pass" if all(checks.values()) else "fail"
    chk = paths.ROOT / "ai" / "runs" / f"{run_id}.checks.json"
    provenance.write_json(chk, {"run": run_id, "checks": checks, "tool_results": results,
                                "status": status, "written": provenance.now()})
    log.result(status, chk)
    errs = audit.verify(log.path)
    for k, v in checks.items():
        print(f"{'ok  ' if v else 'FAIL'} {k}")
    print(f"{run_id}: {status}; log {paths.rel(log.path)}" + (f"; log problems {errs}" if errs else ""))
    return 0 if status == "pass" and not errs else 1


if __name__ == "__main__":
    sys.exit(main())
