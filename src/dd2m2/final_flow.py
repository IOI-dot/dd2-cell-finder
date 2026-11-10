"""Option 2 M3: select cells by remapping, then evaluate generator responses."""

import csv
import hashlib
import json
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, nullcontext
from pathlib import Path

from dd2 import designs, envcheck, mapping, paths, provenance
from dd2.demo import detect_top

from . import evaluate, tutorials
from .areamodel import calibrate
from .candidates import candidates, cell_request
from .generator import merge_responses, scale_cell_area
from .library import write_library
from .measure import baseline, measure
from .tables import write_csv


def _read(path):
    return json.loads(path.read_text())


def _import(lib, count, out):
    actual = envcheck.liberty_import_count(lib, out / "liberty_import.log")
    if actual != 189 + count:
        raise RuntimeError(f"{lib.name}: Yosys imported {actual} cells, expected {189 + count}")


def _trial_area(names, lib, resolve, work):
    def area(name):
        design, src = resolve(name)
        # Use the same RTL-to-ABC recipe as the measured run. Reloading saved
        # RTLIL can change ABC's ordering and therefore the mapped area.
        return min(
            evaluate.map_design(design, src, lib, script, work / name / script)["area_um2"]
            for script in mapping.SCRIPTS
        )

    if len(names) == 1:
        return area(names[0])
    with ThreadPoolExecutor(max_workers=min(4, len(names))) as pool:
        return sum(pool.map(area, names))


def _select(ranked, score, starting_area, limit, *, best_of_all=False):
    """Take the first improvement or the best measured improvement in each round."""
    remaining = list(ranked)
    selected, trials = [], []
    curve = [{"cells": 0, "cell": "", "total_best_um2": starting_area}]
    area = starting_area
    mode = "Best-of-all selection" if best_of_all else "Greedy selection"
    print(f"{mode}: {len(remaining)} eligible candidates, limit {limit}", flush=True)
    while remaining and len(selected) < limit:
        start = len(trials)
        winner = None
        winning_area = area
        if best_of_all:
            print(f"Round {len(selected) + 1}: testing all {len(remaining)} remaining candidates", flush=True)
        for i, request in enumerate(remaining):
            new_area = score([*selected, request])
            trials.append(
                {
                    "prefix_size": len(selected),
                    "cell": request["name"],
                    "previous_best_um2": area,
                    "trial_best_um2": new_area,
                    "kept": False,
                }
            )
            if len(trials) % 25 == 0:
                print(f"Completed {len(trials)} trials; kept {len(selected)} cells", flush=True)
            if new_area < winning_area - 1e-6:
                winner = i
                winning_area = new_area
                if not best_of_all:
                    break
        if winner is None:
            break
        request = remaining.pop(winner)
        selected.append(request)
        trials[start + winner]["kept"] = True
        area = winning_area
        curve.append({"cells": len(selected), "cell": request["name"], "total_best_um2": area})
        print("Kept", request["name"], "at total best area", area, flush=True)
    return selected, trials, curve


def _validate_mapping(names, out, lib, requests, resolve, label):
    _import(lib, len(requests), out)
    rows, best = measure(names, out, lib, requests, resolve=resolve, label=label)
    if any(
        r[f"{side}_{field}"] != "pass"
        for r in rows
        for side in ("baseline", "extended")
        for field in ("equivalence", "timing_status")
    ):
        raise RuntimeError(f"{label}: mapping verification failed; see {out}")
    result = tutorials.verify(names, out, lib) if resolve is tutorials.resolve else {}
    if any(not r["mapping_and_gate_simulation_verified"] for r in result.values()):
        raise RuntimeError(f"{label}: tutorial gate simulation failed; see {out}")
    return best[-1]["extended_best_um2"]


