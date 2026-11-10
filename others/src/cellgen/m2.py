"""Option 1 Milestone 2 evidence (handout Table 7, M2): the reference cells against Table 4, the
characterizer against Table 5, every test cell of Table 6, and the two sizings. Writes
results/option1/m2/ and the cells/ views. `python -m cellgen.m2 refs|tests|table5|summary`."""
import csv
import itertools
import re
import shutil
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from dd2 import boolfn as bf
from dd2 import paths, provenance

from . import characterize as ch
from . import eda, flow, simulate, sta, stress
from .m1 import inputs_of

OUT = paths.results("option1", "m2")
REFS = flow.SIX + flow.MULTI_STAGE
# handout Table 6, and "one function of your choice": xor3, the hardest for the decomposition
TEST_CELLS = [("nand2", "!(A & B)", "nand2_1"), ("nor2", "!(A | B)", "nor2_1"), ("nand3", "!(A & B & C)", "nand3_1"),
              ("nor3", "!(A | B | C)", "nor3_1"), ("a21oi", "!((A & B) | C)", "a21oi_1"), ("o21ai", "!((A | B) & C)", "o21ai_1"),
              ("a22oi", "!((A & B) | (C & D))", "a22oi_1"), ("o22ai", "!((A | B) & (C | D))", "o22ai_1"),
              ("and2", "A & B", "and2_1"), ("a21o", "(A & B) | C", "a21o_1"), ("mux2", "(A & !C) | (B & C)", "mux2_1"),
              ("maj3", "(A & B) | (C & (A | B))", "maj3_1"), ("xor2", "A ^ B", "xor2_1"),
              ("nest1", "!(A & (B | (C & D)))", None), ("nest2", "!(A | (B & (C | D)))", None),
              ("maj4n", "!((C&D) | (A&B&(C|D)))", None), ("maj4", "(C&D) | (A&B&(C|D))", None),
              ("xor3", "A ^ B ^ C", "xor3_1")]


def ref_job(c):
    return flow.build_reference(c)


def test_job(t, sizing="hd", suffix=""):
    short, expr, hd = t
    ins = inputs_of(expr)
    tt = bf.eval_expr(expr, ins)
    name = f"dd2_t_{short}{suffix}"
    try:
        rep = flow.build(name, ins, tt, sizing=sizing)
    except Exception as e:                 # a cell that cannot be built is a failed row, not a crash
        return {"cell": name, "status": "fail", "failed_checks": ["build"], "error": str(e), "expression": expr}
    rep |= {"expression": expr, "hd_cell": hd, "short": short}
    rep["hd_comparison"] = hd_comparison(name, ins, tt, hd) if hd and rep["status"] == "pass" else None
    return rep


def worst_arcs(rows, rename=None) -> dict:
    """Worst delay and slew per input pin and input edge, over the side inputs."""
    out = {}
    for r in rows:
        if "error" in r:
            continue
        p = (rename or {}).get(r["pin"], r["pin"])
        d = out.setdefault(p, {})
        for edge in ("rise", "fall"):
            d[f"delay_in_{edge}_ns"] = max(d.get(f"delay_in_{edge}_ns", 0), r[f"delay_in_{edge}_ns"])
            d[f"slew_in_{edge}_ns"] = max(d.get(f"slew_in_{edge}_ns", 0), r[f"transition_in_{edge}_ns"])
    return out


