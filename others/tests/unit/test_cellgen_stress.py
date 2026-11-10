"""SA and SB, measured from geometry and written on every extracted device (handout section 5)."""
import pytest

pytest.importorskip("klayout", reason="Option 1 needs KLayout")
from cellgen import stress
from dd2 import paths

HD_GDS = paths.ROOT / "pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"


def test_inv_1_is_0_26_on_both_sides():
    m = stress.measure(HD_GDS, "sky130_fd_sc_hd__inv_1")
    assert len(m) == 2 and all(v == (0.26, 0.26) for v in m.values())


def test_series_gates_measure_through_the_neighbour():
    m = stress.measure(HD_GDS, "sky130_fd_sc_hd__nand2_1")
    # diffusion 0.155 to 1.245, gates at 0.415 and 0.835
    assert m[(0.415, "n")] == (0.26, 0.68) and m[(0.835, "n")] == (0.68, 0.26)


def test_annotate_writes_sa_sb_on_every_device(tmp_path):
    ext = tmp_path / "c.ext"
    ext.write_text('device msubckt sky130_fd_pr__nfet_01v8 83 47 84 48 l=30 w=130 "VNB" "B" 60 0 "VGND" 130 1,1 "n" 130 1,1\n'
                   'device msubckt sky130_fd_pr__nfet_01v8 167 47 168 48 l=30 w=130 "VNB" "A" 60 0 "n" 130 1,1 "Y" 130 1,1\n')
    spice = tmp_path / "c.spice"
    spice.write_text(".subckt c A B Y VGND VNB\nX0 Y A n VNB sky130_fd_pr__nfet_01v8 w=0.65 l=0.15\n"
                     "X1 n B VGND VNB sky130_fd_pr__nfet_01v8 w=0.65 l=0.15\n.ends\n")
    out = tmp_path / "o.spice"
    stress.annotate(spice, out, HD_GDS, "sky130_fd_sc_hd__nand2_1", ext=ext)
    lines = out.read_text().splitlines()
    assert lines[1].endswith("sa=0.68 sb=0.26") and lines[2].endswith("sa=0.26 sb=0.68")


def test_a_device_without_geometry_is_an_error(tmp_path):
    ext = tmp_path / "c.ext"
    ext.write_text("")
    spice = tmp_path / "c.spice"
    spice.write_text(".subckt c A Y\nX0 Y A n VNB sky130_fd_pr__nfet_01v8 w=0.65 l=0.15\n.ends\n")
    with pytest.raises(ValueError, match="no device"):
        stress.annotate(spice, tmp_path / "o.spice", HD_GDS, "sky130_fd_sc_hd__nand2_1", ext=ext)


def test_extresist_capacitance_counts_once():
    from cellgen import eda
    text = ".subckt c A VNB\nC1 A VNB 0.15f\nC2 A.n0 VNB 0.06f\nC3 A.t0 VNB 0.03f\nC4 A Y 0.02f\nC5 A.n1 Y 0.01f\n.ends\n"
    out = eda.count_caps_once(text)
    c = dict(l.split()[0:1] + [float(l.split()[3][:-1])] for l in out.splitlines() if l.startswith("C"))
    assert abs(c["C1"] - 0.06) < 1e-9 and c["C2"] == 0.06 and c["C3"] == 0.03
    assert c["C4"] == 0.02                       # a coupling cap is not a substrate cap
    assert abs(sum(v for k, v in c.items() if k in ("C1", "C2", "C3")) - 0.15) < 1e-9
