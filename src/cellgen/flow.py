"""Build and verify one cell end to end (Option 1 handout, section 4, steps 1-7 at cp1).

Work files go to <work_root>/<name>/ (default build/cells/); the views and reports a reader needs
go to <out_root>/<name>/ (default cells/). Every check records its raw report path, and the cell's
status is pass only if every required check passes.
"""
import re
import shutil
from pathlib import Path

from dd2 import boolfn as bf
from dd2 import liberty, paths, provenance

from . import abut, compare, eda, euler, layers, layout, network, simulate

TAP_ONLY = {"nwell.4", "LU.2", "LU.3"}   # a lone cell has no taps (handout section 2)
HD = "sky130_fd_sc_hd__"
SUPPLIES = ["VGND", "VNB", "VPB", "VPWR"]


def hd_gds() -> Path:
    return paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"


def hd_spice() -> Path:
    return paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"


def _subckt(hd_cell: str) -> str:
    return re.search(rf"^\.subckt {HD}{hd_cell} .*?^\.ends", hd_spice().read_text(), re.M | re.S).group(0)


def installed_sizes(hd_cell: str) -> dict:
    """W of the installed cell's NMOS and PMOS (um), from the PDK SPICE netlist."""
    w = {"n": set(), "p": set()}
    for kind, val in re.findall(r"sky130_fd_pr__(n|p)fet_01v8\S* w=([\d.e+]+)u", _subckt(hd_cell)):
        w[kind].add(round(float(val) * 1e-6, 4))     # "650000u" = 0.65 um in these netlists
    return {k: sorted(v) for k, v in w.items()}


def installed_pins(hd_cell: str) -> list:
    """Input pins of the installed cell, in the SPICE port order (inputs come before VGND)."""
    ports = _subckt(hd_cell).splitlines()[0].split()[2:]
    return ports[:ports.index("VGND")]


def reference(hd_cell: str) -> dict:
    """Pin names and sizes from the installed SPICE netlist (handout 4.1); the function from the
    Liberty file, whose input order must agree with the netlist."""
    cell = next(c for c in liberty.read_cells(paths.full_hd_lib()) if c.name == HD + hd_cell)
    pins = installed_pins(hd_cell)
    if sorted(pins) != sorted(cell.inputs):
        raise ValueError(f"{hd_cell}: SPICE pins {pins} differ from Liberty pins {cell.inputs}")
    tt = bf.permute(cell.tt, len(pins), [cell.inputs.index(p) for p in pins])
    sizes = installed_sizes(hd_cell)
    return {"inputs": pins, "tt": tt, "function": cell.function, "wn": sizes["n"][0], "wp": sizes["p"][0],
            "sizes": sizes, "pins_from": "PDK SPICE netlist (checked against the Liberty file)"}


def _parasitics(rc_spice: str) -> dict:
    total = {}
    for a, b, v in re.findall(r"^C\d+ (\S+) (\S+) ([\d.e+-]+)f", rc_spice, re.M):
        for n in (a, b):
            total[n] = round(total.get(n, 0.0) + float(v), 5)
    res = re.findall(r"^R\d+ \S+ \S+ ([\d.e+-]+)", rc_spice, re.M)
    return {"c_fF_per_net": dict(sorted(total.items())), "resistors": len(res),
            "r_ohm_total": round(sum(float(r) for r in res), 3),
            "note": "Magic extresist (tolerance 10) keeps no resistor in a cell this small" if not res else ""}


def hd_port_order(netlist: str, cell: str, inputs) -> str:
    """Rewrite the .subckt line in HD's port order: inputs, VGND VNB VPB VPWR, then Y."""
    order = list(inputs) + SUPPLIES + ["Y"]
    old = simulate.subckt_ports(netlist, cell)
    if sorted(old) != sorted(order):
        raise ValueError(f"extracted ports {old} are not {order}")
    return re.sub(rf"^(\.subckt\s+{re.escape(cell)}\s+).*$", lambda m: m.group(1) + " ".join(order),
                  netlist, count=1, flags=re.M | re.I)