def hd_comparison(name, ins, tt, hd) -> dict:
    """Handout section 6: width, area, delay and slew at the HD point nearest 100 ps and 10 fF.
    Our test inputs A, B, C map onto HD's pin names by the permutation that gives the same function."""
    ref = flow.reference(hd)
    rename = None
    for perm in itertools.permutations(ref["inputs"]):
        if bf.eval_expr(_tt_expr(tt, perm), ref["inputs"]) == ref["tt"]:
            rename = dict(zip(ref["inputs"], ins)) | {p: i for p, i in zip(perm, ins)}
            break
    if rename is None:
        return {"error": f"no pin permutation maps the function onto {hd}"}
    work = paths.build("cells") / name / "hd"
    work.mkdir(parents=True, exist_ok=True)
    full = flow.HD + hd
    eda.magic(work, eda.extract_script(eda.HD_GDS, full, rc=True), "extract")
    stress.annotate(work / f"{full}_rc.spice", work / "installed.spice", flow.hd_gds(), full)
    out = flow.installed_output(hd)
    point = simulate.hd_table_point(hd_cell=hd)
    theirs = worst_arcs(simulate.delays(work, full, work / "installed.spice", ref["inputs"], ref["tt"], point, out), rename)
    tdir = paths.build("cells") / name
    ours = worst_arcs(simulate.delays(tdir, name, tdir / f"{name}_rc_sasb.spice", ins, tt, point))
    rep = provenance_load(name)
    sites_hd = round(flow.compare.Gds(flow.hd_gds(), full).width() / 0.46)
    return {"hd_cell": full, "width_sites": {"ours": rep["layout"]["width_sites"], "hd": sites_hd},
            "area_um2": {"ours": round(rep["layout"]["width_um"] * 2.72, 4), "hd": round(sites_hd * 0.46 * 2.72, 4)},
            "point": point, "ours": ours, "hd": theirs}


def provenance_load(name):
    import json
    return json.loads((paths.ROOT / "cells" / name / "report.json").read_text())


def _tt_expr(tt, names) -> str:
    return ch.function_text(tt, list(names))


def refs() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(4) as pool:
        reports = dict(zip(REFS, pool.map(ref_job, REFS)))
    rows = []
    for c, r in reports.items():
        provenance.write_json(OUT / "references" / f"{c}.json", r)
        k, cmp = r["checks"], r["comparison"]
        order = cmp["gate_order"]
        rows.append({"cell": c, "status": r["status"], "failed": " ".join(r["failed_checks"]),
                     "frame": cmp["frame"]["verdict"], "transistors_lvs": cmp["transistors"]["lvs_with_wl"],
                     "transistors_ours": cmp["transistors"]["count_ours"], "transistors_installed": cmp["transistors"]["count_installed"],
                     "pins": "pass" if not cmp["pins"]["ours_errors"] else "fail",
                     "wiring": "pass" if cmp["wiring_layers"]["ours"]["ok"] else "fail",
                     "met1_outside_rails_um2": cmp["wiring_layers"]["ours"]["met1_outside_rails_um2"],
                     "abutment_errors": cmp["abutment"]["errors"], "sites_ours": cmp["width_sites"]["ours"],
                     "sites_installed": cmp["width_sites"]["installed"], "gates_ours": " ".join(order["ours"]["gates"]),
                     "gates_installed": " ".join(order["installed"]["gates"]),
                     "pitch_ours": " ".join(map(str, order["ours"]["pitch_um"])),
                     "pitch_installed": " ".join(map(str, order["installed"]["pitch_um"])),
                     "breaks_ours": sum(order["ours"]["diffusion_breaks"].values()),
                     "breaks_installed": sum(order["installed"]["diffusion_breaks"].values()),
                     "drc": k["drc"]["errors"], "lvs": k["lvs"]["result"], "rc_lvs": k["rc_lvs"]["result"],
                     "spice": k["spice"]["status"], "model": k["model"]["status"]}
                    | _par(cmp["parasitics"], "ours") | _par(cmp["parasitics"], "installed"))
        shutil.copy(paths.ROOT / "cells" / r["cell"] / "comparison.svg", OUT / "references" / f"{c}.svg")
    _csv(OUT / "table4.csv", rows)
    return 0 if all(r["status"] == "pass" for r in reports.values()) else 1


def _par(p, who) -> dict:
    caps = p[who]["c_fF_per_net"]
    return {f"c_total_fF_{who}": round(sum(caps.values()) / 2, 3), f"r_total_ohm_{who}": p[who]["r_ohm_total"]}