def _estimated(names, objective, out, ranked, group, limit, resolve, base_rows=None, *, best_of_all=False):
    out.mkdir(parents=True, exist_ok=True)
    base_lib = paths.given() / "hd_reduced.lib"
    if base_rows is None:
        base_rows = baseline(names, out, resolve=resolve)
    if any(r["equivalence"] != "pass" for r in base_rows):
        raise RuntimeError("baseline CEC failed")
    areas = {(r["design"], r["script"]): r["area_um2"] for r in base_rows}
    base_area = sum(min(areas[name, script] for script in mapping.SCRIPTS) for name in objective)
    requests = [
        cell_request(c, group, f"M3-{c['rank']:04d}") for c in ranked if c["eligible"]
    ]
    cache_context = closing(sqlite3.connect(out / "trial_scores.sqlite3")) if best_of_all else nullcontext()
    with tempfile.TemporaryDirectory(prefix="trial_", dir=out) as temp, cache_context as cache:
        work = Path(temp)
        trial_lib = work / "trial.lib"
        if cache is not None:
            cache.execute("CREATE TABLE IF NOT EXISTS scores (key TEXT PRIMARY KEY, area REAL NOT NULL)")
            context = json.dumps(
                [objective, mapping.SCRIPTS,
                 [{k: r[k] for k in ("design", "top", "script", "area_um2", "inputs", "yosys")}
                  for r in base_rows if r["design"] in objective],
                 provenance.sha256(Path(evaluate.__file__))],
                sort_keys=True,
            )

        def score(prefix):
            write_library(base_lib, trial_lib, prefix)
            if cache is not None:
                key = hashlib.sha256((context + provenance.sha256(trial_lib)).encode()).hexdigest()
                saved = cache.execute("SELECT area FROM scores WHERE key = ?", (key,)).fetchone()
                if saved is not None:
                    return saved[0]
            try:
                area = _trial_area(objective, trial_lib, resolve, work)
            except RuntimeError:
                for log in work.glob("*/?/mapping.log"):
                    target = out / "failed_trial" / log.relative_to(work)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(log.read_bytes())
                raise
            if cache is not None:
                cache.execute("INSERT INTO scores VALUES (?, ?)", (key, area))
                cache.commit()
            return area

        selected, trials, curve = _select(requests, score, base_area, limit, best_of_all=best_of_all)
    write_csv(
        out / "selection_trials.csv", trials,
        ["prefix_size", "cell", "previous_best_um2", "trial_best_um2", "kept"],
    )
    write_csv(out / "cell_curve_estimated.csv", curve)
    lib = out / "hd_extended_estimated.lib"
    if selected:
        write_library(base_lib, lib, selected)
    else:
        lib.write_bytes(base_lib.read_bytes())
    measured = _validate_mapping(names, out, lib, selected, resolve, "estimated")
    if abs(measured - curve[-1]["total_best_um2"]) > 1e-5:
        raise RuntimeError("verified estimated result differs from the greedy trial")
    _plot_curve(curve, [], out)
    _sensitivity(names, out, lib, selected, resolve, measured)
    current = {f'{request["name"]}.json' for request in selected}
    for path in (out / "requests").glob("*.json"):
        if path.name not in current:
            path.unlink()
    for request in selected:
        provenance.write_json(out / "requests" / f'{request["name"]}.json', request)
    provenance.write_json(out / "requests.json.tmp", selected).replace(out / "requests.json")
    return selected


