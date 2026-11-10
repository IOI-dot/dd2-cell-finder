"""Every Option 1 check must fail on a deliberately broken case (overview 4.3, rule 3).

The defects are made from a freshly generated nand2 so the checks are exercised end to end; the
course tools run in the dd2-layout-tools image (these tests skip if it is not built).
"""
import itertools
import re
import shutil
import subprocess

import pytest

pytest.importorskip("klayout", reason="Option 1 needs KLayout/GDSfactory (make setup installs them)")

from cellgen import abut, eda, euler, flow, layout, network, simulate
from dd2 import boolfn as bf
from dd2 import paths

pytestmark = pytest.mark.skipif(
    subprocess.run(["docker", "image", "inspect", eda.IMAGE], capture_output=True).returncode != 0,
    reason="course image dd2-layout-tools not built (make o1-image)")

NAME = "t_nand2"
_n = itertools.count()


@pytest.fixture
def tmp_path():
    """Docker (Colima) only sees the user's home: keep tool work dirs under build/."""
    d = paths.build("test_o1", f"t{next(_n)}")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    return d
TT = bf.eval_expr("!(A&B)", "AB")


@pytest.fixture(scope="module")
def work():
    d = paths.build("test_o1", "work")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    net = network.single_stage(TT, ["A", "B"])
    cell = layout.generate(net, euler.order(net), NAME)
    layout.write_gds(cell, d / "cell.gds")
    (d / "schematic.spice").write_text(layout.schematic_spice(net, NAME))
    eda.magic(d, eda.extract_script("/w/cell.gds", NAME), "extract")
    return d, cell, net


def test_good_cell_passes_lvs(work):
    d, _, _ = work
    assert eda.netgen_lvs(d, f"{NAME}.spice", NAME, "schematic.spice", NAME, "lvs_ok")["result"] == "match"


def test_drc_rejects_gate_pitch_below_rule(work, tmp_path):
    _, cell, _ = work
    gates = sorted({r.box[0] for r in cell.rects if r.layer == "poly" and r.box[3] - r.box[1] > 2})
    shift = 0.08                                    # A's gate moves 0.08 um towards B: poly.2 must fire
    rects = [layout.Rect(r.layer, (r.box[0] - shift, r.box[1], r.box[2] - shift, r.box[3]), r.net)
             if r.layer == "poly" and r.net == "A" else r for r in cell.rects]
    bad = layout.Cell(NAME, cell.width, rects, cell.labels)
    layout.write_gds(bad, tmp_path / "cell.gds")
    _, log = eda.magic(tmp_path, eda.drc_script(["/w/cell.gds"], NAME), "drc")
    d = eda.parse_drc(log)
    assert d["errors"] and "poly.2" in d["rules"], d
    assert len(gates) == 2


def test_lvs_rejects_wrong_width(work):
    d, _, net = work
    (d / "schematic_badw.spice").write_text(layout.schematic_spice(net, NAME, wn=0.42))
    r = eda.netgen_lvs(d, f"{NAME}.spice", NAME, "schematic_badw.spice", NAME, "lvs_badw")
    assert r["result"] == "mismatch"


def _schematic(net, gate_map):
    """The generator's schematic with transistor gates renamed by gate_map[(kind, index)]."""
    lines = layout.schematic_spice(net, NAME).splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.startswith("X"):
            f = line.split()
            k = int(f[0][1:])
            f[2] = gate_map.get(k, f[2])
            line = " ".join(f)
        out.append(line)
    return "\n".join(out) + "\n"


def test_lvs_rejects_swapped_pins(work):
    # NEG-08: A and B exchanged on every transistor; the ports keep their names
    d, _, net = work
    swap = {i: {"A": "B", "B": "A"}[t.gate] for i, t in enumerate(net.transistors)}
    (d / "schematic_pins.spice").write_text(_schematic(net, swap))
    assert eda.netgen_lvs(d, f"{NAME}.spice", NAME, "schematic_pins.spice", NAME, "lvs_pins")["result"] == "mismatch"


def test_lvs_rejects_swapped_series_order(work):
    # only the two series NMOS exchange gates: B next to Y, A next to VGND (HD has A next to Y)
    d, _, net = work
    swap = {i: {"A": "B", "B": "A"}[t.gate] for i, t in enumerate(net.transistors) if t.kind == "n"}
    (d / "schematic_series.spice").write_text(_schematic(net, swap))
    assert eda.netgen_lvs(d, f"{NAME}.spice", NAME, "schematic_series.spice", NAME, "lvs_series")["result"] == "mismatch"


def test_spice_rejects_deleted_pullup(work):
    d, _, _ = work
    sim = d / "sim"
    sim.mkdir(exist_ok=True)
    lines = (d / f"{NAME}.spice").read_text().splitlines()
    gone = next(i for i, l in enumerate(lines) if "pfet" in l and " B " in l)
    (sim / "broken.spice").write_text("\n".join(lines[:gone] + lines[gone + 1:]) + "\n")
    r = simulate.spice(sim, NAME, sim / "broken.spice", ["A", "B"], TT)
    assert r["status"] == "fail" and any("DC row 1" in e for e in r["errors"])


