import pytest

pytest.importorskip("klayout", reason="Option 1 needs KLayout/GDSfactory (make setup installs them)")

from cellgen import euler, flow, layout, network
from dd2 import boolfn as bf


def test_installed_sizes_parse_both_spice_forms():
    # the PDK netlist writes w=650000u and w=1e+06u; both are micrometres x 1e6
    assert flow.installed_sizes("inv_1") == {"n": [0.65], "p": [1.0]}
    assert flow.installed_sizes("nand2_1") == {"n": [0.65], "p": [1.0]}


def test_layout_refuses_a_width_that_needs_folding():
    net = network.single_stage(bf.eval_expr("!A", "A"), ["A"])
    with pytest.raises(ValueError, match="fold"):
        layout.build(net, euler.order(net), "x", wp=1e6)
