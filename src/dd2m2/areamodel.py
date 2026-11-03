"""Step 1: fit the area model on the HD x1 cells, with its held-out error."""

from dd2 import liberty, paths, provenance

from .cost import fit_model, implementation
from .tables import write_csv


def calibrate(out):
    full = paths.full_hd_lib()
    cells = liberty.read_cells(full)
    reduced = liberty.cell_names(paths.given() / "hd_reduced.lib")
    rows = []
    excluded = []
    for c in cells:
        if c.name not in reduced or not c.name.endswith("_1"):
            continue
        if len(c.inputs) > 4:
            excluded.append(
                {"name": c.name, "reason": "more than four inputs: outside candidate implementation domain"}
            )
            continue
        # The HD calibration cells are actual existing cells: NAND4/NOR4
        # legitimately have four-stack native implementations. The candidate
        # three-stack constraint must not artificially inflate their features.
        cost = implementation(c.tt, len(c.inputs), max_series=4)
        rows.append(
            dict(
                name=c.name,
                function=c.function,
                arity=len(c.inputs),
                area_um2=c.area,
                transistors=cost["transistors"],
                stages=cost["stages"],
                inverters=cost["inverters"],
                realization=cost["expression"],
                method=cost["method"],
            )
        )
    model, records = fit_model(rows)
    model["source_liberty"] = provenance.hash_inputs([full])
    model["excluded"] = excluded
    model["stack_limits"] = {"hd_calibration": 4, "new_candidates": 3}
    if not model["single_stage_cells"] or not model["multi_stage_cells"]:
        raise ValueError("area model must cover both single and multi-stage HD cells")
    provenance.write_json(out / "area_model.json", model)
    write_csv(out / "area_model_fit.csv", records)
    write_csv(out / "area_model_excluded.csv", excluded, ["name", "reason"])
    print(
        "Area model:",
        len(rows),
        "HD x1 cells; LOO MAPE",
        round(model["loo_mean_absolute_percent_error"], 2),
        "%",
        flush=True,
    )
    return cells, model
