import json

from dd2 import aig, cutcheck
from dd2.paths import ROOT

FX = ROOT / "tests" / "fixtures"


def test_correct_and_wrong_tables():
    g = aig.read_aiger(FX / "xor.aag")
    assert cutcheck.check(g, 5, (1, 2), 0b0110)
    assert not cutcheck.check(g, 5, (1, 2), 0b0111)     # one flipped bit
    assert cutcheck.check(g, 5, (3, 4), 0b0001)
    assert not cutcheck.check(g, 5, (3,), 0b01)          # leaves do not cut the cone


def test_independent_of_enumerator():
    src = (ROOT / "src" / "dd2" / "cutcheck.py").read_text()
    assert "import cuts" not in src and "from .cuts" not in src and "from . import cuts" not in src


def test_broken_case_wrong_truth_table_is_rejected():
    case = json.loads((ROOT / "tests" / "broken" / "wrong_truth_table.json").read_text())
    g = aig.read_aiger(ROOT / case["aig"])
    tt = int(case["tt"], 16)
    assert not cutcheck.check(g, case["root"], tuple(case["leaves"]), tt)
    # The cut itself is real: only the flipped bit is wrong.
    assert cutcheck.check(g, case["root"], tuple(case["leaves"]), tt ^ (1 << case["flipped_bit"]))