def _csv(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def tests(only=()) -> int:
    """only: rebuild just these short names; the others keep their saved reports."""
    import json
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(t, "hd", "") for t in TEST_CELLS] + [(("nor3", "!(A | B | C)", "nor3_1"), "stack", "_stack")]
    todo = [j for j in jobs if not only or j[0][0] + j[2] in only]
    with ProcessPoolExecutor(4) as pool:
        fresh = {r["cell"]: r for r in pool.map(lambda_job, todo)}
    reports = []
    for t, _, suffix in jobs:
        name = f"dd2_t_{t[0]}{suffix}"
        saved = OUT / "test_cells" / f"{name}.json"
        reports.append(fresh[name] if name in fresh else json.loads(saved.read_text()))
    rows, cmp_rows = [], []
    for r in reports:
        provenance.write_json(OUT / "test_cells" / f"{r['cell']}.json", r)
        if "layout" not in r:
            rows.append({"cell": r["cell"], "expression": r["expression"], "status": "fail", "failed": r.get("error", "")})
            continue
        k = r["checks"]
        rows.append({"cell": r["cell"], "expression": r["expression"], "status": r["status"], "failed": " ".join(r["failed_checks"]),
                     "stages": k["network"]["stages"], "transistors": k["network"]["transistors"],
                     "max_series": k["network"]["max_series"], "sites": r["layout"]["width_sites"],
                     "breaks_n": r["layout"]["row_breaks"]["n"], "breaks_p": r["layout"]["row_breaks"]["p"],
                     "met1_nets": " ".join(r["layout"].get("met1_nets") or []), "drc": k["drc"]["errors"],
                     "abutment": k["abutment"]["errors"], "lvs": k["lvs"]["result"], "rc_lvs": k["rc_lvs"]["result"],
                     "layers": k["layers"]["status"], "spice": k["spice"]["status"], "model": k["model"]["status"],
                     "sizing": r["sizing"]["policy"]})
        h = r.get("hd_comparison")
        if h and "error" not in h:
            for pin, ours in h["ours"].items():
                cmp_rows.append({"cell": r["cell"], "hd_cell": h["hd_cell"], "sites_ours": h["width_sites"]["ours"],
                                 "sites_hd": h["width_sites"]["hd"], "area_ours_um2": h["area_um2"]["ours"],
                                 "area_hd_um2": h["area_um2"]["hd"], "pin": pin}
                                | {f"{k_}_ours": v for k_, v in ours.items()}
                                | {f"{k_}_hd": v for k_, v in h["hd"].get(pin, {}).items()})
    _csv(OUT / "test_cells.csv", [dict(zip(_keys(rows), (x.get(k_, "") for k_ in _keys(rows)))) for x in rows])
    if cmp_rows:
        _csv(OUT / "test_vs_hd.csv", cmp_rows)
    sizing(reports)
    return 0 if all(r["status"] == "pass" for r in reports) else 1


def _keys(rows):
    return list(dict.fromkeys(k for r in rows for k in r))


def lambda_job(j):
    return test_job(*j)


def sizing(reports):
    """Handout 8.2: the two sizings of !(A | B | C): width and delay per input pin."""
    by = {r["cell"]: r for r in reports}
    rows = []
    for name, policy in (("dd2_t_nor3", "hd"), ("dd2_t_nor3_stack", "stack")):
        r = by[name]
        if "layout" not in r:
            continue
        w = paths.build("cells") / name
        per = worst_arcs(simulate.delays(w, name, w / f"{name}_rc_sasb.spice", list("ABC"), r_tt()))
        for pin, d in per.items():
            rows.append({"sizing": policy, "cell": name, "sites": r["layout"]["width_sites"], "status": r["status"],
                         "pin": pin} | d)
    if rows:
        _csv(OUT / "sizing_nor3.csv", rows)


def r_tt():
    return bf.eval_expr("!(A | B | C)", list("ABC"))


def validate_cell(c, engine, broken=False) -> dict:
    full = flow.HD + c
    tag = f"{engine}{'_broken' if broken else ''}"
    w = paths.build("val") / c / tag
    if w.exists():
        shutil.rmtree(w)
    w.mkdir(parents=True)
    eda.magic(w, eda.extract_script(eda.HD_GDS, full, rc=True), "extract")
    stress.annotate(w / f"{full}_rc.spice", w / "installed.spice", flow.hd_gds(), full)
    ref = flow.reference(c)
    hd = ch.read_cell(c)
    spec = {"index_1": hd["tables"][0]["index_1"], "index_2": hd["tables"][0]["index_2"]}
    r = ch.characterize(full, w / "installed.spice", ref["inputs"], hd["output"], ref["tt"], spec, ch.Engine(engine), w / "sim",
                        broken_full_ramp=broken)
    return {"cell": c, "engine": engine, "broken": broken, "result": r, "hd": hd, "ref": ref}


