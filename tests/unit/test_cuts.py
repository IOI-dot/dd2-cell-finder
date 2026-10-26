from dd2 import aig, boolfn as bf, cuts
from dd2.paths import ROOT

FX = ROOT / "tests" / "fixtures"


def cutmap(name, k=4):
    return cuts.enumerate_cuts(aig.read_aiger(FX / name), k)


def test_and_gate():
    c = cutmap("and2.aag")
    assert c[3] == [((1, 2), 0b1000), ((3,), 0b10)]
    assert c[1] == [((1,), 0b10)] and c[2] == [((2,), 0b10)]


def test_xor_complemented_edges_and_reconvergence():
    c = dict(cutmap("xor.aag")[5])
    # node 5 = !n3 & !n4 with n3 = a&b, n4 = !a&!b.  Supersets of (1,2) are dominated.
    assert c == {(1, 2): 0b0110, (3, 4): 0b0001, (5,): 0b10}


def test_leaf_limit():
    c = dict(cutmap("and5.aag")[9])        # 5-input AND chain: no 5-leaf cut
    assert all(len(l) <= 4 for l in c)
    # n9 = n8 & e, n8 = n7 & d, n7 = n6 & c, n6 = a & b
    assert c[(3, 4, 5, 6)] == 0x8000 and c[(5, 8)] == 0b1000 and c[(4, 5, 7)] == 0x80
    assert (1, 2, 3, 4, 5) not in c
    assert all(len(l) <= 2 for l, _ in cutmap("and5.aag", k=2)[9])


def test_latch_output_is_a_leaf():
    c = dict(cutmap("latch.aag")[4])        # n4 = n3 & !latch(2); n3 = a & latch
    assert c[(1, 2)] == bf.eval_expr("A & B & !B", ["A", "B"]) == 0


def test_dominated_cuts_removed_and_order_stable():
    c1, c2 = cutmap("and5.aag"), cutmap("and5.aag")
    assert c1 == c2
    for v, cs in c1.items():
        sets = [set(l) for l, _ in cs]
        assert not any(a < b for a in sets for b in sets)
