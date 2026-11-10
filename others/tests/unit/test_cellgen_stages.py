"""Option 1 step 2 and 3: multi-stage decomposition, sizing, and the installed series order."""
import itertools

import pytest

from cellgen import euler, network
from dd2 import boolfn as bf


def chk(expr, inputs, max_t=None, stages=None):
    inputs = list(inputs)
    tt = bf.eval_expr(expr, inputs)
    net = network.synthesize(tt, inputs)
    assert network.switch_check(net, tt) == []
    assert network.max_series(net) <= 3
    if max_t is not None:
        assert len(net.transistors) <= max_t, [s.out for s in net.stages]
    if stages is not None:
        assert len(net.stages) == stages
    return net


@pytest.mark.parametrize("expr, inputs, max_t, stages", [
    ("!(A&B)", "AB", 4, 1),
    ("A&B", "AB", 6, 2),                         # and2: nand2 + inverter
    ("(A&B)|C", "ABC", 8, 2),                    # a21o
    ("(A&!C)|(B&C)", "ABC", 12, 3),              # mux2, as HD
    ("A^B", "AB", 10, 2),                        # xor2, as HD: nor2 + a21oi
    ("!(A^B)", "AB", 10, 2),
    ("(A&B)|(C&(A|B))", "ABC", 12, 2),           # maj3
    ("(C&D)|(A&B&(C|D))", "ABCD", 14, 2),
])
def test_table6_decompositions(expr, inputs, max_t, stages):
    chk(expr, inputs, max_t, stages)


@pytest.mark.parametrize("expr, inputs", [
    ("A&B&C&D", "ABCD"), ("A|B|C|D", "ABCD"), ("!(A&B&C&D)", "ABCD"), ("!(A|B|C|D)", "ABCD"),
    ("A^B^C", "ABC"), ("A^B^C^D", "ABCD"), ("(A&B)^(C&D)", "ABCD"), ("(A|!B)&(C^D)", "ABCD"),
    ("!A", "A"), ("A", "A"), ("A&!A", "A"), ("A|!A", "A"),
])
def test_hard_functions_still_get_a_network(expr, inputs):
    inputs = list(inputs)
    tt = bf.eval_expr(expr, inputs)
    if tt in (0, (1 << (1 << len(inputs))) - 1) or expr == "A":
        with pytest.raises(ValueError):
            network.synthesize(tt, inputs)
        return
    chk(expr, inputs)


def test_decomposition_stage_order_is_topological():
    net = chk("(A&!C)|(B&C)", "ABC")
    seen = set(net.inputs)
    for s in net.stages:
        assert set(s.leaves) <= seen
        seen.add(s.out)
    assert net.stages[-1].out == "Y"


def test_series_variants_reach_the_installed_order():
    # HD a21oi_1: PUN has B1 next to Y; PDN has A1 next to Y (installed SPICE netlist)
    inst = [("n", "A2", "a_199_47#", "VGND"), ("p", "A1", "a_113_297#", "VPWR"), ("p", "B1", "Y", "a_113_297#"),
            ("n", "B1", "VGND", "Y"), ("p", "A2", "VPWR", "a_113_297#"), ("n", "A1", "Y", "a_199_47#")]
    inst = [network.Transistor(*t, w=0.65 if t[0] == "n" else 1.0) for t in inst]
    tt = bf.eval_expr("!((A1&A2)|B1)", ["A1", "A2", "B1"])
    net = network.match_installed(tt, ["A1", "A2", "B1"], inst)
    assert network.same_topology(net.transistors, inst)
    assert {t.w for t in net.transistors if t.kind == "p"} == {1.0}


def test_stack_sizing_folds_into_fingers_and_keeps_inner_stages_x1():
    nor3 = network.synthesize(bf.eval_expr("!(A|B|C)", "ABC"), list("ABC"))
    sized = network.size(nor3, "stack")
    p = [t for t in sized.transistors if t.kind == "p"]
    n = [t for t in sized.transistors if t.kind == "n"]
    assert len(n) == 3 and len(p) == 9 and all(abs(t.w - 1.0) < 1e-9 for t in p)
    assert network.switch_check(sized, bf.eval_expr("!(A|B|C)", "ABC")) == []
    a21o = network.size(network.synthesize(bf.eval_expr("(A&B)|C", "ABC"), list("ABC")), "stack")
    out_stage = [t for t in a21o.transistors if t.stage == len(a21o.stages) - 1]
    assert len(out_stage) == 2                    # the inverter stays x1


def test_parallel_fingers_count_once_in_series_depth():
    net = network.size(network.synthesize(bf.eval_expr("!(A|B|C)", "ABC"), list("ABC")), "stack")
    assert network.max_series(net) == 3


def test_a_contact_that_is_not_square_stops_the_layout():
    from cellgen import layout
    c = layout.Cell("x", 1.0)
    c.add("licon", (0, 0, 0.165, 0.17), "A")
    assert layout._li_clashes(c)


def test_hd_sizing_is_one_finger_each():
    net = network.size(network.synthesize(bf.eval_expr("!(A&B)", "AB"), ["A", "B"]), "hd")
    assert sorted(t.w for t in net.transistors) == [0.65, 0.65, 1.0, 1.0]


def test_every_npn_class_of_three_inputs_synthesizes():
    # exhaustive for 3 inputs: every non-constant function that depends on all its inputs
    names = list("ABC")
    for tt in range(1, 255):
        if len(bf.depends_on(tt, 3)) != 3:
            continue
        assert network.switch_check(network.synthesize(tt, names), tt) == [], hex(tt)




def test_folded_nor3_has_no_diffusion_break():
    tt = bf.eval_expr("!(A|B|C)", "ABC")
    net = network.size(network.synthesize(tt, list("ABC")), "stack")
    o = euler.candidates(net)[0]
    assert euler.validate(net, o) == []
    assert sum(1 for g in o.gates) == 9
    assert o.row_breaks["p"] == 0                 # VPWR A p A VPWR A p B p2 ... : an Euler path exists


def test_multistage_orders_concatenate_and_share_rails():
    tt = bf.eval_expr("A&B", "AB")
    net = network.size(network.synthesize(tt, list("AB")), "hd")
    o = euler.candidates(net)[0]
    assert euler.validate(net, o) == []
    assert len(o.gates) == 3 and o.breaks == 0     # nand2 mirrored so that its rails meet the inverter's


def test_a21o_needs_one_break_where_its_pmos_ends_are_not_rails():
    # PMOS of a21oi: the middle net has odd degree, so an Euler path must end there, not at VPWR
    tt = bf.eval_expr("(A&B)|C", "ABC")
    net = network.size(network.synthesize(tt, list("ABC")), "hd")
    o = euler.candidates(net)[0]
    assert euler.validate(net, o) == [] and len(o.gates) == 4 and o.breaks == 1


def test_no_euler_path_reports_breaks():
    # a function with no common Euler path keeps every transistor and counts its breaks
    tt = bf.eval_expr("!((A&B)|(C&D))", "ABCD")
    net = network.size(network.synthesize(tt, list("ABCD")), "hd")
    for o in euler.candidates(net):
        assert euler.validate(net, o) == []
    assert isinstance(euler.candidates(net)[0].breaks, int)
    assert list(itertools.islice(euler.candidates(net), 1))
