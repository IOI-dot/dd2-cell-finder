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


def test_area_after_pins_and_skips_reported(tmp_path):
    lib = tmp_path / "x.lib"
    lib.write_text('library (x) {\n'
                   '  cell (c1) { pin (A) { direction : input; } pin (Y) { direction : output; function : "!A"; }\n'
                   '    area : 2.5; }\n'
                   '  cell (c2) { area : 1; pin (A) { direction : input; } pin (Y) { direction : output; } }\n'
                   '}\n')
    skipped = []
    cells = liberty.read_cells(lib, skipped)
    assert [(c.name, c.area) for c in cells] == [("c1", 2.5)]       # finding 12: was area 0.0
    assert skipped == [("c2", "output pin Y has no function")]       # recorded, not silent


def test_missing_area_recorded(tmp_path):
    lib = tmp_path / "y.lib"
    lib.write_text('library (y) { cell (c4) { pin (A) { direction : input; } '
                   'pin (Y) { direction : output; function : "!A"; } } }\n')
    skipped = []
    assert liberty.read_cells(lib, skipped) == [] and skipped == [("c4", "no area")]
