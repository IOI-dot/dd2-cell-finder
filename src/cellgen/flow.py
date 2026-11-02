"""Build and verify one cell end to end (Option 1 handout, section 4, steps 1-7 at cp1).

Work files go to <work_root>/<name>/ (default build/cells/); the views and reports a reader needs
go to <out_root>/<name>/ (default cells/). Every check records its raw report path, and the cell's
status is pass only if every required check passes.
"""
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dd2 import boolfn as bf
from dd2 import liberty, paths, provenance

from . import abut, compare, eda, euler, layers, layout, network, simulate, stress

TAP_ONLY = {"nwell.4", "LU.2", "LU.3"}   # a lone cell has no taps (handout section 2)
HD = "sky130_fd_sc_hd__"
SIX = ("inv_1", "nand2_1", "nor2_1", "nand3_1", "a21oi_1", "o21ai_1")
MULTI_STAGE = ("a21o_1", "mux2_1")
SUPPLIES = ["VGND", "VNB", "VPB", "VPWR"]


def standalone_ok(d: dict) -> bool:
    """A lone cell passes if it has no DRC error, or if every error is a tap rule; errors whose
    reason could not be parsed never pass."""
    if d["errors"] is None:
        return False
    return d["errors"] == 0 or (bool(d["rules"]) and set(d["rules"]) <= TAP_ONLY)


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


def installed_transistors(hd_cell: str) -> list:
    """The installed cell's devices, from the PDK SPICE netlist."""
    return [network.Transistor(kind, g, d, s_, w=round(float(w) * 1e-6, 4))
            for d, g, s_, kind, w in re.findall(r"^X\d+ (\S+) (\S+) (\S+) \S+ sky130_fd_pr__(n|p)fet_01v8\S* w=([\d.e+]+)u",
                                                _subckt(hd_cell), re.M)]


def installed_output(hd_cell: str) -> str:
    ports = _subckt(hd_cell).splitlines()[0].split()[2:]
    return ports[ports.index("VPWR") + 1]


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
    """R and C on each net: a net's subnodes (Y.t0, Y.n1) count as the net."""
    base = lambda n: n.split(".")[0].rstrip("#")                               # noqa: E731
    cap, res = {}, {}
    for a, b, v in re.findall(r"^C\S* (\S+) (\S+) ([\d.e+-]+)f", rc_spice, re.M):
        for n in {base(a), base(b)}:
            cap[n] = round(cap.get(n, 0.0) + float(v), 5)
    for a, b, v in re.findall(r"^R\S* (\S+) (\S+) ([\d.e+-]+)", rc_spice, re.M):
        if base(a) == base(b):
            res[base(a)] = round(res.get(base(a), 0.0) + float(v), 3)
    return {"c_fF_per_net": dict(sorted(cap.items())), "r_ohm_per_net": dict(sorted(res.items())),
            "r_ohm_total": round(sum(res.values()), 3)}


def _rects(cell) -> dict:
    """The cell's drawn shapes by layer, for the live view."""
    out = {}
    for r in cell.rects:
        if r.layer in ("nwell", "diff", "poly", "licon", "li1", "mcon", "met1"):
            out.setdefault(r.layer, []).append(r.box)
    return out


