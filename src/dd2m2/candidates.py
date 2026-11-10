"""Steps 3 and 4: rank the candidate functions by mapped-cone savings, and write the cell
requests (Appendix A) for the best eligible ones."""

import gzip
import json
from collections import Counter, defaultdict

from dd2 import boolfn as bf, designs, mapping, paths, provenance, redundancy

from . import cones, tutorials
from .cost import implementation, predict_area
from .tables import write_csv


def candidates(names, out, cells, model, *, resolve=tutorials.resolve, cuts_dir=None):
    objective_names = [name for name in names if name in {d.name for d in designs.required()}] or names
    counts = defaultdict(Counter)
    # Original M1 discovery counts are retained separately for each AIG variant.
    for name in names:
        for variant in ["synth", "restructured"]:
            p = (
                out / "tutorial_discovery" / name / "cuts" / (variant + ".summary.json")
                if name in tutorials.SPECS
                else paths.results("m1", "cuts", name, variant + ".summary.json")
            )
            if cuts_dir is not None:
                p = cuts_dir / (variant + ".summary.json")
            if p.is_file():
                hist = json.loads(p.read_text()).get("p_histogram", {})
                for key, count in hist.items():
                    arity, tt = key.split(":")
                    n = int(arity)
                    if 2 <= n <= 4:
                        counts[(n, int(tt, 16))][variant] += count
    occurrences = defaultdict(list)
    idx = redundancy.HdIndex(cells)
    for name in names:
        for script in mapping.SCRIPTS:
            p = out / "mapping" / name / "baseline" / script / "mapped.json"
            print("Mapped-cone costs:", name, script, flush=True)
            for r in cones.mapped_cuts(json.loads(p.read_text()), resolve(name)[0].top, cells):
                key = (r["arity"], r["tt"])
                counts[key]["mapped"] += 1
                occurrences[key].append(r | {"design": name, "script": script})
    cell_by_name = {c.name: c for c in cells}
    invs = [c.area for c in cells if len(c.inputs) == 1 and c.tt == 1]
    inv_area = min(invs)
    baselines = json.loads((out / "baseline_mappings.json").read_text())
    base = {(r["design"], r["script"]): r["area_um2"] for r in baselines}
    results = []
    occurrence_path = out / "candidate_occurrences.jsonl.gz"
    with gzip.open(occurrence_path, "wt") as f:
        for (n, tt), hist in sorted(counts.items()):
            cls = redundancy.classify(tt, n, idx)
            cost = implementation(tt, n)
            area = predict_area(model, cost)
            witness = cls["witness"]
            threshold = None
            if witness:
                threshold = cell_by_name[witness["cell"]].area + (
                    inv_area if cls["class"] == redundancy.INVERTER else 0
                )
            keep = cls["class"] == redundancy.NEW or (
                cls["class"] != redundancy.EXISTS and area < (threshold or 0)
            )
            savings = defaultdict(float)
            used = defaultdict(set)
            accepted = 0
            replace = 0.0
            for occ in sorted(
                occurrences[(n, tt)],
                key=lambda r: (-r["replaced_area_um2"], r["design"], r["script"], r["root"]),
            ):
                f.write(json.dumps({"class_key": f"{n}:{bf.to_hex(tt,n)}"} | occ) + "\n")
                k = (occ["design"], occ["script"])
                removed = set(occ["removed_cells"])
                benefit = occ["replaced_area_um2"] - area
                if benefit > 0 and not removed & used[k]:
                    used[k] |= removed
                    savings[k] += benefit
                    accepted += 1
                    replace += occ["replaced_area_um2"]
            predicted = sum(
                min(base[(name, s)] for s in mapping.SCRIPTS)
                - min(base[(name, s)] - savings[(name, s)] for s in mapping.SCRIPTS)
                for name in objective_names
            )
            r = dict(
                key=f"{n}:{bf.to_hex(tt,n)}",
                arity=n,
                truth_table=bf.to_hex(tt, n),
                pn_class=bf.to_hex(bf.canon_pn(tt, n), n),
                npn_class=bf.to_hex(bf.canon_npn(tt, n), n),
                expression=cost["expression"],
                redundancy_class=cls["class"],
                witness=witness,
                transistors=cost["transistors"],
                stages=cost["stages"],
                inverters=cost["inverters"],
                max_series=cost["max_series"],
                estimated_area_um2=area,
                existing_implementation_threshold_um2=threshold,
                eligible=keep,
                aig_synth_occurrences=hist["synth"],
                aig_restructured_occurrences=hist["restructured"],
                mapped_occurrences=len(occurrences[(n, tt)]),
                nonoverlapping_profitable_occurrences=accepted,
                replaced_area_for_selected_occurrences_um2=replace,
                estimated_best_of_both_saving_um2=predicted,
                cost=cost,
            )
            results.append(r)
    results.sort(
        key=lambda r: (
            not r["eligible"],
            -r["estimated_best_of_both_saving_um2"],
            -r["mapped_occurrences"],
            r["key"],
        )
    )
    for i, r in enumerate(results, 1):
        r["rank"] = i
    provenance.write_json(out / "candidates.json", results)
    fields = [
        "rank",
        "key",
        "arity",
        "truth_table",
        "expression",
        "redundancy_class",
        "witness",
        "eligible",
        "transistors",
        "stages",
        "inverters",
        "max_series",
        "estimated_area_um2",
        "existing_implementation_threshold_um2",
        "aig_synth_occurrences",
        "aig_restructured_occurrences",
        "mapped_occurrences",
        "nonoverlapping_profitable_occurrences",
        "replaced_area_for_selected_occurrences_um2",
        "estimated_best_of_both_saving_um2",
    ]
    write_csv(out / "ranked_candidates.csv", results, fields)
    write_csv(
        out / "redundancy_report.csv",
        results,
        [
            "key",
            "expression",
            "redundancy_class",
            "witness",
            "eligible",
            "estimated_area_um2",
            "existing_implementation_threshold_um2",
        ],
    )
    provenance.write_json(
        out / "candidate_ranking_method.json",
        {
            "source": "actual cells of the reduced-library A/B mappings; primary-input/FF boundaries",
            "shared_logic": "only cells with no outside consumers except the cut root are reclaimable",
            "overlap": "greedy non-overlapping occurrences per candidate, design and script; classes can still overlap",
            "estimate": "predicted best-of-both aggregate; final areas are measured by remapping",
            "objective_designs": objective_names,
            "aig_frequency": "synth/restructured counts are separate descriptions of the same designs, not added as physical instances",
        },
    )
    return results


