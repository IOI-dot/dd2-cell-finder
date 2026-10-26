"""Option 1 front end: request reader, single-stage CMOS networks and the switch-level check."""
import json

import pytest

from cellgen import network, request
from dd2 import boolfn as bf
from dd2.paths import ROOT


def test_request_reader_accepts_appendix_a_example():
    req = request.read(ROOT / "docs" / "interface" / "request_example.json")
    assert req.inputs == ["A", "B", "C", "D"] and req.tt == 0x077F and req.status == "ok"


def test_request_reader_refuses_mismatch_and_too_many_inputs(tmp_path):
    ex = json.loads((ROOT / "docs" / "interface" / "request_example.json").read_text())
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(ex | {"truth_table": "0x077E"}))
    r = request.read(bad)
    assert r.status == "fail" and "does not match" in r.reason
    five = tmp_path / "five.json"
    five.write_text(json.dumps(ex | {"inputs": list("ABCDE"), "expression": "A&B&C&D&E",
                                     "truth_table": "0x80000000"}))
    r = request.read(five)
    assert r.status == "unsupported" and "4 inputs" in r.reason


@pytest.mark.parametrize("expr, inputs, n_t", [
    ("!A", "A", 2), ("!(A&B)", "AB", 4), ("!(A|B)", "AB", 4), ("!(A&B&C)", "ABC", 6),
    ("!((A1&A2)|B1)", ["A1", "A2", "B1"], 6), ("!((A1|A2)&B1)", ["A1", "A2", "B1"], 6),
    ("!((C&D)|(A&B&(C|D)))", "ABCD", 12),
])
def test_single_stage_networks_pass_switch_check(expr, inputs, n_t):
    inputs = list(inputs)
    tt = bf.eval_expr(expr, inputs)
    net = network.single_stage(tt, inputs)
    assert len(net.transistors) == n_t
    assert network.max_series(net) <= 3
    assert network.switch_check(net, tt) == []


def test_nand2_series_order_matches_hd():
    # HD nand2_1: A's NMOS touches Y, B's NMOS touches VGND (installed SPICE netlist).
    net = network.single_stage(bf.eval_expr("!(A&B)", "AB"), ["A", "B"])
    n = {t.gate: t for t in net.transistors if t.kind == "n"}
    assert "Y" in (n["A"].drain, n["A"].source) and "VGND" in (n["B"].drain, n["B"].source)


def test_not_single_stage_is_refused():
    with pytest.raises(ValueError, match="negative unate"):
        network.single_stage(bf.eval_expr("A&B", "AB"), ["A", "B"])


def test_switch_check_catches_deleted_pullup_and_short():
    tt = bf.eval_expr("!(A&B)", "AB")
    net = network.single_stage(tt, ["A", "B"])
    broken = network.Network(net.inputs, [t for t in net.transistors if not (t.kind == "p" and t.gate == "B")])
    errs = network.switch_check(broken, tt)
    assert errs and any("floating" in e for e in errs)          # A=1, B=0: nothing pulls Y up
    shorted = network.Network(net.inputs, net.transistors + [network.Transistor("p", "A", "Y", "VGND")])
    assert any("short" in e for e in network.switch_check(shorted, tt))


def test_output_list_is_unsupported_with_a_clear_reason(tmp_path):
    ex = json.loads((ROOT / "docs" / "interface" / "request_example.json").read_text())
    r = request.parse(ex | {"output": ["Y", "Z"]})
    assert r.status == "unsupported" and "one output" in r.reason and "4 inputs" not in r.reason


def test_hd_table_point_comes_from_the_delay_table():
    from cellgen import simulate
    p = simulate.hd_table_point()
    assert p["table"] == "cell_rise" and p["variable_1"] == "input_net_transition"
    assert p["slew_ns"] == 0.122474 and p["load_pf"] == 0.00952062


def test_invalid_request_still_gets_a_response(tmp_path):
    pytest.importorskip("klayout", reason="Option 1 needs KLayout/GDSfactory")
    from cellgen import cli
    ex = json.loads((ROOT / "docs" / "interface" / "request_example.json").read_text())
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(ex | {"inputs": list("ABCDE"), "expression": "A&B&C&D&E", "truth_table": "0x80000000"}))
    assert cli.main(["request", str(bad), "--out", str(tmp_path / "cells"), "--work", str(tmp_path / "w")]) == 2
    resp = json.loads((tmp_path / "cells" / ex["name"] / "response.json").read_text())
    assert resp["status"] == "unsupported" and resp["request_id"] == ex["request_id"] and resp["reason"]
