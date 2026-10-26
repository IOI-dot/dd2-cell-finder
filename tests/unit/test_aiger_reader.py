import pytest

from dd2 import aig
from dd2.paths import ROOT

FX = ROOT / "tests" / "fixtures"


def sim(g, a, b):
    val = {0: 0, 1: a, 2: b}
    for lhs, r0, r1 in g.ands:
        val[lhs >> 1] = (val[r0 >> 1] ^ (r0 & 1)) & (val[r1 >> 1] ^ (r1 & 1))
    o = g.outputs[0]
    return val[o >> 1] ^ (o & 1)


@pytest.mark.parametrize("name", ["xor.aag", "xor.aig"])
def test_ascii_and_binary_agree(name):
    g = aig.read_aiger(FX / name)
    assert (g.M, g.I, g.L, g.O, g.A) == (5, 2, 0, 1, 3)
    assert g.ands == [(6, 4, 2), (8, 5, 3), (10, 9, 7)] or g.ands == [(6, 2, 4), (8, 3, 5), (10, 7, 9)]
    assert [sim(g, a, b) for a in (0, 1) for b in (0, 1)] == [0, 1, 1, 0]


def test_malformed_header_raises():
    with pytest.raises(ValueError):
        aig.read_aiger(FX / "bad_header.aag")


def test_bad_state_lines_are_outputs():
    # ABC writes primary outputs as B (bad-state) lines; they must not be lost.
    g = aig.read_aiger(FX / "xor_bad_output.aag")
    assert (g.O, g.B) == (0, 1) and g.bad == [10] and g.all_outputs() == [10]
    assert aig.header(FX / "xor_bad_output.aag") == {"M": 5, "I": 2, "L": 0, "O": 0, "A": 3, "B": 1, "C": 0}


def test_and_gates_must_be_topological():
    with pytest.raises(ValueError, match="topological"):
        aig.read_aiger(FX / "unordered.aag")