def build(name: str, inputs, tt: int, hd_cell: str | None = None, wn=0.65, wp=1.0,
          request: dict | None = None, out_root: Path | None = None, work_root: Path | None = None) -> dict:
    work = Path(work_root or paths.build("cells")) / name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    out = Path(out_root or paths.ROOT / "cells") / name
    out.mkdir(parents=True, exist_ok=True)
    rec = provenance.RunRecord(argv=["cellgen", "build", name])
    rep = {"cell": name, "inputs": list(inputs), "truth_table": bf.to_hex(tt, len(inputs)),
           "sizing": {"nmos_w_um": wn, "pmos_w_um": wp, "l_um": 0.15}, "checks": {}}
    ck = rep["checks"]

    # steps 1-2: network and switch-level check
    net = network.single_stage(tt, inputs)
    errs = network.switch_check(net, tt)
    ck["network"] = {"status": "pass" if not errs and network.max_series(net) <= 3 else "fail",
                     "transistors": len(net.transistors), "max_series": network.max_series(net), "errors": errs}
    # step 4: ordering; step 5: layout
    order = euler.order(net)
    ck["ordering"] = {"status": "pass" if not euler.validate(net, order) else "fail",
                      "gates": order.gates, "rows": order.rows, "breaks": order.breaks}
    cell = layout.generate(net, order, name, wn=wn, wp=wp)
    gds = layout.write_gds(cell, work / "cell.gds")
    (work / "schematic.spice").write_text(layout.schematic_spice(net, name, wn, wp))
    rep["layout"] = {k: v for k, v in cell.report.items() if k != "rows"}
    if cell.report.get("route_failures"):
        ck["route"] = {"status": "fail", "nets": cell.report["route_failures"]}

    # the frame, pins and wiring of the generated cell (handout sections 2 and 4.1)
    ours = compare.Gds(gds, name)
    frame = compare.frame_check(ours, layout.load_frame()["frame"])
    ck["frame"] = {"status": "pass" if all(r["match"] for r in frame) else "fail", "rows": frame}
    pin_errs = compare.pin_check(ours, inputs)
    ck["pins"] = {"status": "pass" if not pin_errs else "fail", "errors": pin_errs}
    wiring = compare.wiring_layers(ours)
    ck["wiring_layers"] = wiring | {"status": "pass" if wiring["ok"] else "fail"}

    # step 6: physical checks
    ck["layers"] = {"status": "pass" if not (e := layers.check(gds, name)) else "fail", "errors": e}
    _, log = eda.magic(work, eda.drc_script(["/w/cell.gds"], name), "drc_standalone")
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
    side = abut_res["side"]["errors"]
    ck["drc"] = {"status": "pass" if side == 0 else "fail", "errors": side, "where": "row tap|cell|inv_1|fill_1"}
    eda.magic(work, eda.extract_script("/w/cell.gds", name), "extract")
    ck["lvs"] = eda.netgen_lvs(work, f"{name}.spice", name, "schematic.spice", name, "lvs_schematic")
    ck["lvs"]["status"] = "pass" if ck["lvs"]["result"] == "match" else "fail"
    if hd_cell:
        r = eda.netgen_lvs(work, f"{name}.spice", name, eda.HD_SPICE, HD + hd_cell, "lvs_installed")
        ck["lvs_vs_installed"] = r | {"status": "pass" if r["result"] == "match" else "fail"}
    eda.magic(work, eda.extract_script("/w/cell.gds", name, rc=True), "extract_rc")
    rc = (work / f"{name}_rc.spice").read_text()

    # step 7: function at transistor and model level
    sim = simulate.spice(work, name, work / f"{name}_rc.spice", inputs, tt)
    ck["spice"] = sim
    (work / "cell.v").write_text(simulate.verilog_model(name, inputs, tt))
    ck["model"] = simulate.verilog_check(work / "cell.v", name, inputs, tt, work)

    # section 4.1: comparison with the installed cell (same Magic RC flow, same testbench)
    if hd_cell:
        inst = compare.Gds(hd_gds(), HD + hd_cell)
        eda.magic(work, eda.extract_script(eda.HD_GDS, HD + hd_cell, rc=True), "extract_installed_rc")
        inst_rc_path = work / f"{HD}{hd_cell}_rc.spice"
        inst_rc = inst_rc_path.read_text() if inst_rc_path.exists() else ""
        xor = compare.frame_xor(ours, inst)
        inst_pins = compare.pin_check(inst, inputs)
        timing = {}
        if inst_rc:
            tdir = work / "timing"
            tdir.mkdir(exist_ok=True)
            shutil.copy(work / f"{name}_rc.spice", tdir / "ours.spice")
            shutil.copy(inst_rc_path, tdir / "installed.spice")
            timing = {"ours": simulate.delays(tdir, name, tdir / "ours.spice", inputs, tt),
                      "installed": simulate.delays(tdir, HD + hd_cell, tdir / "installed.spice", inputs, tt),
                      "point": simulate.hd_table_point(),
                      "method": "ngspice on both RC-extracted cells, 50% delay and 20-80% transition; "
                                "the calibrated characterizer is cp2 work"}
        rep["comparison"] = {
            "installed": HD + hd_cell,
            "frame": {"xor_um2": xor, "verdict": "match" if xor["identical"] else "differ"},
            "transistors": {"lvs_with_wl": ck["lvs_vs_installed"]["result"]},
            "pins": {"ours_errors": pin_errs, "installed_errors": inst_pins,
                     "ours": ours.labels(), "installed": inst.labels()},
            "wiring_layers": {"ours": wiring, "installed": compare.wiring_layers(inst)},
            "abutment": {"errors": total},
            "width_sites": {"ours": round(ours.width() / 0.46), "installed": round(inst.width() / 0.46)},
            "gate_order": {"ours": compare.gate_order(ours), "installed": compare.gate_order(inst)},
            "parasitics": {"ours": _parasitics(rc), "installed": _parasitics(inst_rc)},
            "timing": timing,
        }
        must = xor["identical"] and ck["lvs_vs_installed"]["result"] == "match" and not pin_errs \
            and wiring["ok"] and total == 0
        ck["comparison"] = {"status": "pass" if must else "fail",
                            "rule": "Table 4 'must match' rows: frame, transistors, pins, wiring layers, abutment"}
        compare.svg([(f"ours: {name}", gds, name), (f"installed: {HD}{hd_cell}", hd_gds(), HD + hd_cell)],
                    out / "comparison.svg")

    required = ["network", "ordering", "frame", "pins", "wiring_layers", "layers", "drc_standalone", "drc",
                "abutment", "lvs", "spice", "model"] + (["lvs_vs_installed", "comparison"] if hd_cell else [])
    failed = [k for k in required if ck.get(k, {}).get("status") != "pass"] + (["route"] if "route" in ck else [])
    rep["status"] = "pass" if not failed else "fail"
    rep["failed_checks"] = failed
    rec.finish(0 if not failed else 1)
    rep["run"] = rec.asdict()

    # views for the reader (netlists in HD's port order)
    for f in ("cell.gds", "schematic.spice", "cell.v"):
        shutil.copy(work / f, out / f)
    raw = (work / f"{name}.spice").read_text()
    try:
        (out / "extracted.spice").write_text(hd_port_order(raw, name, inputs))
        (out / "rc_extracted.spice").write_text(hd_port_order(rc, name, inputs))
    except ValueError as e:                # e.g. a net left in pieces: keep the raw netlists, fail the cell
        (out / "extracted.spice").write_text(raw)
        (out / "rc_extracted.spice").write_text(rc)
        ck["ports"] = {"status": "fail", "error": str(e)}
        rep["status"] = "fail"
        rep["failed_checks"] = sorted(set(rep["failed_checks"]) | {"ports"})
        rep["run"]["status"] = "fail"
    provenance.write_json(out / "report.json", rep)
    if request is not None:
        provenance.write_json(out / "response.json", response(request, rep))
    return rep