def _plot_curve(estimated, real, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    for label, rows in [("Estimated", estimated), ("Real", real)]:
        if rows:
            ax.plot(
                [int(r["cells"]) for r in rows],
                [float(r["total_best_um2"]) for r in rows],
                "o-",
                label=label,
            )
    ax.set(xlabel="Cells added in greedy order", ylabel="Total best-of-A/B area (µm²)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "cell_curve.pdf")
    plt.close(fig)


def _sensitivity(names, out, source, requests, resolve, original_area):
    if not requests:
        provenance.write_json(
            out / "sensitivity.json", {"status": "no selected cell", "reason": "no candidate reduced total area"}
        )
        return
    dest = out / "sensitivity"
    dest.mkdir(exist_ok=True)
    cell = requests[0]["name"]
    lib = dest / "hd_extended_70pct.lib"
    before, after = scale_cell_area(source, lib, cell)
    baseline(names, dest, resolve=resolve)
    affected = _validate_mapping(names, dest, lib, requests, resolve, "sensitivity")
    provenance.write_json(
        out / "sensitivity.json",
        {
            "cell": cell, "original_cell_area_um2": before, "scaled_cell_area_um2": after,
            "original_total_best_um2": original_area, "scaled_total_best_um2": affected,
            "library_sha256": provenance.sha256(lib),
        },
    )


def _names():
    missing = [name for name in tutorials.SPECS if not tutorials.supplied(name)]
    if missing:
        raise ValueError("missing original tutorial inputs: " + ", ".join(missing))
    required = [d.name for d in designs.required()]
    # The technical report explicitly compares these three implementations of the same ISA.
    return required + list(tutorials.SPECS) + ["pic16", "p16c5x"], required


def estimated(out, group, limit, *, best_of_all=False):
    names, objective = _names()
    ranked = _read(paths.results("m2", "candidates.json"))
    if not best_of_all:
        return _estimated(names, objective, out, ranked, group, limit, tutorials.resolve)

    import fcntl

    if out.resolve().is_relative_to(paths.results("m3", "estimated").resolve()):
        raise ValueError("use a separate output directory for the best-of-all experiment")
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".sweep.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(f"a best-of-all run already uses {out}") from error
        if (out / "requests.json").exists():
            raise ValueError(f"completed results already exist in {out}; use a new --out directory")
        return _estimated(names, objective, out, ranked, group, limit, tutorials.resolve, best_of_all=True)


def real(estimated_out, out, responses):
    names, objective = _names()
    requests = _read(estimated_out / "requests.json")
    out.mkdir(parents=True, exist_ok=True)
    base_lib = paths.given() / "hd_reduced.lib"
    real_lib = out / "hd_extended_real.lib"
    manifest = out / "generator_cells.json"
    manifest.unlink(missing_ok=True)
    real_cells = merge_responses(base_lib, real_lib, requests, responses)
    base_rows = baseline(names, out)
    if any(r["equivalence"] != "pass" for r in base_rows):
        raise RuntimeError("baseline CEC failed")
    estimated_baseline = _read(estimated_out / "baseline_mappings.json")
    comparable = ("design", "script", "area_um2", "inputs", "yosys")
    if [[r[k] for k in comparable] for r in base_rows] != [
        [r[k] for k in comparable] for r in estimated_baseline
    ]:
        raise RuntimeError("estimated and real baselines differ; rerun both with the same tools and inputs")
    best = _validate_mapping(names, out, real_lib, requests, tutorials.resolve, "real")
    areas = {(r["design"], r["script"]): r["area_um2"] for r in base_rows}
    start = sum(min(areas[name, script] for script in mapping.SCRIPTS) for name in objective)
    curve = [{"cells": 0, "cell": "", "total_best_um2": start}]
    with tempfile.TemporaryDirectory(prefix="curve_", dir=out) as temp:
        work = Path(temp)
        for i, request in enumerate(requests, 1):
            if i == len(requests):
                area = best
            else:
                prefix = work / "prefix.lib"
                merge_responses(base_lib, prefix, requests[:i], responses)
                area = _trial_area(objective, prefix, tutorials.resolve, work)
            curve.append({"cells": i, "cell": request["name"], "total_best_um2": area})
    write_csv(out / "cell_curve_real.csv", curve)
    with (estimated_out / "cell_curve_estimated.csv").open() as stream:
        _plot_curve(list(csv.DictReader(stream)), curve, out)
    _sensitivity(names, out, real_lib, requests, tutorials.resolve, best)
    provenance.write_json(manifest, real_cells)


def demo(src, top, sv, group, limit, real_dir=None):
    src = src.absolute()
    if not src.is_file():
        raise ValueError(f"design not found: {src}")
    sv = sv or src.suffix.lower() == ".sv"
    top = top or detect_top(src, sv)
    if not top:
        raise ValueError("could not infer the top module; pass TOP=<module>")
    design = designs.Design(src.stem, top, False, sv)
    root = paths.build("demo", design.name)
    out = root / "estimated"

    def resolve(_name):
        return design, src

    discovery = root / "discovery"
    write_csv(
        root / "aig_cuts.csv",
        tutorials.discover_design(design, src, discovery, root / "full_cuts"),
    )
    cells, model = calibrate(out)
    base_rows = baseline([design.name], out, resolve=resolve)
    ranked = candidates([design.name], out, cells, model, resolve=resolve, cuts_dir=discovery / "cuts")
    _estimated([design.name], [design.name], out, ranked, group, limit, resolve, base_rows)
    if real_dir is not None:
        real_out = root / "real"
        real_out.mkdir(parents=True, exist_ok=True)
        requests = _read(real_dir / "generator_cells.json")
        baseline([design.name], real_out, resolve=resolve)
        _validate_mapping(
            [design.name], real_out, real_dir / "hd_extended_real.lib", requests, resolve, "real",
        )
    print(f"Option 2 demo passed. Evidence: {root}", flush=True)
