"""Option 2's saved records for the studio and the agent, read-only.

Nothing here runs or recomputes Option 2: every value comes from results/m2/ as `make m2` wrote it,
and from the response Option 1 wrote for each requested cell (Option 3).
"""
import csv
import json
import re

from dd2 import paths

M2 = paths.results("m2")
O3 = paths.results("option3")
CELLS = paths.ROOT / "cells"
FIGURES = paths.ROOT / "TA_M2" / "figures"
FIGURE = re.compile(r"\d\d_[a-z_]+\.png")
SHOWN = 30                       # eligible candidates the view lists


def _json(p):
    return json.loads(p.read_text()) if p.is_file() else None


def _csv(p) -> list:
    if not p.is_file():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def requests() -> list:
    return _json(M2 / "requests.json") or []


def answer(req: dict) -> dict:
    """What Option 1 answered for one request: its response, if it has written one."""
    r = _json(CELLS / req["name"] / "response.json")
    return {"request_id": req["request_id"], "name": req["name"], "option1": r["status"] if r else "not built",
            "real_area_um2": r.get("area_um2") if r and r.get("status") == "pass" else None, "reason": (r or {}).get("reason") or ""}


def view() -> dict:
    ready = _json(M2 / "readiness.json") or {}
    model = _json(M2 / "area_model.json") or {}
    ranked = _csv(M2 / "ranked_candidates.csv")
    reqs = {r["truth_table"].upper(): r for r in requests()}
    eligible = [r for r in ranked if r.get("eligible") == "True"]
    cands = []
    for r in eligible[:SHOWN]:
        req = reqs.get(r["key"].split(":")[1].upper())
        cands.append({k: r.get(k) for k in ("rank", "key", "expression", "redundancy_class", "transistors", "stages", "estimated_area_um2",
                                           "mapped_occurrences", "estimated_best_of_both_saving_um2")} | {"request": answer(req) if req else None})
    return {"readiness": {k: ready.get(k) for k in ("checkpoint_ready", "experimental_flow_status", "checks", "remaining", "final_only") if k in ready},
            "area_model": {k: model[k] for k in ("loo_mean_absolute_percent_error", "training_cells") if k in model},
            "counts": {"candidates": len(ranked), "eligible": len(eligible), "requested": len(reqs)},
            "candidates": cands, "best_of_both": _csv(M2 / "best_of_both_estimated.csv"), "mappings": _csv(M2 / "table5_estimated.csv"),
            "figures": figures(), "option3": {"cells": [answer(r) for r in requests()], "summary": _json(O3 / "summary.json"),
                                              "best_of_both": _csv(O3 / "best_of_both_estimated.csv")}}


def _round(row: dict) -> dict:
    """Saved values at the precision the records report, so an answer can quote them as they stand."""
    def r(x):
        try:
            return round(float(x), 4) if "." in str(x) else x
        except ValueError:
            return x
    return {k: r(x) for k, x in row.items()}


def facts() -> dict:
    """What the agent may know about Option 2: small, and only saved values."""
    v = view()
    return {"readiness": v["readiness"], "area_model": v["area_model"], "counts": v["counts"],
            "best_of_both": [_round(b) for b in v["best_of_both"]],
            "notes": ["TOTAL covers the six required benchmarks only; spm and multiplier are tutorial rows, reported separately.",
                      "Predicted savings rank candidates; measured remapping decides. A mapping saves area only where ABC instantiates a new cell."],
            "mappings": [{k: m.get(k) for k in ("design", "script", "new_cell_instances", "reduction_pct", "extended_equivalence", "effect_note")}
                         for m in map(_round, v["mappings"])],
            "top_candidates": [{k: c[k] for k in ("rank", "expression", "estimated_area_um2", "estimated_best_of_both_saving_um2")}
                               | {"request_id": (c["request"] or {}).get("request_id"), "option1": (c["request"] or {}).get("option1")}
                               for c in v["candidates"][:10]],
            "option3": v["option3"]["cells"]}


def request_for(ref: str) -> dict | None:
    """A requested candidate, by its request id (M2-003) or its place among the requests (3)."""
    reqs = requests()
    if re.fullmatch(r"\d{1,2}", ref or "") and 1 <= int(ref) <= len(reqs):
        return reqs[int(ref) - 1]
    return next((r for r in reqs if r["request_id"] == ref), None)


def figures() -> list:
    return sorted(p.name for p in FIGURES.glob("*.png") if FIGURE.fullmatch(p.name)) if FIGURES.is_dir() else []