def setup_check() -> dict:
    """Table 5, Setup: the written Liberty files against the shipped one, value by value."""
    head = ("nom_voltage", "nom_temperature", "slew_lower_threshold_pct_rise", "slew_upper_threshold_pct_rise",
            "slew_lower_threshold_pct_fall", "slew_upper_threshold_pct_fall", "input_threshold_pct_rise",
            "output_threshold_pct_rise", "slew_derate_from_library")
    shipped = ch._lib()
    shipped = shipped[:shipped.index("cell (")]
    diffs = []
    for c in flow.SIX:
        text = (OUT / "libs" / f"{c}_fixed.lib").read_text()
        for key in head:
            if ch._attr(text, key) != ch._attr(shipped, key):
                diffs.append(f"{c}: {key}")
        hd = ch.read_cell(c)["tables"]
        body = text[text.index("cell ("):]                  # not the template, whose index is 1, 2, 3...
        ours = [{"index_1": ch._numbers(a), "index_2": ch._numbers(b)} for a, b in
                re.findall(r'index_1\("([^"]+)"\);\s*index_2\("([^"]+)"\)', body)]
        if len(ours) != len(hd):
            diffs.append(f"{c}: {len(ours)} tables, shipped {len(hd)}")
        if any(abs(x - y) > 1e-9 for o in ours for k in ("index_1", "index_2") for x, y in zip(o[k], hd[0][k])):
            diffs.append(f"{c}: index values differ")
    return {"status": "pass" if not diffs else "fail", "compared": list(head) + ["index_1", "index_2"], "differences": diffs}


def design_level(group: dict, tmpl: str) -> dict:
    """Table 5: the six cells replaced in a copy of the HD Liberty, SPM mapped again and timed."""
    base = paths.given() / "hd_usable.lib"
    swapped = paths.build("val") / "hd_with_six.lib"
    swapped.write_text(sta.swap_cells(base.read_text(), group, tmpl))
    spm = paths.ROOT / "data" / "designs" / "spm.v"
    res = {"library": "given/hd_usable.lib", "design": "data/designs/spm.v", "scripts": {}}
    for script in ("A", "B"):
        a = sta.time_design(base, spm, "spm", paths.build("val") / f"spm_hd_{script}", script)
        b = sta.time_design(swapped, spm, "spm", paths.build("val") / f"spm_six_{script}", script)
        change = round(b["worst_delay_ns"] - a["worst_delay_ns"], 4) if a["status"] == b["status"] == "pass" else None
        res["scripts"][script] = {"shipped": a, "with_six": b, "worst_delay_change_ns": change,
                                  "worst_delay_change_pct": round(change / a["worst_delay_ns"] * 100, 3) if change is not None else None}
    return res


