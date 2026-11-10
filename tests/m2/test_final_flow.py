import json
import shutil
import subprocess
import sys

import pytest

from dd2 import liberty, paths
from dd2m2.final_flow import _select
from dd2m2.generator import merge_responses, scale_cell_area
from dd2m2.reference import disposition


def test_greedy_retries_after_a_prefix_changes():
    requests = [{"name": n} for n in "abc"]
    scores = {"a": 100, "b": 95, "ba": 92, "bac": 93}
    selected, trials, curve = _select(
        requests, lambda prefix: scores["".join(r["name"] for r in prefix)], 100, 10,
    )
    assert [r["name"] for r in selected] == ["b", "a"]
    assert [row["kept"] for row in trials] == [False, True, True, False]
    assert [row["total_best_um2"] for row in curve] == [100, 95, 92]


def test_best_of_all_sweeps_each_round_and_keeps_the_lowest_area():
    requests = [{"name": n} for n in "abcd"]
    scores = {"a": 95, "b": 90, "c": 90, "d": 101, "ba": 91, "bc": 89, "bd": 84, "bda": 84, "bdc": 85}
    selected, trials, curve = _select(
        requests, lambda prefix: scores["".join(r["name"] for r in prefix)], 100, 10, best_of_all=True,
    )
    assert [r["name"] for r in selected] == ["b", "d"]
    assert len(trials) == len(scores)
    assert [row["cell"] for row in trials if row["kept"]] == ["b", "d"]
    assert [row["total_best_um2"] for row in curve] == [100, 90, 84]


def test_table4_acceptance_covers_only_the_recorded_row():
    row = dict(row="new_one_stage_small", handout=5, measured=6, status="definition-open")
    assert disposition([row]) == "TA accepted recorded difference"
    assert disposition([row | {"measured": 7}]) == "unresolved reference disagreement"
    assert disposition([row, {"status": "mismatch"}]) == "unresolved reference disagreement"
    assert disposition([]) == "missing M1 self-test"


def test_generator_import_and_sensitivity(tmp_path):
    name = "dd2_g4__n3_2b_1"
    request = {
        "request_id": "M2-002", "name": name, "inputs": ["A", "B", "C"], "output": "Y",
        "expression": "(A&!B) | (A&!C) | (!B&!C)", "truth_table": "0x2B",
        "sizing": "hd", "estimated_area_um2": 10.0096,
    }
    fixture = paths.ROOT / "cells" / name
    response = json.loads((fixture / "response.json").read_text())
    bundle = tmp_path / "responses"
    bundle.mkdir()
    response["files"]["liberty"] = "cell.lib"
    (bundle / "cell.lib").write_bytes((fixture / "cell.lib").read_bytes())
    metadata = bundle / "response.json"
    metadata.write_text(json.dumps(response))
    base = tmp_path / "baseline.lib"
    base.write_text('library ("test") {\n}\n')
    extended = tmp_path / "extended.lib"
    scaled = tmp_path / "scaled.lib"

    records = merge_responses(base, extended, [request], bundle)
    assert records[0]["real_area_um2"] == response["area_um2"]
    assert liberty.read_cells(extended)[0].tt == int(request["truth_table"], 16)
    original, adjusted = scale_cell_area(extended, scaled, name)
    assert adjusted == pytest.approx(0.7 * original)
    assert liberty.read_cells(scaled)[0].area == pytest.approx(adjusted)

    metadata.write_text(json.dumps(response | {"status": "fail", "reason": "deliberate failure"}))
    with pytest.raises(ValueError, match="passing matching cell"):
        merge_responses(base, extended, [request], bundle)
    with pytest.raises(ValueError, match="missing course generator response"):
        merge_responses(base, extended, [request | {"request_id": "missing"}], bundle)


@pytest.mark.skipif(
    any(not shutil.which(tool) for tool in ("yosys", "yosys-abc", "sta")),
    reason="unseen-design integration requires Yosys, ABC and OpenSTA",
)
def test_demo_runs_on_an_unseen_combinational_design(tmp_path):
    source = tmp_path / "dd2_combo_test.v"
    source.write_text(
        "module combo(input [3:0] a,b,c,d, output [3:0] y); "
        "assign y = ~(d & ((a & b) | (c & (a | b)))); endmodule\n"
    )
    run = subprocess.run(
        [sys.executable, "-m", "dd2m2", "demo", str(source), "--group", "4", "--limit", "1"],
        cwd=paths.ROOT, capture_output=True, text=True, timeout=180,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    out = paths.build("demo", source.stem, "estimated")
    assert json.loads((out / "requests.json").read_text())
    assert (out / "sensitivity.json").is_file()
