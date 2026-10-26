import json

from dd2 import designs, mapping, paths


def test_cpu8_reduced_A(tmp_path):
    r = mapping.run_mapping(designs.get("cpu8"), "reduced", "A", tmp_path, paths.given())
    assert r["run"]["status"] == "pass" and r["area_um2"] > 1000 and r["cells"] > 100
    assert json.loads((tmp_path / "cpu8/reduced/A/result.json").read_text())["area_um2"] == r["area_um2"]
    assert r["run"]["inputs"] and r["run"]["tools"]["yosys"]


def test_table1_rejects_incomplete_matrix(tmp_path):
    try:
        mapping.write_table1([], tmp_path / "t.csv", ["cpu8"])
    except ValueError as e:
        assert "missing" in str(e)
    else:
        raise AssertionError("incomplete Table 1 accepted")