def table5() -> int:
    setup = ch.read_setup()
    sims = {e: ch.Engine(e).identity(paths.build("val")) for e in ("fixed", "stock")}
    out = {"setup": setup, "simulators": sims, "cells": {}, "builds": {}}
    all_err = {}
    caps_ok = True
    libs = OUT / "libs"
    libs.mkdir(parents=True, exist_ok=True)
    group, tmpl = {}, ""
    for engine in ("fixed", "stock"):
        errs = []
        for c in flow.SIX:
            v = validate_cell(c, engine)
            cmp = ch.compare_tables(v["result"]["tables"], v["hd"]["tables"])
            delay = ch.compare_tables([t for t in v["result"]["tables"] if t["table"].startswith("cell_")],
                                      [t for t in v["hd"]["tables"] if t["table"].startswith("cell_")])
            trans = ch.compare_tables([t for t in v["result"]["tables"] if "transition" in t["table"]],
                                      [t for t in v["hd"]["tables"] if "transition" in t["table"]])
            caps = {p: {"ours": round(x.get("mean", 0), 7), "shipped": v["hd"]["capacitance"][p],
                        "error_pct": round(abs(x.get("mean", 0) - v["hd"]["capacitance"][p]) / v["hd"]["capacitance"][p] * 100, 3)}
                    for p, x in v["result"]["capacitance"].items()}
            if engine == "fixed":
                caps_ok = caps_ok and all(x["error_pct"] <= 10 for x in caps.values())
            sides = {f"{t['pin']} {t['table']}": t["sides_tried"] for t in v["result"]["tables"] if t["sides_tried"]}
            out["cells"].setdefault(c, {})[engine] = {
                "entries": cmp["entries"], "median_abs_pct": cmp["median_abs_pct"], "max_abs_pct": cmp["max_abs_pct"],
                "worst": cmp["worst"], "delay_median_abs_pct": delay["median_abs_pct"],
                "transition_median_abs_pct": trans["median_abs_pct"], "input_capacitance": caps, "slowest_side_search": sides}
            errs += cmp["errors_pct"]
            text = ch.liberty_text(flow.HD + c, v["ref"]["inputs"], v["hd"]["output"], v["ref"]["tt"], v["hd"]["area"],
                                   v["result"]["capacitance"], v["result"]["tables"], setup, sims[engine])
            (libs / f"{c}_{engine}.lib").write_text(text)
            if engine == "fixed":
                out["cells"][c]["liberty_load"] = sta.load_liberty(libs / f"{c}_{engine}.lib", paths.build("val") / "load")
                group[flow.HD + c] = ch.cell_group(flow.HD + c, v["ref"]["inputs"], v["hd"]["output"], v["ref"]["tt"],
                                                   v["hd"]["area"], v["result"]["capacitance"], v["result"]["tables"])
                tmpl = ch.template(v["result"]["tables"])
        all_err[engine] = errs
        worst = max(out["cells"].values(), key=lambda d: d[engine]["max_abs_pct"])[engine]
        out["builds"][engine] = {"entries": len(errs), "median_abs_pct": round(statistics.median(errs), 3),
                                 "max_abs_pct": round(max(errs), 3), "worst": worst["worst"]}
        provenance.write_json(OUT / "table5.json", out)
    out["design_level"] = design_level(group, tmpl)
    provenance.write_json(OUT / "table5.json", out)
    # the broken case of Table 5: index the tables by the full ramp
    broken = {}
    for c in ("inv_1", "nand2_1"):
        v = validate_cell(c, "fixed", broken=True)
        d = ch.compare_tables([t for t in v["result"]["tables"] if t["table"].startswith("cell_")],
                              [t for t in v["hd"]["tables"] if t["table"].startswith("cell_")])
        broken[c] = {"delay_median_abs_pct": d["median_abs_pct"], "good_delay_median_abs_pct": out["cells"][c]["fixed"]["delay_median_abs_pct"]}
    out["broken_full_ramp"] = {"cells": broken, "rule": "the delay median must get worse than with the 20-80% slew and pass 5%",
                               "flagged": all(b["delay_median_abs_pct"] > 5 and b["delay_median_abs_pct"] > b["good_delay_median_abs_pct"]
                                              for b in broken.values())}
    load = [c["liberty_load"] for c in out["cells"].values()]
    out["setup_check"] = setup_check()
    per_cell = [v["fixed"]["median_abs_pct"] for v in out["cells"].values()]
    out["requirements"] = {"setup": out["setup_check"]["status"], "median_le_5pct": out["builds"]["fixed"]["median_abs_pct"] <= 5,
                           "every_cell_median_le_5pct": max(per_cell) <= 5, "input_cap_within_10pct": caps_ok,
                           "liberty_loads": all(x["yosys"] == x["opensta"] == "pass" for x in load),
                           "design_level_reported": all(s["worst_delay_change_ns"] is not None for s in out["design_level"]["scripts"].values()),
                           "broken_flagged": out["broken_full_ramp"]["flagged"]}
    provenance.write_json(OUT / "table5.json", out)
    return 0 if all(v in (True, "pass") for v in out["requirements"].values()) else 1


def _spec(hd_cell):
    t = ch.read_cell(hd_cell)["tables"][0]
    return {"index_1": t["index_1"], "index_2": t["index_2"]}