def requests(out, group, limit, candidates):
    eligible = [r for r in candidates if r["eligible"]]
    chosen = eligible[:limit]
    reqs = []
    for i, c in enumerate(chosen, 1):
        r = cell_request(c, group, f"M2-{i:03d}")
        provenance.write_json(out / "requests" / f'{r["name"]}.json', r)
        reqs.append(r)
    provenance.write_json(out / "requests.json", reqs)
    group_name_path = paths.ROOT / "config/group_name.txt"
    group_name = group_name_path.read_text().strip() if group_name_path.is_file() else f"Group {group}"
    provenance.write_json(
        out / "selection.json",
        {
            "group": group,
            "group_name": group_name,
            "selected_keys": [r["key"] for r in chosen],
            "rule": f"first {limit} eligible ranked candidates; M2 exploratory set, not final greedy selection",
            "note": "zero predicted or actual saving is retained as an experimental result, never forced positive",
        },
    )
    return reqs


def cell_request(c, group, request_id):
    name = f'dd2_g{group}__n{c["arity"]}_{c["truth_table"][2:].lower()}_1'
    return {
        "request_id": request_id,
        "name": name,
        "inputs": list("ABCD"[: c["arity"]]),
        "output": "Y",
        "expression": c["expression"],
        "truth_table": c["truth_table"],
        "sizing": "hd",
        "estimated_area_um2": c["estimated_area_um2"],
    }
