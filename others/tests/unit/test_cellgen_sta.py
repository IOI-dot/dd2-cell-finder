"""The design-level steps of Table 5: swap cells in a Liberty copy, parse the timing report."""
from cellgen import sta

LIB = '''library ("x") {
    time_unit : "1ns";
    lu_table_template ("del") { variable_1 : "input_net_transition"; }
    cell ("a") { area : 1; pin ("Y") { function : "1"; } }
    cell ("b") { area : 2; }
}
'''


def test_swap_replaces_only_the_named_cell_and_adds_the_template():
    out = sta.swap_cells(LIB, {"a": '    cell ("a") { area : 9; }\n'}, '    lu_table_template ("t") { }\n')
    assert 'area : 9' in out and 'area : 2' in out and 'function' not in out
    assert out.index('lu_table_template ("t")') < out.index('cell ("a")')


def test_swap_refuses_a_cell_that_is_not_there():
    import pytest
    with pytest.raises(ValueError, match="zz"):
        sta.swap_cells(LIB, {"zz": ""}, "")


def test_worst_slack_is_read_from_the_marker():
    assert sta.parse_slack("noise\nWS 7.25\n") == 7.25
    assert sta.parse_slack("no marker") is None