def _timing_job(c):
    """Table 4, Timing: both cells through one flow, at the index values of the shipped tables."""
    ref = flow.reference(c)
    y = flow.installed_output(c)
    name = f"dd2_ref__{c}"
    work = paths.build("cells") / name
    theirs = validate_cell(c, "fixed")["result"]
    ours = ch.characterize(name, work / f"{name}_rc_sasb.spice", ref["inputs"], y, ref["tt"], _spec(c), ch.Engine("fixed"),
                           work / "char", jobs=3)
    shipped = ch.read_cell(c)["tables"]
    a = ch.compare_tables(ours["tables"], theirs["tables"])
    b = ch.compare_tables(ours["tables"], shipped)
    return {"cell": c, "median_vs_installed_pct": a["median_abs_pct"], "max_vs_installed_pct": a["max_abs_pct"],
            "median_vs_shipped_pct": b["median_abs_pct"], "max_vs_shipped_pct": b["max_abs_pct"], "entries": a["entries"]}


def timing() -> int:
    """Characterize no generated cell until all six meet Table 5 (handout 5.1)."""
    import json
    t5 = json.loads((OUT / "table5.json").read_text())
    if not all(v in (True, "pass") for v in t5["requirements"].values()):
        print("Table 5 is not met: no generated cell may be characterized")
        return 1
    with ProcessPoolExecutor(2) as pool:
        rows = list(pool.map(_timing_job, REFS))
    _csv(OUT / "table4_timing.csv", rows)
    return 0


# Handout Table 4: "report, and explain any extra site" and "explain each difference".
WHY = {"nor2_1": "Same width. Our order is the first the search found; the installed cell mirrors it.",
       "o21ai_1": "HD jogs its stripes and widens npc locally to lift B1's contact above the band. We keep straight "
                  "stripes and the frame's npc band, so all three pads share one row, which costs the extra site.",
       "a21o_1": "The a21oi stage's PMOS row cannot end on VPWR, so both cells have a break before the inverter. HD packs "
                 "its pads tighter with jogged stripes; our straight stripes cost the extra site.",
       "mux2_1": "Three stages side by side with two PMOS breaks. HD folds the two transmission paths into one row with "
                 "0.42 um devices and no break; the hd policy gives every finger 0.65 and 1.00 um, so timing differs too.",
       "nand3_1": "Same order and width; the two pitches are in the other order, because our splay is on the other side.",
       "a21oi_1": "Same width; the order is mirrored, and our pitches come from the pad rule, HD's from jogged stripes."}


def table4_notes(ref):
    rows = ["# Table 4: differences from the installed cells (generated by `make o1-m2`)", "",
            "| Cell | Sites (ours, HD) | Gate order (ours / HD) | Pitch (ours / HD) | Breaks (ours, HD) | Why |", "|---|---|---|---|---|---|"]
    for r in ref:
        rows.append(f"| {r['cell']} | {r['sites_ours']}, {r['sites_installed']} | {r['gates_ours']} / {r['gates_installed']} | "
                    f"{r['pitch_ours']} / {r['pitch_installed']} | {r['breaks_ours']}, {r['breaks_installed']} | {WHY.get(r['cell'], 'No difference.')} |")
    (OUT / "table4_notes.md").write_text("\n".join(rows) + "\n")


