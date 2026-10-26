"""Class table of HD (research D-9): every single-output combinational cell of the full HD
Liberty with its P, PN and NPN class over its essential inputs, and the PN classes grouped."""
import csv
from collections import Counter
from pathlib import Path

from . import boolfn as bf
from . import liberty, paths, provenance


def build(full_lib: Path, reduced_lib: Path, skipped: list | None = None):
    reduced = liberty.cell_names(reduced_lib)
    rows = []
    for c in sorted(liberty.read_cells(full_lib, skipped), key=lambda c: c.name):
        n = len(c.inputs)
        ess = bf.depends_on(c.tt, n)
        t, m = bf.shrink(c.tt, n, ess), len(ess)
        rows.append({"name": c.name, "inputs": c.inputs, "arity": n, "essential_inputs": m,
                     "function": c.function, "tt": bf.to_hex(c.tt, n), "area_um2": c.area,
                     "in_reduced": c.name in reduced, "p_class": bf.to_hex(bf.canon_p(t, m), m),
                     "pn_class": bf.to_hex(bf.canon_pn(t, m), m),
                     "npn_class": bf.to_hex(bf.canon_npn(t, m), m)})
    groups = {}
    for r in rows:
        groups.setdefault((r["essential_inputs"], r["pn_class"]), []).append(r)
    classes = []
    for (m, pn), members in sorted(groups.items()):
        small = min(members, key=lambda r: (r["area_um2"], r["name"]))
        classes.append({"inputs": m, "pn_class": pn, "members": len(members),
                        "cells": " ".join(r["name"].replace("sky130_fd_sc_hd__", "") for r in members),
                        "smallest": small["name"], "smallest_area_um2": small["area_um2"],
                        "in_reduced": any(r["in_reduced"] for r in members)})
    return rows, classes


def run(pdk: Path, given: Path, out: Path) -> int:
    full, red = paths.full_hd_lib(pdk), Path(given) / "hd_reduced.lib"
    rec = provenance.RunRecord(argv=["dd2", "hdclasses"], inputs=provenance.hash_inputs([full, red]))
    skipped = []
    rows, classes = build(full, red, skipped)
    rec.finish(0)
    out = Path(out)
    provenance.write_json(out / "hd_classes.json", {
        "cells": rows, "pn_classes": classes, "cells_total": len(rows),
        "pn_classes_total": len(classes),
        "npn_classes_total": len({(r["essential_inputs"], r["npn_class"]) for r in rows}),
        "p_classes_total": len({(r["essential_inputs"], r["p_class"]) for r in rows}),
        "excluded_total": len(skipped),
        "excluded_by_reason": dict(Counter(reason.split(" pin ")[0] if "has no function" in reason
                                           else reason for _, reason in skipped)),
        "excluded": [{"name": n, "reason": r} for n, r in sorted(skipped)],
        "run": rec.asdict()})
    with open(out / "hd_classes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "inputs"] + ["inputs"])
        w.writeheader()
        for r in rows:
            w.writerow(r | {"inputs": " ".join(r["inputs"])})
    with open(out / "hd_pn_classes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(classes[0]))
        w.writeheader()
        w.writerows(classes)
    print(f"HD: {len(rows)} cells, {len(classes)} PN classes, "
          f"{len({(r['essential_inputs'], r['npn_class']) for r in rows})} NPN classes")
    return 0
