"""Baseline mapping (Option 2 handout section 2) and Table 1.

The Yosys commands are exactly those of given/scripts/map.sh; we only add `tee` lines that write
the same `stat` to files, so the area is parsed from JSON rather than grepped (research D-3).
"""
import csv
import json
import re
from pathlib import Path

from . import designs, paths, provenance, tools

SCRIPTS = {
    "A": "+strash;dch,-f;amap;topo",
    "B": "+strash;&get,-n;&dch,-f;&nf,-R,1000;&put",
}
LIBRARIES = {"usable": "hd_usable.lib", "reduced": "hd_reduced.lib"}


def yosys_script(verilog, top, lib, script, sv=False, stat_txt="stat.txt", stat_json="stat.json"):
    sv_flag = "-sv" if sv else ""
    handout = (f"read_verilog {sv_flag} {verilog}; synth -flatten -top {top}; "
               f"dfflibmap -liberty {lib}; abc -liberty {lib} -script {SCRIPTS[script]}; "
               f"opt_clean -purge")
    return (f"{handout}; tee -q -o {stat_txt} stat -liberty {lib}; "
            f"tee -q -o {stat_json} stat -json -liberty {lib}")


HANDOUT_TOL_UM2 = 0.06   # the handout prints areas to 0.1 um^2; anything beyond rounding differs


def matches_handout(ours: float, handout: float | None, tol: float = HANDOUT_TOL_UM2) -> bool:
    return handout is not None and abs(ours - handout) <= tol


def parse_stat(stat: dict, top: str):
    mods = stat["modules"]
    m = mods.get("\\" + top) or mods.get(top)
    if m is None:
        raise ValueError(f"top {top!r} not in stat modules {list(mods)}")
    return float(m["area"]), int(m["num_cells"]), dict(m.get("num_cells_by_type", {}))


def run_mapping(design, library: str, script: str, out: Path, given: Path, src: Path | None = None) -> dict:
    d = Path(out) / design.name / library / script
    d.mkdir(parents=True, exist_ok=True)
    src = Path(src) if src else Path(given) / "designs" / f"{design.name}.v"
    lib = Path(given) / LIBRARIES[library]
    cmd = yosys_script(src, design.top, lib, script, design.sv, d / "stat.txt", d / "stat.json")
    argv = tools.yosys_cmd() + ["-q", "-p", cmd]
    rec = provenance.RunRecord(argv=[str(a) for a in argv], inputs=provenance.hash_inputs([src, lib]),
                               tools={"yosys": tools.version(tools.yosys_cmd() + ["-V"])})
    code, secs = tools.run(argv, d / "yosys.log")
    result = {"design": design.name, "top": design.top, "library": library, "script": script,
              "seconds": secs}
    try:
        area, cells, by_type = parse_stat(json.loads((d / "stat.json").read_text()), design.top)
        result.update(area_um2=area, cells=cells, cell_counts=by_type)
        rec.finish(code, logs=[d / "yosys.log", d / "stat.txt", d / "stat.json"])
    except (OSError, ValueError, KeyError) as e:
        result["error"] = f"could not parse stat: {e}"
        rec.finish(code or 1, logs=[d / "yosys.log"], status="fail")
    result["run"] = rec.asdict()
    provenance.write_json(d / "result.json", result)
    return result


def write_table1(results, path: Path, names) -> Path:
    got = {(r["design"], r["library"], r["script"]): r for r in results if r["run"]["status"] == "pass"}
    missing = [(n, l, s) for n in names for l in LIBRARIES for s in SCRIPTS if (n, l, s) not in got]
    if missing:
        raise ValueError(f"Table 1 incomplete, missing {missing}")
    path.parent.mkdir(parents=True, exist_ok=True)
    yosys = next(iter(got.values()))["run"]["tools"]["yosys"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["design", "script", "usable_um2", "reduced_um2", "reduced_vs_usable_pct",
                    "handout_usable_um2", "handout_reduced_um2", "reduced_vs_handout_pct",
                    "matches_handout", "yosys", "handout_yosys"])
        for n in names:
            ref = designs.HANDOUT_TABLE1.get(n, {})
            for s in SCRIPTS:
                u, r = got[(n, "usable", s)]["area_um2"], got[(n, "reduced", s)]["area_um2"]
                hu, hr = ref.get(("usable", s)), ref.get(("reduced", s))
                w.writerow([n, s, f"{u:.4f}", f"{r:.4f}", f"{100 * (r - u) / u:+.2f}",
                            hu, hr, f"{100 * (r - hr) / hr:+.2f}" if hr else "",
                            "yes" if matches_handout(u, hu) and matches_handout(r, hr) else "no",
                            yosys, designs.HANDOUT_YOSYS])
    return path


def run_all(given: Path, out: Path, names=None) -> int:
    names = names or [d.name for d in designs.required()]
    results = []
    for n in names:
        for lib in LIBRARIES:
            for s in SCRIPTS:
                r = run_mapping(designs.get(n), lib, s, Path(out) / "baseline", given)
                print(f"{n:10s} {lib:8s} {s}  {r.get('area_um2', 'FAIL')}  {r['run']['status']}")
                results.append(r)
    try:
        write_table1(results, Path(out) / "table1.csv", names)
    except ValueError as e:
        print(f"FAIL {e}")
        return 1
    print(f"wrote {paths.rel(Path(out) / 'table1.csv')}")
    return 0
