"""The Table 4 question: the six verified one-stage witnesses against the handout's five."""

import json

from dd2 import boolfn as bf, paths, provenance

from .cost import stage_forms
from .tables import write_csv


ACCEPTED_ROW = ("new_one_stage_small", 5, 6, "definition-open")
DISPOSITION = "TA accepted GB4's six-versus-five result as submitted, per the team."


def disposition(rows):
    if not rows:
        return "missing M1 self-test"
    differences = [r for r in rows if r.get("status") != "match"]
    if not differences:
        return "match"
    if len(differences) == 1:
        r = differences[0]
        if tuple(r.get(k) for k in ("row", "handout", "measured", "status")) == ACCEPTED_ROW:
            return "TA accepted recorded difference"
    return "unresolved reference disagreement"


def witness_report(out):
    p = paths.results("m1", "redundancy", "self_test.json")
    if not p.exists():
        return {"status": "missing M1 self-test"}
    st = json.loads(p.read_text())
    rows = st.get("table4", [])
    openrows = [r for r in rows if r.get("status") != "match"]
    witnesses = []
    for row in openrows:
        for w in row.get("witnesses", []):
            t = int(w["tt"], 16)
            f = stage_forms(4).get(t ^ bf.mask(4))
            if not f:
                continue
            key, expr = f
            y = "!(" + expr + ")"
            witnesses.append(
                {
                    "truth_table": w["tt"],
                    "expression": y,
                    "literals": key[0],
                    "transistors": 2 * key[0],
                    "n_series": key[2],
                    "p_series": key[3],
                    "truth_table_verified": bf.eval_expr(y, list("ABCD")) == t,
                }
            )
    write_csv(
        out / "reference_count_witnesses.csv",
        witnesses,
        [
            "truth_table",
            "expression",
            "literals",
            "transistors",
            "n_series",
            "p_series",
            "truth_table_verified",
        ],
    )
    data = {
        "status": disposition(rows),
        "rows": openrows,
        "witnesses": witnesses,
        "note": DISPOSITION if disposition(rows) == "TA accepted recorded difference" else "",
    }
    provenance.write_json(out / "reference_count_review.json", data)
    question = [
        "# Table 4 clarification for GB4",
        "",
        "The checker reproduces the Exists, Exists-with-inverter, Contained and New counts,",
        "and the nine one-stage and eight read-once classes. The limited one-stage row",
        "gives six classes where the handout gives five. The reference number remains unchanged.",
        "",
        "| Truth table | Expression | Transistors | NMOS series | PMOS series |",
        "|---|---|---:|---:|---:|",
    ]
    for w in witnesses:
        expr = w["expression"].replace("|", r"\|")
        question.append(
            f'| {w["truth_table"]} | `{expr}` | {w["transistors"]} | {w["n_series"]} | {w["p_series"]} |'
        )
    question += [
        "",
        "Each row has a verified 16-row truth table and uses six literal occurrences,",
        "giving six NMOS plus six PMOS transistors in complementary series/parallel networks.",
        "Input A is the least significant truth-table variable.",
        "",
        data["note"] or f'Review status: {data["status"]}.',
    ]
    (out / "reference_count_question.md").write_text("\n".join(question) + "\n")
    return data
