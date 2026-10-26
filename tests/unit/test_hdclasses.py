from dd2 import hdclasses, paths


def test_rows(tmp_path):
    rows, classes = hdclasses.build(paths.full_hd_lib(), paths.given() / "hd_reduced.lib")
    by = {r["name"]: r for r in rows}
    assert len(rows) == 323
    inv, nand2 = by["sky130_fd_sc_hd__inv_1"], by["sky130_fd_sc_hd__nand2_1"]
    assert inv["tt"] == "0x1" and inv["arity"] == 1 and inv["in_reduced"]
    assert nand2["tt"] == "0x7" and nand2["pn_class"] == by["sky130_fd_sc_hd__and2_1"]["pn_class"]
    assert by["sky130_fd_sc_hd__a2111oi_0"]["in_reduced"] is False
    assert sum(c["members"] for c in classes) == 323
