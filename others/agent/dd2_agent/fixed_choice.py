"""The fixed-choice version (overview 4.2): the same inputs, tools and checks as the agent, with the
choices the plan fixes: the first ordering, hd sizing, default routing, one build, no retry."""
import json
import sys
import time
from pathlib import Path

from dd2 import paths, provenance

from . import audit, tools
from .graph import facts

SETTINGS = {"sizing": "hd", "order_index": 0}


def run(expr: str, name: str, run_id: str | None = None, log_dir=audit.LOG_DIR) -> dict:
    run_id = run_id or audit.new_run_id(log_dir)
    log = audit.RunLog(run_id, log_dir)
    t0 = time.time()
    code, out = tools.call("build_cell", {"expr": expr, "name": name} | SETTINGS, run_id, log, "fixed")
    report = json.loads(Path(out).read_text()) if out and Path(out).exists() else {}
    rev = facts(report, SETTINGS) | {"report": paths.rel(Path(out)) if out else None, "exit_code": code}
    chk = log.path.with_suffix(".checks.json")
    summary = {"run": run_id, "function": expr, "model": "none (fixed choices)", "seconds": round(time.time() - t0, 1),
               "calls": {"model": 0, "tool": 1}, "revisions": [rev], "best": rev, "status": rev["status"]}
    provenance.write_json(chk, summary)
    log.result(rev["status"], chk)
    summary["log_problems"] = audit.verify(log.path)
    return summary


if __name__ == "__main__":
    s = run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "fixed_cell")
    print(json.dumps({k: s[k] for k in ("run", "status", "seconds")} | {"best": s["best"]}))
    sys.exit(0 if s["status"] == "pass" else 1)
