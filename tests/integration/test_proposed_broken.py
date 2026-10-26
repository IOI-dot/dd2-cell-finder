"""The proposed broken cases must fail their checks (tests/broken_proposed/README.md)."""
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
