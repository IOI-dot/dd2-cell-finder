"""Layer check (Option 1 handout 3.2): implants and npc as drawn, which Magic does not check."""
import pytest

pytest.importorskip("klayout", reason="Option 1 needs KLayout/GDSfactory (make setup installs them)")

from cellgen import euler, layers, layout, network
from dd2 import boolfn as bf, paths

HD_GDS = paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"


@pytest.fixture(scope="module")
def nand2_gds(tmp_path_factory):
    net = network.single_stage(bf.eval_expr("!(A&B)", "AB"), ["A", "B"])
    cell = layout.generate(net, euler.order(net), "t_nand2")
    return layout.write_gds(cell, tmp_path_factory.mktemp("g") / "t.gds"), cell


def test_generated_cell_passes(nand2_gds):
    assert layers.check(nand2_gds[0], "t_nand2") == []


def test_installed_nand2_passes():
    assert layers.check(HD_GDS, "sky130_fd_sc_hd__nand2_1") == []


def test_missing_hvtp_is_caught(nand2_gds, tmp_path):
    cell = nand2_gds[1]
    broken = layout.Cell(cell.name, cell.width, [r for r in cell.rects if r.layer != "hvtp"], cell.labels)
    gds = layout.write_gds(broken, tmp_path / "b.gds")
    errs = layers.check(gds, "t_nand2")
    assert any("hvtp" in e for e in errs)


def test_missing_npc_is_caught(nand2_gds, tmp_path):
    cell = nand2_gds[1]
    broken = layout.Cell(cell.name, cell.width, [r for r in cell.rects if r.layer != "npc"], cell.labels)
    assert any("npc" in e for e in layers.check(layout.write_gds(broken, tmp_path / "c.gds"), "t_nand2"))
