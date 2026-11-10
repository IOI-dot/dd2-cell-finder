"""Option 2 in the studio: read-only views of its saved records, and the link to Option 1 (Option 3)."""
import csv
import json

import pytest

pytest.importorskip("ag_ui_langgraph", reason="make setup installs the web extra")
from fastapi.testclient import TestClient

from dd2_agent import graph, model, option2, server

REQS = [{"request_id": "M2-001", "name": "dd2_g4__n4_17ff_1", "inputs": list("ABCD"), "output": "Y", "expression": "!((D&((A&B)|(C&(A|B)))))",
         "truth_table": "0x17FF", "sizing": "hd", "estimated_area_um2": 8.7584}]


@pytest.fixture
def m2(tmp_path, monkeypatch):
    d = tmp_path / "m2"
    d.mkdir()
    (d / "requests.json").write_text(json.dumps(REQS))
    (d / "readiness.json").write_text(json.dumps({"checkpoint_ready": False, "experimental_flow_status": "pass",
                                                  "checks": {"mapping_equivalence": True, "reference_table4_agrees": False},
                                                  "remaining": ["Table 4: six against five"], "tutorial_inputs": {"x": "big"}}))
    (d / "area_model.json").write_text(json.dumps({"loo_mean_absolute_percent_error": 14.61, "training_cells": 61, "coefficients_sites": [1]}))
    rows = [{"rank": "1", "key": "4:0x17FF", "expression": "!((D&((A&B)|(C&(A|B)))))", "redundancy_class": "New", "eligible": "True",
             "estimated_area_um2": "8.7584", "mapped_occurrences": "231", "estimated_best_of_both_saving_um2": "1777.9552", "transistors": "12", "stages": "1"},
            {"rank": "2", "key": "2:0x8", "expression": "A&B", "redundancy_class": "Exists", "eligible": "False",
             "estimated_area_um2": "6.2", "mapped_occurrences": "9", "estimated_best_of_both_saving_um2": "0", "transistors": "6", "stages": "2"}]
    with open(d / "ranked_candidates.csv", "w", newline="") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    for name, cols, row in [("best_of_both_estimated.csv", ["design", "baseline_best_um2", "extended_best_um2", "saving_um2", "reduction_pct"],
                             ["spm", "2869.0", "2830.2", "38.8", "1.35"]),
                            ("table5_estimated.csv", ["design", "script", "extended_equivalence", "new_cell_instances"], ["spm", "A", "pass", "3"])]:
        with open(d / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerow(row)
    cells = tmp_path / "cells" / REQS[0]["name"]
    cells.mkdir(parents=True)
    (cells / "response.json").write_text(json.dumps({"status": "pass", "area_um2": 9.248, "reason": None}))
    monkeypatch.setattr(option2, "M2", d)
    monkeypatch.setattr(option2, "CELLS", tmp_path / "cells")
    monkeypatch.setattr(option2, "O3", tmp_path / "o3")
    return d


def test_the_view_holds_records_and_each_request_says_what_option_1_answered(m2):
    v = option2.view()
    assert v["readiness"]["checkpoint_ready"] is False and v["readiness"]["remaining"] == ["Table 4: six against five"]
    assert "tutorial_inputs" not in v["readiness"]
    assert v["area_model"] == {"loo_mean_absolute_percent_error": 14.61, "training_cells": 61}
    assert [c["rank"] for c in v["candidates"]] == ["1"] and v["counts"] == {"candidates": 2, "eligible": 1, "requested": 1}
    assert v["candidates"][0]["request"] == {"request_id": "M2-001", "name": "dd2_g4__n4_17ff_1", "option1": "pass", "real_area_um2": 9.248, "reason": ""}
    assert v["best_of_both"][0]["design"] == "spm" and v["mappings"][0]["new_cell_instances"] == "3"


def test_a_candidate_is_found_by_request_id_or_rank(m2):
    assert option2.request_for("M2-001")["name"] == "dd2_g4__n4_17ff_1"
    assert option2.request_for("1")["request_id"] == "M2-001"
    assert option2.request_for("m2-1") is None and option2.request_for("7") is None


def test_figures_are_served_by_exact_name_only():
    client = TestClient(server.create_app(dict(model.load_config(), model={"provider": "scripted", "name": "x"})))
    for bad in ["../../Makefile", "x.png", "01_area_model_validation.svg"]:
        assert client.get(f"/api/option2/figure/{bad}").status_code == 404
    names = option2.figures()
    if names:
        r = client.get(f"/api/option2/figure/{names[0]}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_building_a_candidate_routes_its_expression_to_option_1(m2):
    it = model.Intent(kind="BUILD_CANDIDATE", expression="", sizing="hd", order_index=0, revision="", reason="", options=[], focus="", candidate="M2-001")
    r = graph.Run.route(graph.Run.__new__(graph.Run), it, {"revisions": []})
    assert r["expr"] == REQS[0]["expression"] and r["intent"]["kind"] == "BUILD_CANDIDATE"


def test_an_unknown_candidate_builds_nothing(m2):
    it = model.Intent(kind="BUILD_CANDIDATE", expression="", sizing="hd", order_index=0, revision="", reason="", options=[], focus="", candidate="M2-099")
    r = graph.Run.route(graph.Run.__new__(graph.Run), it, {"revisions": []})
    assert "expr" not in r and r["intent"]["kind"] == "UNCLEAR"
