"""What the agent adds over fixed choices (overview 4.2): the same functions, tools and checks, each
function through the fixed-choice version and through the agent, with the cost, the time and the
result of each run -> results/option1/m2/agent_vs_fixed.csv. --runs 3 repeats the agent, as the
overview asks for the functions given at the demo."""
import argparse
import csv
import sys
from concurrent.futures import ProcessPoolExecutor

from cellgen.m2 import TEST_CELLS
from dd2 import paths, provenance

from . import audit, fixed_choice, graph, model

OUT = paths.results("option1", "m2")


def row(short, mode, i, s) -> dict:
    b = s["best"] or {}
    return {"function": short, "mode": mode, "run": i, "run_id": s["run"], "status": s["status"], "stop": s.get("stop", ""),
            "sites": b.get("sites"), "met1_nets": len(b.get("met1_nets") or []), "breaks": b.get("breaks"),
            "builds": len(s["revisions"]), "model_calls": s["calls"]["model"], "tokens_in": s["calls"].get("in", 0),
            "tokens_out": s["calls"].get("out", 0), "seconds": s["seconds"],
            "model": s["model"] if s["calls"]["model"] else "no model call",
            "failure": "" if s["status"] == "pass" else ", ".join(b.get("failed") or [s.get("stop") or "no revision"]),
            "log_ok": not s["log_problems"]}


def job(j) -> dict:
    short, expr, mode, i, run_id = j
    if mode == "fixed":
        return row(short, mode, i, fixed_choice.run(expr, f"f_{short}", run_id=run_id))
    return row(short, mode, i, graph.run(expr, f"a_{short}", run_id=run_id))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dd2_agent.compare")
    ap.add_argument("cells", nargs="*", help="short names from TEST_CELLS (default: all)")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args(argv)
    cfg = model.load_config()
    if not model.available(cfg["model"]):
        print(f"model {model.label(cfg['model'])} is not available: install Codex CLI and sign in", file=sys.stderr)
        return 2
    jobs = []
    for short, expr, _ in (t for t in TEST_CELLS if not a.cells or t[0] in a.cells):
        for mode, i in [("fixed", 1)] + [("agent", k) for k in range(1, a.runs + 1)]:
            run_id = audit.new_run_id()              # reserved here: parallel runs must not share an ID
            (audit.LOG_DIR / f"{run_id}.jsonl").touch()
            jobs.append((short, expr, mode, i, run_id))
    rows = []
    with ProcessPoolExecutor(a.jobs) as pool:
        for r in pool.map(job, jobs):
            rows.append(r)
            write(rows)
    return 0


def write(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "agent_vs_fixed.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    provenance.write_json(OUT / "agent_vs_fixed.json", {"written": provenance.now(), "rows": len(rows)})


if __name__ == "__main__":
    sys.exit(main())
