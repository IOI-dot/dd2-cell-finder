from dd2 import aig, designs, paths


def test_cpu8_both_variants(tmp_path):
    arts = aig.extract_design(designs.get("cpu8"), paths.given(), tmp_path)
    s, r = arts["synth"], arts["restructured"]
    assert s["run"]["status"] == r["run"]["status"] == "pass"
    assert s["aig_sha256"] != r["aig_sha256"]
    assert s["header"]["L"] == s["ffs_after_synth"] == 82          # latches = flip-flops
    assert any("dch" in c for c in r["commands"])
    g = aig.read_aiger(tmp_path / "cpu8" / "restructured.aig")    # parses: no choice nodes
    assert g.A == r["header"]["A"] and g.L == 82
