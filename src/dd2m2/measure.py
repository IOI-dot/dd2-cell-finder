"""Steps 2 and 5: map every design onto the reduced library, then onto the extended one,
proving each mapping with ABC cec and timing it with OpenSTA."""

import json

from dd2 import designs, mapping, paths, provenance

from . import evaluate, tutorials
from .tables import write_csv


def baseline(names, out):
    rows = []
    for name in names:
        d, src = tutorials.resolve(name)
        for script in mapping.SCRIPTS:
            dest = out / "mapping" / name / "baseline" / script
            r = evaluate.map_design(d, src, paths.given() / "hd_reduced.lib", script, dest)
            eq = evaluate.verify_mapping(d, paths.given() / "hd_reduced.lib", dest)
            rows.append(r | {"equivalence": eq["status"]})
            print("Baseline", name, script, r["area_um2"], "equivalence", eq["status"], flush=True)
    provenance.write_json(out / "baseline_mappings.json", rows)
    return rows


def measure(names, out, lib, reqs):
    rows = []
    base = json.loads((out / "baseline_mappings.json").read_text())
    lookup = {(r["design"], r["script"]): r for r in base}
    new_names = {r["name"] for r in reqs}
    for name in names:
        d, src = tutorials.resolve(name)
        for script in mapping.SCRIPTS:
            dest = out / "mapping" / name / "extended" / script
            r = evaluate.map_design(d, src, lib, script, dest)
            eq = evaluate.verify_mapping(d, lib, dest)
            timing = evaluate.timing(d, lib, dest)
            b = lookup[(name, script)]
            base_dir = out / "mapping" / name / "baseline" / script
            bt = evaluate.timing(d, paths.given() / "hd_reduced.lib", base_dir)
            instances = sum(v for k, v in r["cell_counts"].items() if k.lstrip("\\") in new_names)
            rows.append(
                dict(
                    design=name,
                    script=script,
                    baseline_um2=b["area_um2"],
                    extended_um2=r["area_um2"],
                    reduction_pct=100 * (b["area_um2"] - r["area_um2"]) / b["area_um2"],
                    new_cell_instances=instances,
                    baseline_equivalence=b["equivalence"],
                    extended_equivalence=eq["status"],
                    baseline_delay_ns=bt["worst_arrival_ns"],
                    extended_delay_ns=timing["worst_arrival_ns"],
                    baseline_timing_status=bt["status"],
                    extended_timing_status=timing["status"],
                    effect_note=(
                        "library-induced remapping; no new cell instantiated"
                        if instances == 0 and abs(b["area_um2"] - r["area_um2"]) > 1e-6
                        else "new cell instantiated" if instances else "no new cell instantiated"
                    ),
                )
            )
            print(
                "Extended",
                name,
                script,
                "area",
                r["area_um2"],
                "new instances",
                instances,
                "CEC",
                eq["status"],
                flush=True,
            )
    write_csv(out / "table5_estimated.csv", rows)
    best = []
    for name in names:
        ds = [r for r in rows if r["design"] == name]
        b = min(r["baseline_um2"] for r in ds)
        e = min(r["extended_um2"] for r in ds)
        best.append(
            dict(
                design=name,
                baseline_best_um2=b,
                extended_best_um2=e,
                saving_um2=b - e,
                reduction_pct=100 * (b - e) / b,
            )
        )
    required_names = {d.name for d in designs.required()}
    b = sum(r["baseline_best_um2"] for r in best if r["design"] in required_names)
    e = sum(r["extended_best_um2"] for r in best if r["design"] in required_names)
    best.append(
        dict(
            design="TOTAL",
            baseline_best_um2=b,
            extended_best_um2=e,
            saving_um2=b - e,
            reduction_pct=100 * (b - e) / b,
        )
    )
    write_csv(out / "best_of_both_estimated.csv", best)
    return rows, best
