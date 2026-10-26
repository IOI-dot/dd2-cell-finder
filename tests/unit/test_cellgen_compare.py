"""Section 4.1 "must match" rows: frame, pins and wiring layers, each with a broken case."""
import copy

import pytest

pytest.importorskip("klayout", reason="Option 1 needs KLayout/GDSfactory (make setup installs them)")

from cellgen import compare, euler, layout, network  # noqa: E402
from dd2 import boolfn as bf, paths  # noqa: E402

HD = paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"
FRAME = layout.load_frame()["frame"]


@pytest.fixture(scope="module")
def nand2(tmp_path_factory):
    net = network.single_stage(bf.eval_expr("!(A&B)", "AB"), ["A", "B"])
    cell = layout.generate(net, euler.order(net), "c_nand2")
    gds = layout.write_gds(cell, tmp_path_factory.mktemp("c") / "c.gds")
    return cell, gds


def write(cell, rects, tmp_path, name="m.gds"):
    return layout.write_gds(layout.Cell(cell.name, cell.width, rects, cell.labels), tmp_path / name)


@pytest.mark.parametrize("hd", ["inv_1", "nand2_1"])
def test_frame_check_installed(hd):
    rows = compare.frame_check(compare.Gds(HD, f"sky130_fd_sc_hd__{hd}"), FRAME)
    assert all(r["match"] for r in rows), [r for r in rows if not r["match"]]
    assert any(r["layer"] == "nwell x" for r in rows) and any(r["layer"].startswith("li1") for r in rows)


def test_frame_check_catches_a_moved_band():
    plan = copy.deepcopy(FRAME)
    plan["nwell"]["y"] = [1.30, 2.91]
    rows = compare.frame_check(compare.Gds(HD, "sky130_fd_sc_hd__inv_1"), plan)
    assert not next(r for r in rows if r["layer"] == "nwell")["match"]


def test_frame_xor_generated_vs_installed(nand2, tmp_path):
    cell, gds = nand2
    inst = compare.Gds(HD, "sky130_fd_sc_hd__nand2_1")
    x = compare.frame_xor(compare.Gds(gds, cell.name), inst)
    assert x["identical"] and "met1" in x and "li1_rails" in x
    shrunk = [layout.Rect(r.layer, (r.box[0], r.box[1] + 0.1, r.box[2], r.box[3]), r.net) if r.layer == "hvtp" else r
              for r in cell.rects]
    assert not compare.frame_xor(compare.Gds(write(cell, shrunk, tmp_path), cell.name), inst)["identical"]


def test_wiring_layers_catch_met1_inside(nand2, tmp_path):
    cell, gds = nand2
    assert compare.wiring_layers(compare.Gds(gds, cell.name))["ok"]
    extra = cell.rects + [layout.Rect("met1", (0.5, 1.0, 0.8, 1.3), "Y")]
    assert not compare.wiring_layers(compare.Gds(write(cell, extra, tmp_path), cell.name))["ok"]


@pytest.mark.parametrize("hd", ["inv_1", "nand2_1"])
def test_pin_check_installed(hd):
    inputs = {"inv_1": ["A"], "nand2_1": ["A", "B"]}[hd]
    assert compare.pin_check(compare.Gds(HD, f"sky130_fd_sc_hd__{hd}"), inputs) == []


def test_pin_check_generated_and_broken(nand2, tmp_path):
    cell, gds = nand2
    assert compare.pin_check(compare.Gds(gds, cell.name), ["A", "B"]) == []
    # input A's label moved out of the npc band, and VPB's label dropped
    labels = [(l, t, x, (0.5 if t == "A" else y)) for l, t, x, y in cell.labels if t != "VPB"]
    bad = layout.write_gds(layout.Cell(cell.name, cell.width, cell.rects, labels), tmp_path / "p.gds")
    errs = compare.pin_check(compare.Gds(bad, cell.name), ["A", "B"])
    assert any(e.startswith("A:") and "npc band" in e for e in errs) and any("VPB" in e for e in errs)


@pytest.mark.parametrize("hd, inputs", [("a21oi_1", ["A1", "A2", "B1"]), ("nand3_1", ["A", "B", "C"]),
                                        ("o21ai_1", ["A1", "A2", "B1"]), ("a22oi_1", ["A1", "A2", "B1", "B2"])])
def test_pin_check_accepts_cells_with_several_labels_per_pin(hd, inputs):
    assert compare.pin_check(compare.Gds(HD, f"sky130_fd_sc_hd__{hd}"), inputs) == []


def test_pin_check_requires_a_pin_shape_under_every_label(nand2, tmp_path):
    cell, _ = nand2
    ys = [(x, y) for l, t, x, y in cell.labels if t == "Y"]
    x0, y0 = ys[0]
    rects = [r for r in cell.rects if not (r.layer == "li1.pin" and r.box[0] <= x0 <= r.box[2] and r.box[1] <= y0 <= r.box[3])]
    bad = write(cell, rects, tmp_path, "y.gds")
    assert any("Y" in e and "pin shape" in e for e in compare.pin_check(compare.Gds(bad, cell.name), ["A", "B"]))


@pytest.mark.parametrize("what", ["met1 short", "li1 gap"])
def test_frame_check_requires_full_width_rails(nand2, tmp_path, what):
    cell, _ = nand2
    rects = []
    for r in cell.rects:
        if what == "met1 short" and r.layer == "met1" and r.net == "VPWR" and r.box[2] - r.box[0] > 1:
            r = layout.Rect("met1", (r.box[0], r.box[1], 1.0, r.box[3]), r.net)
        if what == "li1 gap" and r.layer == "li1" and r.net == "VGND" and r.box[1] < 0 and r.box[2] - r.box[0] > 1:
            rects.append(layout.Rect("li1", (r.box[0], r.box[1], 0.6, r.box[3]), r.net))
            r = layout.Rect("li1", (0.9, r.box[1], r.box[2], r.box[3]), r.net)
        rects.append(r)
    rows = compare.frame_check(compare.Gds(write(cell, rects, tmp_path, "r.gds"), cell.name), FRAME)
    assert not all(r["match"] for r in rows), what
