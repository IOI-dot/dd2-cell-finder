from dd2 import aig, designs, paths


def test_cpu8_both_variants(tmp_path):
    arts = aig.extract_design(designs.get("cpu8"), paths.given(), tmp_path)
    s, r = arts["synth"], arts["restructured"]
    assert s["run"]["status"] == r["run"]["status"] == "pass"
    assert s["header"]["L"] == s["ffs_after_synth"] == 82          # latches = flip-flops
    assert any("dch" in c for c in r["commands"]) and r["has_choices"] is False
    assert r["equivalent_to_synth"] is True                         # ABC cec
    assert r["outputs"] == s["outputs"] == 13                       # O + B, nothing lost
    assert r["strash_only_ands"] <= s["header"]["A"]
    g = aig.read_aiger(tmp_path / "cpu8" / "restructured.aig")
    assert g.A == r["header"]["A"] and g.L == 82 and len(g.all_outputs()) == 13
