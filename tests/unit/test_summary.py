from dd2 import mapping, summary


def row(dev_um2, hd=4186.5):
    return {"reduced_um2": f"{hd + dev_um2:.4f}", "handout_reduced_um2": str(hd),
            "usable_um2": f"{hd + dev_um2:.4f}", "handout_usable_um2": str(hd),
            "reduced_vs_handout_pct": f"{100 * dev_um2 / hd:+.2f}", "yosys": "Yosys 0.70+post (x)"}


def test_table1_reproduced_only_within_rounding():
    assert mapping.matches_handout(4186.53, 4186.5) and not mapping.matches_handout(4195.27, 4186.5)
    assert summary.table1_status([row(0.04), row(-0.02)]) == "pass"
    st = summary.table1_status([row(0.04), row(8.77)])
    assert st.startswith("NOT REPRODUCED") and "1/2" in st


def test_selftest_status_names_open_row():
    st = {"run": {"status": "pass"}, "table4": [
        {"row": "exists", "status": "match"},
        {"row": "new_one_stage_small", "status": "definition-open"}]}
    assert summary.selftest_status(st) == "pass on rows 1-5 and 7; row 6 open (Q-1)"
    st["table4"][1]["status"] = "match"
    assert summary.selftest_status(st) == "pass"
    st["run"]["status"] = "fail"
    assert summary.selftest_status(st) == "FAIL"
