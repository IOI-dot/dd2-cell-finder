"""The characterizer's setup, ramp, arcs and Liberty text (handout section 5). No simulator needed."""
import math

import pytest

from cellgen import characterize as ch
from dd2 import boolfn as bf


@pytest.fixture(scope="module")
def setup():
    return ch.read_setup()


def test_setup_comes_from_the_liberty_file(setup):
    assert setup["voltage"] == 1.8 and setup["temperature"] == 25.0
    assert (setup["slew_lower"], setup["slew_upper"]) == (20.0, 80.0)
    assert setup["input_threshold"] == 50.0 and setup["output_threshold"] == 50.0
    assert setup["side_rule"] == "slowest"          # no timing group in the HD cells has a when


def test_hd_tables_parse_with_their_own_index_values():
    cell = ch.read_cell("nand2_1")
    arcs = {(a["pin"], a["table"]) for a in cell["tables"]}
    assert ("A", "cell_rise") in arcs and ("B", "fall_transition") in arcs
    t = next(a for a in cell["tables"] if a["pin"] == "A" and a["table"] == "cell_rise")
    assert len(t["index_1"]) == 7 and len(t["index_2"]) == 7 and len(t["values"]) == 7
    assert math.isclose(cell["capacitance"]["A"], 0.002315)


def test_the_ramp_is_the_slew_over_the_threshold_span(setup):
    assert ch.full_ramp(0.06, setup) == pytest.approx(0.1)
    # the Table 5 broken case: the index read as the whole ramp
    assert ch.full_ramp(0.06, setup, broken_full_ramp=True) == 0.06


def test_arcs_of_a_nand_are_negative_unate():
    tt = bf.eval_expr("!(A&B)", "AB")
    arcs = ch.arcs(["A", "B"], tt)
    assert {(a["pin"], a["sense"]) for a in arcs} == {("A", "negative_unate"), ("B", "negative_unate")}
    a = next(x for x in arcs if x["pin"] == "A" and x["out_edge"] == "rise")
    assert a["in_edge"] == "fall" and a["sides"] == [2]      # B must be 1


def test_an_aoi22_input_has_three_side_settings():
    tt = bf.eval_expr("!((A&B)|(C&D))", "ABCD")
    a = next(x for x in ch.arcs(list("ABCD"), tt) if x["pin"] == "A" and x["out_edge"] == "fall")
    assert len(a["sides"]) == 3


def test_an_xor_arc_is_non_unate_with_both_senses_measured():
    tt = bf.eval_expr("A^B", "AB")
    arcs = [a for a in ch.arcs(["A", "B"], tt) if a["pin"] == "A"]
    assert {(a["in_edge"], a["out_edge"]) for a in arcs} == {("rise", "rise"), ("fall", "fall"), ("rise", "fall"), ("fall", "rise")}
    assert {a["sense"] for a in arcs} == {"positive_unate", "negative_unate"}


def test_compare_finds_median_and_worst():
    hd = [{"pin": "A", "table": "cell_rise", "index_1": [1, 2], "index_2": [3, 4], "values": [[1.0, 2.0], [4.0, 8.0]]}]
    ours = [{"pin": "A", "table": "cell_rise", "values": [[1.0, 2.0], [4.0, 16.0]]}]
    c = ch.compare_tables(ours, hd)
    assert c["entries"] == 4 and c["median_abs_pct"] == 0.0 and c["max_abs_pct"] == 100.0
    assert c["worst"]["slew_ns"] == 2 and c["worst"]["load_pf"] == 4


def test_liberty_function_gives_the_truth_table():
    tt = bf.eval_expr("(A&!C)|(B&C)", "ABC")
    assert bf.eval_expr(ch.function_text(tt, list("ABC")).replace(" ", ""), list("ABC")) == tt


def test_liberty_holds_one_cell_with_hd_units(setup):
    table = {"pin": "A", "table": "cell_rise", "sense": "negative_unate", "index_1": [0.01, 0.02],
             "index_2": [0.001, 0.002], "values": [[0.1, 0.2], [0.3, 0.4]]}
    text = ch.liberty_text("c", ["A"], "Y", bf.eval_expr("!A", ["A"]), 3.75, {"A": 0.002}, [table], setup,
                           {"version": "ngspice-47", "sha256": "ab" * 32})
    assert text.count("cell (") == 1 and 'time_unit : "1ns"' in text and "capacitive_load_unit" in text
    assert "ngspice-47" in text and "ab" * 32 in text and 'function : "' in text
