import json

import pytest

from dd2 import boolfn as bf, liberty, paths, redundancy
from dd2.paths import ROOT

N = 4


@pytest.fixture(scope="module")
def idx():
    return redundancy.HdIndex(liberty.read_cells(paths.full_hd_lib()))


def tt(expr):
    return bf.eval_expr(expr, ["A", "B", "C", "D"])


def test_exists_after_permutation(idx):
    r = redundancy.classify(tt("!((C & A) | (D & B))"), N, idx)       # a22oi, inputs shuffled
    assert r["class"] == "Exists" and "a22oi" in r["witness"]["cell"]


def test_exists_with_input_inverter(idx):
    r = redundancy.classify(0x000B, N, idx)
    assert r["class"] == "Exists with an inverter" and r["witness"]["inverted"].startswith("input")


def test_output_inversion_on_synthetic_library():
    nand3 = liberty.LibCell("x_nand3", ["A", "B", "C"], "Y", "!(A&B&C)",
                            bf.eval_expr("!(A&B&C)", "ABC"), 1.0)
    i = redundancy.HdIndex([nand3])
    r = redundancy.classify(bf.eval_expr("A&B&C", "ABC"), 3, i)
    assert r["class"] == "Exists with an inverter" and r["witness"]["inverted"] == "output"


def test_contained_with_witness(idx):
    r = redundancy.classify(tt("!(A & (B | (C & D)))"), N, idx)
    assert r["class"] == "Contained"
    w = r["witness"]
    assert set(w["ties"].values()) <= {"A", "B", "C", "D", 0, 1}
    cell = {c.name: c for c in idx.cells}[w["cell"]]
    # re-evaluate the witness: the HD cell with its inputs tied as stated computes the candidate
    cols = {p: (bf.var_tt("ABCD".index(s), N) if isinstance(s, str) else (bf.mask(N) if s else 0))
            for p, s in w["ties"].items()}
    expr = cell.function
    got = 0
    for row in range(16):
        vals = [(cols[p] >> row) & 1 for p in cell.inputs]
        j = sum(v << k for k, v in enumerate(vals))
        got |= ((cell.tt >> j) & 1) << row
    assert got == tt("!(A & (B | (C & D)))")


def test_new(idx):
    assert redundancy.classify(0x077F, N, idx)["class"] == "New"


def test_broken_case_hd_cell_as_candidate(idx):
    case = json.loads((ROOT / "tests" / "broken" / "hd_cell_as_candidate.json").read_text())
    t = bf.eval_expr(case["expression"], case["inputs"])
    r = redundancy.classify(t, len(case["inputs"]), idx)
    assert r["class"] == case["expected"] == "Exists"
    assert r["witness"]["cell"].startswith(case["expected_witness_family"])


def test_every_hd_cell_is_exists(idx):
    for c in idx.cells:
        assert redundancy.classify(c.tt, len(c.inputs), idx)["class"] == "Exists", c.name


def test_table4(idx):
    rep = redundancy.table4(idx)
    got = {r["row"]: r for r in rep["rows"]}
    for row in ("exists", "exists_with_inverter", "contained", "new", "new_one_stage", "one_stage_read_once"):
        assert got[row]["status"] == "match", got[row]
    assert got["one_stage_read_once"]["breakdown"] == {"Exists": 6, "Contained": 2}
    # Row 6: measured 6 against the handout's 5 (research Q-1); recorded, never tuned.
    assert got["new_one_stage_small"]["measured"] == 6
    assert got["new_one_stage_small"]["status"] == "definition-open"


@pytest.mark.parametrize("tt, n", [(0x6, 1), (0xFFFF, 1), (0x1FFFF, 4)])
def test_table_too_wide_for_arity_is_rejected(idx, tt, n):
    # verifier finding 11: 0x6 at arity 1 used to come back Exists (as buf_1)
    with pytest.raises(ValueError, match="does not fit"):
        redundancy.classify(tt, n, idx)