def test_rc_lvs_rejects_a_broken_rc_netlist(work):
    """RC-LVS compares the RC netlist's devices: one wrong connection in it must fail."""
    d = work[0]
    eda.magic(d, eda.extract_script("/w/cell.gds", NAME, rc=True), "extract_rc")
    rc = d / "rc_for_broken.spice"
    text = eda.rc_for_lvs((d / f"{NAME}_rc.spice").read_text())
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("X") and " VGND " in l)
    lines[i] = lines[i].replace(" VGND ", " Y ", 1)
    rc.write_text("\n".join(lines) + "\n")
    r = eda.netgen_lvs(d, rc.name, NAME, "schematic.spice", NAME, "lvs_rc_broken")
    assert r["result"] == "mismatch"


def test_rc_lvs_rejects_a_missing_resistor(work):
    """RC-LVS joins nets through their resistors: with one gone, a device hangs off a stray node."""
    d = work[0]
    eda.magic(d, eda.extract_script("/w/cell.gds", NAME, rc=True), "extract_rc2")
    lines = (d / f"{NAME}_rc.spice").read_text().splitlines()
    node = next(t for l in lines if l.startswith("X") for t in l.split()[1:5] if t.startswith("Y."))
    kept = [l for l in lines if not (l.startswith("R") and node in l.split()[1:3])]   # parallel Rs too: a true open
    assert len(kept) < len(lines)
    (d / "rc_no_r.spice").write_text(eda.rc_for_lvs("\n".join(kept) + "\n"))
    assert eda.netgen_lvs(d, "rc_no_r.spice", NAME, "schematic.spice", NAME, "lvs_rc_no_r")["result"] == "mismatch"


def test_model_rejects_wrong_row(tmp_path):
    good = simulate.verilog_model(NAME, ["A", "B"], TT)
    (tmp_path / "bad.v").write_text(good.replace("4'h7", "4'h5"))      # row 1 wrong
    r = simulate.verilog_check(tmp_path / "bad.v", NAME, ["A", "B"], TT, tmp_path)
    assert r["status"] == "fail" and any(e.startswith("row 1") for e in r["errors"])
    (tmp_path / "good.v").write_text(good)
    assert simulate.verilog_check(tmp_path / "good.v", NAME, ["A", "B"], TT, tmp_path)["status"] == "pass"


def test_abutment_without_tap_fails(work, tmp_path):
    import klayout.db as kdb
    d, cell, _ = work
    files = abut.build(flow.hd_gds(), d / "cell.gds", NAME, cell.width, tmp_path)
    ly = kdb.Layout()
    ly.read(str(files["side"][0]))
    top = ly.top_cell()
    for inst in list(top.each_inst()):
        if inst.cell.name.endswith("tapvpwrvgnd_1"):
            inst.delete()
    ly.write(str(tmp_path / "notap.gds"))
    r = eda.parse_drc(eda.magic(tmp_path, eda.drc_script(["/w/notap.gds"], top.name), "drc_notap")[1])
    assert r["errors"] and "nwell.4" in r["rules"]
    ok = eda.parse_drc(eda.magic(tmp_path, eda.drc_script([f"/w/{files['side'][0].name}"], files["side"][1]), "drc_side")[1])
    assert ok["errors"] == 0 and ok["bbox_um"][2] > 3.5        # the real row: cells present, clean


def test_abutment_catches_what_a_lone_cell_hides(work, tmp_path):
    # NMOS diffusion stretched to 0.02 um from the right edge: alone it only fails the tap rules,
    # but against a mirrored copy of itself the diffusions are 0.04 um apart (difftap.3 is 0.27)
    _, cell, _ = work
    right = max(r.box[2] for r in cell.rects if r.layer == "diff")
    rects = [layout.Rect(r.layer, (r.box[0], r.box[1], cell.width - 0.02, r.box[3]), r.net)
             if r.layer == "diff" and r.box[2] == right and r.box[3] < 1.0 else r for r in cell.rects]
    bad = layout.write_gds(layout.Cell(NAME, cell.width, rects, cell.labels), tmp_path / "edge.gds")
    alone = eda.parse_drc(eda.magic(tmp_path, eda.drc_script(["/w/edge.gds"], NAME), "drc_alone")[1])
    assert set(alone["rules"]) <= flow.TAP_ONLY, alone
    files = abut.build(flow.hd_gds(), bad, NAME, cell.width, tmp_path / "fx")
    fx = eda.parse_drc(eda.magic(tmp_path / "fx", eda.drc_script([f"/w/{files['self'][0].name}"], files["self"][1]), "drc_self")[1])
    assert fx["errors"] and "diff/tap.3" in fx["rules"], fx
