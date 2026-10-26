"""results/m1/summary.md: every M1 requirement -> its evidence file -> status read from the record.

Also rewrites the block between the m1-summary markers in README.md, so headline numbers there
are copied from records, never typed.
"""
import csv
import json
from pathlib import Path

from . import interface, paths

START, END = "<!-- m1-summary:start -->", "<!-- m1-summary:end -->"


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def _rows(p: Path):
    try:
        return list(csv.DictReader(open(p)))
    except OSError:
        return []


def table1_status(rows) -> str:
    """pass only if every cell equals the handout to its printed precision."""
    from .mapping import matches_handout
    ok = [r for r in rows if matches_handout(float(r["usable_um2"]), float(r["handout_usable_um2"]))
          and matches_handout(float(r["reduced_um2"]), float(r["handout_reduced_um2"]))]
    if rows and len(ok) == len(rows):
        return "pass"
    dev = max((abs(float(r["reduced_vs_handout_pct"])) for r in rows), default=0.0)
    ver = rows[0]["yosys"].split(" (")[0] if rows else "?"
    return (f"NOT REPRODUCED: {len(ok)}/{len(rows)} rows match the handout "
            f"({ver} vs the handout's 0.33; max deviation {dev:.2f}%)")


def selftest_status(st: dict) -> str:
    if st.get("run", {}).get("status") != "pass":
        return "FAIL"
    if any(r["status"] == "definition-open" for r in st.get("table4", [])):
        return "pass on rows 1-5 and 7; row 6 open (Q-1)"
    return "pass"


def build(m1: Path) -> tuple:
    env = _load(m1 / "environment.json") or {}
    t1 = _rows(m1 / "table1.csv")
    base = [_load(p) for p in sorted((m1 / "baseline").glob("*/*/*/result.json"))]
    man = _load(m1 / "aigs" / "manifest.json") or {}
    cuts = _rows(m1 / "cuts" / "summary.csv")
    hd = _load(m1 / "hd_classes.json") or {}
    st = _load(m1 / "redundancy" / "self_test.json") or {}
    agent_checks = sorted((paths.ROOT / "ai" / "runs").glob("*.checks.json"))
    agent = _load(agent_checks[-1]) if agent_checks else {}
    req_ok = not interface.validate_request(_load(paths.ROOT / "docs/interface/request_example.json") or {}) \
        and not interface.validate_response(_load(paths.ROOT / "docs/interface/response_example.json") or {})

    def st_(ok):
        return "pass" if ok else "FAIL"

    yosys = (t1[0]["yosys"].split(" (")[0] if t1 else "?")
    cut_total = sum(int(r["cuts"]) for r in cuts)
    cut_fail = sum(int(r["failures"]) for r in cuts)
    rows = [
        ("Environment (make check)", "results/m1/environment.json", st_(env.get("status") == "pass")),
        (f"Table 1: {len(base)} mappings measured (research D-2)", "results/m1/table1.csv",
         table1_status(t1) if len(base) == 24 and all(b["run"]["status"] == "pass" for b in base)
         else "FAIL: mappings missing or failed"),
        (f"AIGs of every required design, synth and restructured: {len(man.get('artifacts', []))} artifacts",
         "results/m1/aigs/manifest.json", st_(man.get("status") == "pass" and len(man.get("artifacts", [])) == 12)),
        (f"Cut enumerator passing its check: {cut_total} cuts, {cut_fail} failures",
         "results/m1/cuts/summary.csv", st_(len(cuts) == 12 and cut_fail == 0
                                            and all(r["status"] == "pass" for r in cuts))),
        (f"Class table of HD: {hd.get('cells_total')} cells, {hd.get('pn_classes_total')} PN classes, "
         f"{hd.get('npn_classes_total')} NPN classes", "results/m1/hd_classes.csv",
         st_(hd.get("run", {}).get("status") == "pass")),
        (f"Redundancy self-test: {st.get('hd_cells_exists')}/{st.get('hd_cells_total')} HD cells Exists; "
         "Table 4 below", "results/m1/redundancy/self_test.json", selftest_status(st)),
        ("Agentic rows: tools wrapped, checks read-only, runs logged",
         paths.rel(agent_checks[-1]) if agent_checks else "ai/runs/", st_(agent.get("status") == "pass")),
        ("Option 3: request/response format fixed (Appendix A)", "docs/interface/", st_(req_ok)),
    ]
    lines = ["| cp1 requirement | Evidence | Status |", "|---|---|---|"]
    lines += [f"| {a} | `{b}` | {c} |" for a, b, c in rows]
    t4 = ["", "Table 4 self-test (4-input functions that depend on all inputs, up to input order):", "",
          "| Row | Handout | Measured | Status |", "|---|---:|---:|---|"]
    t4 += [f"| {r['row']} | {r['handout']} | {r['measured']} | {r['status']} |" for r in st.get("table4", [])]
    t1l = ["", f"Table 1 (um^2, {yosys}; the handout's Yosys 0.33 values for comparison):", "",
           "| Design | Script | Usable | Reduced | Reduced vs usable | Handout reduced | Ours vs handout |",
           "|---|---|---:|---:|---:|---:|---:|"]
    t1l += [f"| {r['design']} | {r['script']} | {float(r['usable_um2']):.1f} | {float(r['reduced_um2']):.1f} | "
            f"{r['reduced_vs_usable_pct']}% | {r['handout_reduced_um2']} | {r['reduced_vs_handout_pct']}% |"
            for r in t1]
    cl = ["", "Cuts per AIG:", "", "| Design | Variant | ANDs | Cuts | Failures | PN classes | NPN classes |",
          "|---|---|---:|---:|---:|---:|---:|"]
    cl += [f"| {r['design']} | {r['variant']} | {r['ands']} | {r['cuts']} | {r['failures']} | "
           f"{r['pn_classes']} | {r['npn_classes']} |" for r in cuts]
    body = "\n".join(lines + t4 + t1l + cl)
    # A row may honestly fail to reproduce the handout; the run itself fails only on FAIL.
    ok = not any(r[2].startswith("FAIL") for r in rows)
    return body, ok


def run(m1: Path) -> int:
    body, ok = build(Path(m1))
    head = ("# Milestone 1 evidence (generated by `make m1-summary`; do not edit)\n\n"
            "Every status below is read from the record named in the Evidence column.\n\n")
    (Path(m1) / "summary.md").write_text(head + body + "\n")
    readme = paths.ROOT / "README.md"
    if readme.exists():
        t = readme.read_text()
        if START in t and END in t:
            readme.write_text(t[:t.index(START) + len(START)] + "\n" + body + "\n" + t[t.index(END):])
    print(body.split("\n\n")[0])
    return 0 if ok else 1