def _wave(work: Path, points: int = 400) -> list:
    """Y against time from the transient the SPICE check judged, thinned for drawing."""
    tran = work / "tran.txt"
    if not tran.exists():
        return []
    rows = [line.split() for line in tran.read_text().splitlines()[1:] if line.strip()]
    step = max(1, len(rows) // points)
    return [[round(float(r[0]) * 1e9, 3), round(float(r[1]), 3)] for r in rows[::step]]


def hd_port_order(netlist: str, cell: str, inputs, out="Y") -> str:
    """Rewrite the .subckt line in HD's port order: inputs, VGND VNB VPB VPWR, then the output."""
    order = list(inputs) + SUPPLIES + [out]
    old = simulate.subckt_ports(netlist, cell)
    if sorted(old) != sorted(order):
        raise ValueError(f"extracted ports {old} are not {order}")
    return re.sub(rf"^(\.subckt\s+{re.escape(cell)}\s+).*$", lambda m: m.group(1) + " ".join(order),
                  netlist, count=1, flags=re.M | re.I)


def build(name: str, inputs, tt: int, hd_cell: str | None = None, wn=0.65, wp=1.0,
          request: dict | None = None, out_root: Path | None = None, work_root: Path | None = None,
          sizing: str = "hd", net=None, match_installed: bool = True, layout_opts: dict | None = None) -> dict:
    """match_installed: Table 4's transistor row must match. False for a21o_1 and mux2_1, whose
    transistor comparison is only reported."""
    work = Path(work_root or paths.build("cells")) / name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    out = Path(out_root or paths.ROOT / "cells") / name
    out.mkdir(parents=True, exist_ok=True)
    rec = provenance.RunRecord(argv=["cellgen", "build", name])
    rep = {"cell": name, "inputs": list(inputs), "truth_table": bf.to_hex(tt, len(inputs)),
           "sizing": {"policy": sizing, "nmos_w_um": wn, "pmos_w_um": wp, "l_um": 0.15}, "checks": {}}
    ck = rep["checks"]

    # steps 1-3: network, switch-level check, sizing
    eda.trace("network", "Finding the CMOS network", "running", f"truth table {rep['truth_table']}", "network",
              {"inputs": list(inputs), "tt": tt})
    net = network.size(net or network.synthesize(tt, inputs), sizing, wn, wp)
    errs = network.switch_check(net, tt)
    eda.trace("network", "CMOS network and switch-level check", "bad" if errs else "ok",
              f"{len(net.transistors)} transistors in {len(net.stages)} stage(s), at most {network.max_series(net)} in series, every input row checked",
              "network", {"inputs": list(inputs), "tt": tt, "stages": len(net.stages),
                          "transistors": [{"kind": t.kind, "gate": t.gate, "w": t.w, "stage": t.stage} for t in net.transistors]})
    ck["network"] = {"status": "pass" if not errs and network.max_series(net) <= 3 else "fail",
                     "transistors": len(net.transistors), "stages": len(net.stages),
                     "stage_outputs": [s.out for s in net.stages], "max_series": network.max_series(net),
                     "errors": errs}
    if hd_cell and installed_output(hd_cell) != "Y":
        net = network.rename_output(net, installed_output(hd_cell))
    y = net.output
    # step 4: ordering; step 5: layout
    orders = euler.candidates(net)
    eda.trace("ordering", "Paired Euler ordering", "ok", f"{len(orders)} gate orders kept, best has {orders[0].breaks} diffusion break(s): {' '.join(orders[0].gates)}",
              "euler", {"gates": orders[0].gates, "rows": orders[0].rows, "breaks": orders[0].breaks, "candidates": len(orders)})
    eda.trace("layout", "Placing and routing on li1", "running", "narrowest layouts first", "layout")
    cell = layout.generate(net, orders[0], name, orders=orders, wn=wn, wp=wp,
                           progress=lambda n, w, m: eda.trace("layout", "Placing and routing on li1", "running",
                                                              f"attempt {n}, trying {w} sites{' with met1' if m else ''}", "layout"), **(layout_opts or {}))
    eda.trace("layout", "Layout", "bad" if cell.report.get("route_failures") else "ok",
              f"{cell.report['width_sites']} sites after {cell.report['layout_attempts']} attempt(s), order {' '.join(cell.report['gate_order'])}"
              + (f", met1 on {' '.join(cell.report['met1_nets'])}" if cell.report.get("met1_nets") else "")
              + (f", could not route {cell.report['route_failures']}" if cell.report.get("route_failures") else ""),
              "layout", {"width_um": cell.width, "height_um": 2.72, "rects": _rects(cell), "labels": cell.labels})
    rep["layout_options"] = layout_opts or {}
    ck["ordering"] = {"status": "pass" if not any(euler.validate(net, o) for o in orders) else "fail",
                      "gates": cell.report["gate_order"], "rows": cell.report["rows"],
                      "breaks": cell.report["diffusion_breaks"], "row_breaks": cell.report["row_breaks"]}
    gds = layout.write_gds(cell, work / "cell.gds")
    (work / "schematic.spice").write_text(layout.schematic_spice(net, name, wn, wp))
    rep["layout"] = {k: v for k, v in cell.report.items() if k != "rows"}
    if cell.report.get("route_failures"):
        ck["route"] = {"status": "fail", "nets": cell.report["route_failures"]}

    # the frame, pins and wiring of the generated cell (handout sections 2 and 4.1)
    ours = compare.Gds(gds, name)
    frame = compare.frame_check(ours, layout.load_frame()["frame"])
    ck["frame"] = {"status": "pass" if all(r["match"] for r in frame) else "fail", "rows": frame}
    pin_errs = compare.pin_check(ours, inputs, y)
    ck["pins"] = {"status": "pass" if not pin_errs else "fail", "errors": pin_errs}
    wiring = compare.wiring_layers(ours, len(net.stages) > 1 and bool(cell.report.get("met1_nets")))
    ck["wiring_layers"] = wiring | {"status": "pass" if wiring["ok"] else "fail"}

    # step 6: physical checks
    ck["layers"] = {"status": "pass" if not (e := layers.check(gds, name)) else "fail", "errors": e}
    eda.trace("geometry", "Frame, pins, wiring layers and implants", "ok" if all(ck[k]["status"] == "pass" for k in ("frame", "pins", "wiring_layers", "layers")) else "bad",
              "checked against plan_hd.json with KLayout", "frame")
    # five independent Magic runs side by side: together they take about as long as one
    fixtures = abut.build(hd_gds(), gds, name, cell.width, work / "abut")
    with ThreadPoolExecutor(5) as pool:
        alone = pool.submit(eda.magic, work, eda.drc_script(["/w/cell.gds"], name), "drc_standalone")
        rows = {fx: pool.submit(eda.magic, work / "abut", eda.drc_script([f"/w/{fgds.name}"], top), f"drc_{fx}")
                for fx, (fgds, top) in fixtures.items()}
    d = eda.parse_drc(alone.result()[1])
    ck["drc_standalone"] = d | {"status": "pass" if standalone_ok(d) else "fail",
                                "note": "a lone cell may only fail the tap rules nwell.4, LU.2, LU.3",
                                "report": "drc_standalone.log"}
    abut_res = {fx: eda.parse_drc(f.result()[1]) for fx, f in rows.items()}
    total = sum(r["errors"] if r["errors"] is not None else 999 for r in abut_res.values())
    ck["abutment"] = {"status": "pass" if total == 0 else "fail", "errors": total, "fixtures": abut_res}
    eda.trace("abutment", "Abutment with HD cells", "ok" if total == 0 else "bad", f"{total} errors in side, mirror, self and flip rows", "abutment")
    side = abut_res["side"]["errors"]
    ck["drc"] = {"status": "pass" if side == 0 else "fail", "errors": side, "where": "row tap|cell|inv_1|fill_1"}
    eda.trace("drc", "Design rules", "ok" if ck["drc"]["status"] == ck["drc_standalone"]["status"] == "pass" else "bad",
              f"{side} errors in a tap row; alone only the tap rules fire" if side == 0 else f"{side} errors: {' '.join(abut_res['side']['rules'])}", "drc")
    eda.magic(work, eda.extract_script("/w/cell.gds", name), "extract")
    ck["lvs"] = eda.netgen_lvs(work, f"{name}.spice", name, "schematic.spice", name, "lvs_schematic")
    ck["lvs"]["status"] = "pass" if ck["lvs"]["result"] == "match" else "fail"
    eda.trace("lvs", "LVS against the schematic", "ok" if ck["lvs"]["result"] == "match" else "bad", ck["lvs"]["result"], "lvs")
    if hd_cell:
        r = eda.netgen_lvs(work, f"{name}.spice", name, eda.HD_SPICE, HD + hd_cell, "lvs_installed")
        ck["lvs_vs_installed"] = r | {"status": "pass" if r["result"] == "match" else "fail"}
    eda.magic(work, eda.extract_script("/w/cell.gds", name, rc=True), "extract_rc")
    rc_path = work / f"{name}_rc.spice"
    rc = rc_path.read_text() if rc_path.exists() else ""
    if rc:
        (work / "rc_lvs.spice").write_text(eda.rc_for_lvs(rc))
        r = eda.netgen_lvs(work, "rc_lvs.spice", name, "schematic.spice", name, "lvs_rc")
        ck["rc_lvs"] = r | {"status": "pass" if r["result"] == "match" else "fail"}
        eda.trace("rc", "RC extraction and RC-LVS", "ok" if r["result"] == "match" else "bad",
                  f"{len(re.findall(r'^R', rc, re.M))} resistors, {len(re.findall(r'^C', rc, re.M))} capacitors, {r['result']}", "rc_lvs")
    else:
        ck["rc_lvs"] = {"status": "fail", "result": "no RC netlist"}

    # step 7: function at transistor and model level
    sized_rc = work / f"{name}_rc_sasb.spice"
    if rc:
        stress.annotate(rc_path, sized_rc, gds, name)
        ck["spice"] = simulate.spice(work, name, sized_rc, inputs, tt, out=y)
        eda.trace("spice", "Simulation of the extracted netlist", "ok" if ck["spice"]["status"] == "pass" else "bad",
                  f"{1 << len(inputs)} DC rows and {ck['spice']['slots']} transient steps, {len(ck['spice']['errors'])} errors", "spice",
                  {"dc": ck["spice"]["dc_volts"], "wave": _wave(work), "states": simulate.sequence(len(inputs)), "slot_ns": simulate.SLOT_NS})
    else:
        ck["spice"] = {"status": "fail", "errors": ["no RC netlist"]}
    (work / "cell.v").write_text(simulate.verilog_model(name, inputs, tt, y))
    ck["model"] = simulate.verilog_check(work / "cell.v", name, inputs, tt, work, y)
    eda.trace("verilog", "Icarus on the Verilog model", "ok" if ck["model"]["status"] == "pass" else "bad", f"every one of {1 << len(inputs)} input rows", "verilog")

    # section 4.1: comparison with the installed cell (same Magic RC flow, same testbench)
    if hd_cell:
        inst = compare.Gds(hd_gds(), HD + hd_cell)
        eda.magic(work, eda.extract_script(eda.HD_GDS, HD + hd_cell, rc=True), "extract_installed_rc")
        inst_rc_path = work / f"{HD}{hd_cell}_rc.spice"
        inst_rc = inst_rc_path.read_text() if inst_rc_path.exists() else ""
        xor = compare.frame_xor(ours, inst)
        inst_pins = compare.pin_check(inst, inputs, y)
        timing = {}
        if inst_rc and rc:
            tdir = work / "timing"
            tdir.mkdir(exist_ok=True)
            shutil.copy(sized_rc, tdir / "ours.spice")
            stress.annotate(inst_rc_path, tdir / "installed.spice", hd_gds(), HD + hd_cell)
            timing = {"ours": simulate.delays(tdir, name, tdir / "ours.spice", inputs, tt, out=y),
                      "installed": simulate.delays(tdir, HD + hd_cell, tdir / "installed.spice", inputs, tt, out=y),
                      "point": simulate.hd_table_point(),
                      "method": "ngspice on both RC-extracted cells with SA/SB, 50% delay and 20-80% transition"}
        inst_devs = installed_transistors(hd_cell)
        widths = lambda ts: sorted((t.kind, t.w) for t in ts)                # noqa: E731
        frame_ok = xor["identical"] or (not xor.get("compared") and ck["frame"]["status"] == "pass")
        rep["comparison"] = {
            "installed": HD + hd_cell,
            "frame": {"xor_um2": xor, "y_extents": ck["frame"]["status"], "verdict": "match" if frame_ok else "differ"},
            "transistors": {"lvs_with_wl": ck["lvs_vs_installed"]["result"], "count_ours": len(net.transistors),
                            "count_installed": len(inst_devs), "w_ours": widths(net.transistors),
                            "w_installed": widths(inst_devs)},
            "pins": {"ours_errors": pin_errs, "installed_errors": inst_pins,
                     "ours": ours.labels(), "installed": inst.labels(),
                     "shapes_ours": compare.pin_shapes(ours), "shapes_installed": compare.pin_shapes(inst)},
            "wiring_layers": {"ours": wiring, "installed": compare.wiring_layers(inst)},
            "abutment": {"errors": total},
            "width_sites": {"ours": round(ours.width() / 0.46), "installed": round(inst.width() / 0.46)},
            "gate_order": {"ours": compare.gate_order(ours), "installed": compare.gate_order(inst)},
            "parasitics": {"ours": _parasitics(rc), "installed": _parasitics(inst_rc)},
            "timing": timing,
        }
        must = frame_ok and not pin_errs and wiring["ok"] and total == 0
        if match_installed:
            must = must and ck["lvs_vs_installed"]["result"] == "match"
        ck["comparison"] = {"status": "pass" if must else "fail",
                            "rule": "Table 4 'must match' rows: frame, transistors, pins, wiring layers, abutment"
                            + ("" if match_installed else " (transistors reported, not required: multi-stage)")}
        compare.svg([(f"ours: {name}", gds, name), (f"installed: {HD}{hd_cell}", hd_gds(), HD + hd_cell)],
                    out / "comparison.svg")

    required = ["network", "ordering", "frame", "pins", "wiring_layers", "layers", "drc_standalone", "drc",
                "abutment", "lvs", "rc_lvs", "spice", "model"]
    required += (["lvs_vs_installed"] if hd_cell and match_installed else []) + (["comparison"] if hd_cell else [])
    failed = [k for k in required if ck.get(k, {}).get("status") != "pass"] + (["route"] if "route" in ck else [])
    rep["status"] = "pass" if not failed else "fail"
    rep["failed_checks"] = failed
    rec.finish(0 if not failed else 1)
    rep["run"] = rec.asdict()

    # views for the reader (netlists in HD's port order), and the tools' own verdicts as evidence
    for f in ("cell.gds", "schematic.spice", "cell.v"):
        shutil.copy(work / f, out / f)
    (out / "logs").mkdir(exist_ok=True)
    for f in ("drc_standalone.log", "lvs_schematic.out", "lvs_rc.out", "lvs_installed.out", "spice_dc.log", "abut/drc_side.log",
              "abut/drc_mirror.log", "abut/drc_self.log", "abut/drc_flip.log"):
        if (work / f).exists():
            shutil.copy(work / f, out / "logs" / Path(f).name)
    raw = (work / f"{name}.spice").read_text()
    try:
        (out / "extracted.spice").write_text(hd_port_order(raw, name, inputs, y))
        (out / "rc_extracted.spice").write_text(hd_port_order(sized_rc.read_text(), name, inputs, y))
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
    """Sizes and pin names from the installed netlist (handout 4.1). A single-stage reference also
    takes its series order from there, or Netgen could never match it; a multi-stage one is split
    by our own decomposition, so it takes only the pin names."""
    ref = reference(hd_cell)
    if hd_cell in MULTI_STAGE:
        rep = build(f"dd2_ref__{hd_cell}", ref["inputs"], ref["tt"], hd_cell=hd_cell, out_root=out_root,
                    work_root=work_root, match_installed=False)
    else:
        net = network.match_installed(ref["tt"], ref["inputs"], installed_transistors(hd_cell))
        rep = build(f"dd2_ref__{hd_cell}", ref["inputs"], ref["tt"], hd_cell=hd_cell, wn=ref["wn"], wp=ref["wp"],
                    out_root=out_root, work_root=work_root, net=net)
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
