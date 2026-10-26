"""Broken cases proposed for tests/broken/: a Liberty file Yosys must reject (handout 9.1) and a
restructured AIG ABC cec must reject. They are exercised here until a group member moves them."""
import subprocess

from dd2 import aig
from dd2.paths import ROOT

P = ROOT / "tests" / "broken_proposed"


def test_yosys_rejects_liberty():
    p = subprocess.run(["yosys", "-q", "-p", f"read_liberty -lib {P / 'yosys_rejects.lib'}"],
                       capture_output=True, text=True)
    assert p.returncode != 0


def test_cec_rejects_nonequivalent_aig(tmp_path):
    assert not aig.cec(ROOT / "tests/broken/wrong_truth_table.aig", P / "nonequivalent_restructured.aig",
                       tmp_path / "cec.log")
    assert aig.cec(ROOT / "tests/broken/wrong_truth_table.aig", ROOT / "tests/broken/wrong_truth_table.aig",
                   tmp_path / "same.log")


def test_deleted_pullup_netlist_fails_simulation():
    import shutil
    from cellgen import simulate
    from dd2 import paths
    pytest = __import__("pytest")
    if not shutil.which("docker") or subprocess.run(["docker", "image", "inspect", "dd2-layout-tools"],
                                                    capture_output=True).returncode:
        pytest.skip("Docker or the course image is not available here")
    d = paths.build("test_o1", "proposed_pullup")
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    shutil.copy(P / "nand2_pullup_deleted.spice", d / "broken.spice")
    r = simulate.spice(d, "dd2_ref__nand2_1", d / "broken.spice", ["A", "B"], 0x7)
    assert r["status"] == "fail" and any("DC row 1" in e for e in r["errors"])


def test_wrong_row_model_fails_model_check(tmp_path):
    from cellgen import simulate
    r = simulate.verilog_check(P / "nand2_model_wrong_row.v", "dd2_ref__nand2_1", ["A", "B"], 0x7, tmp_path)
    assert r["status"] == "fail" and r["errors"][0].startswith("row 1")
