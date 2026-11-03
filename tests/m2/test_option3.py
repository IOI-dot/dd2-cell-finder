"""Option 3: real Option 1 cells replace Option 2's estimated ones in the extended library."""
import json

import pytest

from dd2 import liberty
from dd2m2 import option3

BASE = """library (base) {
  cell ("inv") { area : 3.75; pin ("A") { direction : input; } pin ("Y") { direction : output; function : "!A"; } }
}
"""


def delivered(tmp_path, name, tt="0x8", expr="A&B", status="pass"):
    lib = tmp_path / name / "cell.lib"
    lib.parent.mkdir(parents=True)
    lib.write_text(f'''library ("{name}_lib") {{
    lu_table_template ("dd2_tmpl") {{ variable_1 : "input_net_transition"; index_1("1, 2"); }}
    cell ("{name}") {{
        area : 6.256;
        pin ("A") {{ direction : "input"; capacitance : 0.002; }}
        pin ("B") {{ direction : "input"; capacitance : 0.002; }}
        pin ("Y") {{ direction : "output"; function : "{expr}"; }}
    }}
}}
''')
    req = {"request_id": "M2-001", "name": name, "inputs": ["A", "B"], "output": "Y", "expression": "A&B",
           "truth_table": tt, "sizing": "hd", "estimated_area_um2": 5.0}
    resp = {"request_id": "M2-001", "status": status, "cell": name, "area_um2": 6.256, "files": {"liberty": str(lib)}}
    return req, resp


def test_a_delivered_cell_joins_the_library_with_its_real_area(tmp_path):
    (tmp_path / "base.lib").write_text(BASE)
    req, resp = delivered(tmp_path, "dd2_g4__n2_8_1")
    used = option3.real_library(tmp_path / "base.lib", tmp_path / "out.lib", [(req, resp)])
    cells = {c.name: c for c in liberty.read_cells(tmp_path / "out.lib")}
    assert set(cells) == {"inv", "dd2_g4__n2_8_1"} and cells["dd2_g4__n2_8_1"].area == pytest.approx(6.256)
    assert [r["name"] for r in used] == ["dd2_g4__n2_8_1"]
    assert (tmp_path / "out.lib").read_text().count('lu_table_template ("dd2_tmpl")') == 1


def test_a_failed_cell_never_joins_the_library(tmp_path):
    (tmp_path / "base.lib").write_text(BASE)
    req, resp = delivered(tmp_path, "dd2_g4__n2_8_1", status="fail")
    assert option3.real_library(tmp_path / "base.lib", tmp_path / "out.lib", [(req, resp)]) == []
    assert liberty.cell_names(tmp_path / "out.lib") == {"inv"}


def test_a_liberty_function_that_disagrees_with_the_request_is_refused(tmp_path):
    (tmp_path / "base.lib").write_text(BASE)
    req, resp = delivered(tmp_path, "dd2_g4__n2_8_1", expr="A|B")
    with pytest.raises(ValueError, match="truth table"):
        option3.real_library(tmp_path / "base.lib", tmp_path / "out.lib", [(req, resp)])


def test_the_comparison_keeps_estimated_and_real_area_side_by_side(tmp_path):
    req, resp = delivered(tmp_path, "dd2_g4__n2_8_1")
    row = option3.compare_row(req, resp)
    assert row == {"request_id": "M2-001", "cell": "dd2_g4__n2_8_1", "status": "pass", "estimated_area_um2": 5.0,
                   "real_area_um2": 6.256, "area_error_pct": pytest.approx(25.12), "reason": ""}
    json.dumps(row)