def summary() -> int:
    """results/option1/m2/summary.md and the README block, from the saved results only."""
    import json
    ref = list(csv.DictReader(open(OUT / "table4.csv")))
    table4_notes(ref)
    cells = list(csv.DictReader(open(OUT / "test_cells.csv")))
    t5 = json.loads((OUT / "table5.json").read_text())
    t5["setup_check"] = setup_check()
    t5["requirements"]["setup"] = t5["setup_check"]["status"]
    provenance.write_json(OUT / "table5.json", t5)
    six = [r for r in ref if r["cell"] in flow.SIX]
    multi = [r for r in ref if r["cell"] in flow.MULTI_STAGE]
    good = sum(r["status"] == "pass" for r in cells)
    fixed, stock = t5["builds"]["fixed"], t5["builds"]["stock"]
    req = t5["requirements"]
    ok_ref = all(r["status"] == "pass" for r in ref)
    ok_t5 = all(v in (True, "pass") for v in req.values())
    ok_cells = good == len(cells)
    d = t5.get("design_level", {}).get("scripts", {})
    lines = ["# Option 1 Milestone 2 evidence (generated by `make o1-m2`; do not edit)", "",
             "| cp2 requirement | Evidence | Status |", "|---|---|---|",
             f"| Six reference cells pass every Table 4 must-match row ({sum(r['status'] == 'pass' for r in six)} of {len(six)}) "
             f"| `results/option1/m2/table4.csv`, `results/option1/m2/references/` | {'pass' if all(r['status'] == 'pass' for r in six) else 'FAIL'} |",
             f"| a21o_1 and mux2_1 built and compared: "
             + "; ".join(f"{r['cell']} {r['transistors_ours']} T vs {r['transistors_installed']} T, {r['sites_ours']} vs {r['sites_installed']} sites, "
                         f"LVS vs installed {r['transistors_lvs']} (reported)" for r in multi)
             + f" | `results/option1/m2/references/` | {'pass' if all(r['status'] == 'pass' for r in multi) else 'FAIL'} |",
             f"| Characterizer against the shipped Liberty: {fixed['entries']} entries of the six cells, median {fixed['median_abs_pct']}%, "
             f"max {fixed['max_abs_pct']}% with the fixed ngspice; median {stock['median_abs_pct']}%, max {stock['max_abs_pct']}% with stock "
             f"| `results/option1/m2/table5.json` | {'pass' if ok_t5 else 'FAIL'} |",
             "| Median per cell, fixed ngspice: " + ", ".join(f"{c} {v['fixed']['median_abs_pct']}%" for c, v in t5["cells"].items())
             + f" | `results/option1/m2/table5.json` | {'pass' if req['every_cell_median_le_5pct'] else 'FAIL'} |",
             f"| Input capacitance within 10%, Liberty loads in Yosys and OpenSTA, full-ramp broken case flagged "
             f"| `results/option1/m2/table5.json` | {'pass' if req['input_cap_within_10pct'] and req['liberty_loads'] and req['broken_flagged'] else 'FAIL'} |",
             "| SPM with the six cells swapped in, worst delay change: "
             + ", ".join(f"script {k} {v['worst_delay_change_ns']} ns ({v['worst_delay_change_pct']}%)" for k, v in d.items())
             + " | `results/option1/m2/table5.json` | " + ("pass" if req["design_level_reported"] else "FAIL") + " |",
             f"| Test cells generated, verified and simulated ({good} of {len(cells)}, the extra one being the stack nor3) "
             f"| `results/option1/m2/test_cells.csv`, `cells/` | {'pass' if ok_cells else 'FAIL'} |"]
    if (OUT / "agent_vs_fixed.csv").exists():
        rows = list(csv.DictReader(open(OUT / "agent_vs_fixed.csv")))
        ag = [r for r in rows if r["mode"] == "agent"]
        fx = [r for r in rows if r["mode"] == "fixed"]
        lines.append(f"| Agent ({ag[0]['model'] if ag else 'none'}) and its fixed-choice version on the test cells: agent runs passing "
                     f"{sum(r['status'] == 'pass' for r in ag)} of {len(ag)}, fixed {sum(r['status'] == 'pass' for r in fx)} of {len(fx)} "
                     f"| `results/option1/m2/agent_vs_fixed.csv`, `ai/runs/` | {'pass' if ag and fx else 'FAIL'} |")
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    readme = paths.ROOT / "README.md"
    a, b = "<!-- o1-m2:start -->", "<!-- o1-m2:end -->"
    t = readme.read_text()
    if a in t and b in t:
        readme.write_text(t[:t.index(a) + len(a)] + "\n" + "\n".join(lines[2:]) + "\n" + t[t.index(b):])
    print("\n".join(lines))
    return 0 if ok_ref and ok_t5 and ok_cells else 1


if __name__ == "__main__":
    stages = {"refs": refs, "tests": tests, "table5": table5, "timing": timing, "summary": summary}
    sys.exit(stages[sys.argv[1]](*([sys.argv[2:]] if sys.argv[1] == "tests" and sys.argv[2:] else [])))