def response(req: dict, rep: dict) -> dict:
    """Appendix A response. Liberty and characterization are cp2/cp3 work, so status stays fail."""
    ck = rep["checks"]
    name = rep["cell"]
    return {"request_id": req["request_id"], "status": "fail",
            "reason": "no Liberty yet: the characterizer is a cp2 deliverable" if rep["status"] == "pass"
            else "failed checks: " + ", ".join(rep["failed_checks"]),
            "cell": name, "stages": 1, "transistors": ck["network"]["transistors"],
            "width_sites": rep["layout"]["width_sites"], "area_um2": round(rep["layout"]["width_um"] * 2.72, 4),
            "files": {"gds": f"cells/{name}/cell.gds", "liberty": f"cells/{name}/cell.lib",
                      "verilog": f"cells/{name}/cell.v", "report": f"cells/{name}/report.json"},
            "checks": {"drc": ck["drc"]["errors"], "lvs": ck["lvs"]["result"], "rc_lvs": "not run",
                       "truth_table": "pass" if ck["spice"]["status"] == ck["model"]["status"] == "pass" else "fail",
                       "abutment": ck["abutment"]["errors"], "layers": ck["layers"]["status"]},
            "ngspice_sha256": "", "tool_version": "cellgen"}


def build_reference(hd_cell: str, out_root: Path | None = None, work_root: Path | None = None) -> dict:
    ref = reference(hd_cell)
    rep = build(f"dd2_ref__{hd_cell}", ref["inputs"], ref["tt"], hd_cell=hd_cell, wn=ref["wn"], wp=ref["wp"],
                out_root=out_root, work_root=work_root)
    rep["reference"] = {k: v for k, v in ref.items() if k != "tt"}
    provenance.write_json(Path(out_root or paths.ROOT / "cells") / rep["cell"] / "report.json", rep)
    return rep


def frame_report() -> dict:
    """The HD frame checked against the installed cells (Option 1 M1)."""
    frame = layout.load_frame()["frame"]
    out = {}
    for c in ("inv_1", "nand2_1"):
        rows = compare.frame_check(compare.Gds(hd_gds(), HD + c), frame)
        out[HD + c] = {"match": all(r["match"] for r in rows), "rows": rows}
    return out
