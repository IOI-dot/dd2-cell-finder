from dd2 import paths


def test_layout():
    assert (paths.ROOT / "pyproject.toml").exists()
    assert paths.FULL_HD_LIB.endswith("sky130_fd_sc_hd__tt_025C_1v80.lib")
    assert paths.full_hd_lib(paths.ROOT / "pdk").name == "sky130_fd_sc_hd__tt_025C_1v80.lib"
    assert paths.results("m1").is_relative_to(paths.ROOT)
