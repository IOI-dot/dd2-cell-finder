"""Build and verify one cell end to end (Option 1 handout, section 4, steps 1-7 at cp1).

Work files go to build/cells/<name>/; the views and reports a reader needs go to cells/<name>/;
the evidence summary goes to results/option1/. Every check records its raw report path.
"""
import json
import re
import shutil
from pathlib import Path

from dd2 import boolfn as bf
from dd2 import liberty, paths, provenance

from . import abut, compare, eda, euler, layers, layout, network, simulate

TAP_ONLY = {"nwell.4", "LU.2", "LU.3"}   # a lone cell has no taps (handout section 2)
HD = "sky130_fd_sc_hd__"


def hd_gds() -> Path:
    return paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"


def installed_sizes(hd_cell: str) -> dict:
    """W of the installed cell's NMOS and PMOS (um), from the PDK SPICE netlist."""
    text = (paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice").read_text()
    body = re.search(rf"^\.subckt {HD}{hd_cell} .*?^\.ends", text, re.M | re.S).group(0)
    w = {"n": set(), "p": set()}
    for kind, val in re.findall(r"sky130_fd_pr__(n|p)fet_01v8\S* w=([\d.e+]+)u", body):
        w[kind].add(round(float(val) * 1e-6, 4))     # "650000u" = 0.65 um in these netlists
    return {k: sorted(v) for k, v in w.items()}


def reference(hd_cell: str) -> dict:
    """Function, pin order and sizes of an installed HD cell, read from the PDK."""
    cell = next(c for c in liberty.read_cells(paths.full_hd_lib()) if c.name == HD + hd_cell)
    sizes = installed_sizes(hd_cell)
    return {"inputs": cell.inputs, "tt": cell.tt, "function": cell.function,
            "wn": sizes["n"][0], "wp": sizes["p"][0], "sizes": sizes}


def _parasitics(rc_spice: str) -> dict:
    total = {}
    for a, b, v in re.findall(r"^C\d+ (\S+) (\S+) ([\d.e+-]+)f", rc_spice, re.M):
        for n in (a, b):
            total[n] = round(total.get(n, 0.0) + float(v), 5)
    res = len(re.findall(r"^R\d+ ", rc_spice, re.M))
    return {"c_fF_per_net": dict(sorted(total.items())), "resistors": res}


def build(name: str, inputs, tt: int, hd_cell: str | None = None, wn=0.65, wp=1.0,
          request: dict | None = None) -> dict:
    work = paths.build("cells", name)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    out = paths.ROOT / "cells" / name
    out.mkdir(parents=True, exist_ok=True)
    rec = provenance.RunRecord(argv=["cellgen", "build", name])
    rep = {"cell": name, "inputs": list(inputs), "truth_table": bf.to_hex(tt, len(inputs)),
           "sizing": {"nmos_w_um": wn, "pmos_w_um": wp, "l_um": 0.15}, "checks": {}}
    ck = rep["checks"]

    # 1-2: network and switch-level check
    net = network.single_stage(tt, inputs)
    errs = network.switch_check(net, tt)
    ck["network"] = {"status": "pass" if not errs and network.max_series(net) <= 3 else "fail",
                     "transistors": len(net.transistors), "max_series": network.max_series(net), "errors": errs}
    # 4: ordering; 5: layout
    order = euler.order(net)
    ck["ordering"] = {"status": "pass" if not euler.validate(net, order) else "fail",
                      "gates": order.gates, "rows": order.rows, "breaks": order.breaks}
    cell = layout.generate(net, order, name, wn=wn, wp=wp)
    gds = layout.write_gds(cell, work / "cell.gds")
    (work / "schematic.spice").write_text(layout.schematic_spice(net, name, wn, wp))
    rep["layout"] = {k: v for k, v in cell.report.items() if k != "rows"}
    if cell.report.get("route_failures"):
        ck["route"] = {"status": "fail", "nets": cell.report["route_failures"]}

    # 6: physical checks
    ck["layers"] = {"status": "pass" if not (e := layers.check(gds, name)) else "fail", "errors": e}
    code, log = eda.magic(work, eda.drc_script(["/w/cell.gds"], name), "drc_standalone")
    d = eda.parse_drc(log)
    ck["drc_standalone"] = d | {"status": "pass" if set(d["rules"]) <= TAP_ONLY and d["errors"] is not None else "fail",
                                "note": "a lone cell may only fail the tap rules nwell.4, LU.2, LU.3",
                                "report": "drc_standalone.log"}
    fixtures = abut.build(hd_gds(), gds, name, cell.width, work / "abut")
    abut_res = {}
    for fx, (fgds, top) in fixtures.items():
        _, flog = eda.magic(work / "abut", eda.drc_script([f"/w/{fgds.name}"], top), f"drc_{fx}")
        abut_res[fx] = eda.parse_drc(flog)
    total = sum(r["errors"] if r["errors"] is not None else 999 for r in abut_res.values())
    ck["abutment"] = {"status": "pass" if total == 0 else "fail", "errors": total, "fixtures": abut_res}
    ck["drc"] = {"status": ck["abutment"]["fixtures"]["side"]["errors"] == 0 and "pass" or "fail",
                 "errors": ck["abutment"]["fixtures"]["side"]["errors"], "where": "row tap|cell|inv_1|fill_1"}
    eda.magic(work, eda.extract_script("/w/cell.gds", name), "extract")
    ck["lvs"] = eda.netgen_lvs(work, f"{name}.spice", name, "schematic.spice", name, "lvs_schematic")
    ck["lvs"]["status"] = "pass" if ck["lvs"]["result"] == "match" else "fail"
    if hd_cell:
        r = eda.netgen_lvs(work, f"{name}.spice", name, eda.HD_SPICE, HD + hd_cell, "lvs_installed")
        ck["lvs_vs_installed"] = r | {"status": "pass" if r["result"] == "match" else "fail"}
    eda.magic(work, eda.extract_script("/w/cell.gds", name, rc=True), "extract_rc")
    rc = (work / f"{name}_rc.spice").read_text()

    # 7: function at transistor and model level
    sim = simulate.spice(work, name, work / f"{name}_rc.spice", inputs, tt)
    ck["spice"] = {k: v for k, v in sim.items() if k != "dc_volts"} | {"dc_volts": sim["dc_volts"]}
    (work / "cell.v").write_text(simulate.verilog_model(name, inputs, tt))
    ck["model"] = simulate.verilog_check(work / "cell.v", name, inputs, tt, work)

    # section 4.1: comparison with the installed cell
    if hd_cell:
        ours, inst = compare.Gds(gds, name), compare.Gds(hd_gds(), HD + hd_cell)
        eda.magic(work, "\n".join([f"gds read {eda.HD_GDS}", f"load {HD}{hd_cell}", "select top cell",
                                   "extract path /w", "extract all", "ext2spice lvs", "ext2spice cthresh 0",
                                   f"ext2spice -p /w -o /w/installed_rc.spice"]), "extract_installed")
        inst_rc = (work / "installed_rc.spice").read_text() if (work / "installed_rc.spice").exists() else ""
        rep["comparison"] = {
            "installed": HD + hd_cell,
            "frame_xor_um2": compare.frame_xor(ours, inst),
            "transistors_lvs_with_wl": ck["lvs_vs_installed"]["result"],
            "pins": {"ours": ours.labels(), "installed": inst.labels()},
            "wiring_layers": {"ours": compare.wiring_layers(ours), "installed": compare.wiring_layers(inst)},
            "width_sites": {"ours": round(ours.width() / 0.46), "installed": round(inst.width() / 0.46)},
            "gate_order": {"ours": compare.gate_order(ours), "installed": compare.gate_order(inst)},
            "parasitics": {"ours": _parasitics(rc), "installed": _parasitics(inst_rc)},
            "timing": "pending: the characterizer is a cp2 deliverable (handout Table 7)",
        }
        compare.svg([(f"ours: {name}", gds, name), (f"installed: {HD}{hd_cell}", hd_gds(), HD + hd_cell)],
                    out / "comparison.svg")

    required = ["network", "ordering", "layers", "drc_standalone", "drc", "abutment", "lvs", "spice", "model"]
    if hd_cell:
        required.append("lvs_vs_installed")
    failed = [k for k in required if ck.get(k, {}).get("status") != "pass"] + (["route"] if "route" in ck else [])
    rep["status"] = "pass" if not failed else "fail"
    rep["failed_checks"] = failed
    rec.finish(0 if not failed else 1)
    rep["run"] = rec.asdict()

    # views for the reader
    for f in ("cell.gds", "schematic.spice", "cell.v"):
        shutil.copy(work / f, out / f)
    shutil.copy(work / f"{name}.spice", out / "extracted.spice")
    shutil.copy(work / f"{name}_rc.spice", out / "rc_extracted.spice")
    provenance.write_json(out / "report.json", rep)
    if request is not None:
        provenance.write_json(out / "response.json", response(request, rep))
    return rep


def response(req: dict, rep: dict) -> dict:
    """Appendix A response. Liberty and characterization are cp2/cp3 work, so status stays fail."""
    ck = rep["checks"]
    name = rep["cell"]
    missing = "no Liberty yet: the characterizer is a cp2 deliverable"
    return {"request_id": req["request_id"], "status": "fail", "reason": missing, "cell": name, "stages": 1,
            "transistors": ck["network"]["transistors"], "width_sites": rep["layout"]["width_sites"],
            "area_um2": round(rep["layout"]["width_um"] * 2.72, 4),
            "files": {"gds": f"cells/{name}/cell.gds", "liberty": f"cells/{name}/cell.lib",
                      "verilog": f"cells/{name}/cell.v", "report": f"cells/{name}/report.json"},
            "checks": {"drc": ck["drc"]["errors"], "lvs": ck["lvs"]["result"], "rc_lvs": "not run",
                       "truth_table": "pass" if ck["spice"]["status"] == ck["model"]["status"] == "pass" else "fail",
                       "abutment": ck["abutment"]["errors"], "layers": ck["layers"]["status"]},
            "ngspice_sha256": "", "tool_version": "cellgen"}


def build_reference(hd_cell: str) -> dict:
    ref = reference(hd_cell)
    return build(f"dd2_ref__{hd_cell}", ref["inputs"], ref["tt"], hd_cell=hd_cell, wn=ref["wn"], wp=ref["wp"])


def frame_report() -> dict:
    """The HD frame checked against the installed cells (Option 1 M1)."""
    frame = layout.load_frame()["frame"]
    out = {}
    for c in ("inv_1", "nand2_1"):
        rows = compare.frame_check(compare.Gds(hd_gds(), HD + c), frame)
        out[HD + c] = {"match": all(r["match"] for r in rows), "rows": rows}
    return out
