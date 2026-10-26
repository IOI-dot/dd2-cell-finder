import pytest

from dd2 import boolfn as bf, liberty, paths
from dd2.paths import ROOT


@pytest.fixture(scope="module")
def full():
    return liberty.read_cells(paths.full_hd_lib())


def test_full_hd_counts(full):
    assert len(full) == 323                       # single-output, combinational, not tri-state
    names = {c.name for c in full}
    assert "sky130_fd_sc_hd__nand2_1" in names
    assert "sky130_fd_sc_hd__dfxtp_1" not in names        # sequential
    assert "sky130_fd_sc_hd__ebufn_1" not in names        # tri-state
    assert "sky130_fd_sc_hd__fa_1" not in names           # two outputs


def test_function_and_area(full):
    c = {c.name: c for c in full}["sky130_fd_sc_hd__a21oi_1"]
    assert c.inputs == ["A1", "A2", "B1"] and c.output == "Y"
    assert c.tt == bf.eval_expr("!((A1 & A2) | B1)", c.inputs)
    assert c.area == pytest.approx(5.0048)


def test_power_down_function_ignored(full):
    assert all("VPWR" not in c.inputs for c in full)


def test_invalid_function_rejected():
    with pytest.raises(ValueError, match="bad_cell_1"):
        liberty.read_cells(ROOT / "tests" / "broken" / "invalid_function.lib")
