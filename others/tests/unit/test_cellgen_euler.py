"""Gate ordering: one gate sequence shared by both diffusion rows (paired Euler path)."""
import pytest

from cellgen import euler, network
from dd2 import boolfn as bf


def order(expr, inputs):
    inputs = list(inputs)
    return euler.order(network.single_stage(bf.eval_expr(expr, inputs), inputs))


def test_inverter():
    o = order("!A", "A")
    assert o.gates == ["A"] and o.rows["n"] == [["VGND", "Y"]] and o.rows["p"] == [["VPWR", "Y"]]
    assert o.breaks == 0


def test_nand2_matches_hd_order():
    # HD nand2_1: B on the left, A on the right; NMOS VGND-B-x-A-Y, PMOS VPWR-B-Y-A-VPWR.
    o = order("!(A&B)", "AB")
    assert o.gates == ["B", "A"] and o.breaks == 0
    assert o.rows["n"] == [["VGND", "n1", "Y"]] and o.rows["p"] == [["VPWR", "Y", "VPWR"]]


@pytest.mark.parametrize("expr, inputs", [
    ("!(A|B)", "AB"), ("!(A&B&C)", "ABC"), ("!(A|B|C)", "ABC"),
    ("!((A1&A2)|B1)", ["A1", "A2", "B1"]), ("!((A1|A2)&B1)", ["A1", "A2", "B1"]),
    ("!((A1&A2)|(B1&B2))", ["A1", "A2", "B1", "B2"]), ("!((C&D)|(A&B&(C|D)))", "ABCD"),
])
def test_every_column_is_consistent(expr, inputs):
    net = network.single_stage(bf.eval_expr(expr, list(inputs)), list(inputs))
    o = euler.order(net)
    assert euler.validate(net, o) == []
    assert o.breaks == 0                     # these all have a common Euler path


def test_validate_catches_a_wrong_order():
    net = network.single_stage(bf.eval_expr("!(A&B)", "AB"), ["A", "B"])
    o = euler.order(net)
    bad = euler.Ordering(o.gates, {"n": [["VGND", "Y", "n1"]], "p": o.rows["p"]}, 0)
    assert euler.validate(net, bad)
