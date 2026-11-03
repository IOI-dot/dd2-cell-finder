"""The whole Option 2 M2 run, step by step (make m2)."""

import json
import sys
from pathlib import Path

from dd2 import envcheck, paths, provenance

from . import tutorials
from .areamodel import calibrate
from .candidates import candidates, requests
from .environment import check
from .library import write_library
from .measure import baseline, measure
from .reference import witness_report
from .report import plots, showcase, summary
from .tables import write_csv


def run(group, limit, names, out):
    out = Path(out).absolute()
    out.mkdir(parents=True, exist_ok=True)
    names = list(dict.fromkeys(list(names) + [n for n in tutorials.SPECS if tutorials.supplied(n)]))
    if not check(out / "environment.json"):
        return 1
    env = json.loads((out / "environment.json").read_text())
    import subprocess

    p = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True)
    (out / "python_packages.txt").write_text(p.stdout)
    cells, model = calibrate(out)
    discovery = tutorials.discovery(names, out)
    if discovery:
        write_csv(out / "tutorial_aig_cuts.csv", discovery)
    baseline(names, out)
    cs = candidates(names, out, cells, model)
    reqs = requests(out, group, limit, cs)
    lib = out / "hd_extended_estimated.lib"
    write_library(paths.given() / "hd_reduced.lib", lib, reqs)
    if out == paths.results("m2"):
        import shutil

        (paths.ROOT / "libs").mkdir(exist_ok=True)
        shutil.copy2(lib, paths.ROOT / "libs/hd_extended_estimated.lib")
    imported = envcheck.liberty_import_count(lib, out / "liberty_import.log")
    want = 189 + len(reqs)
    provenance.write_json(
        out / "extended_library.json",
        {
            "path": paths.rel(lib),
            "sha256": provenance.sha256(lib),
            "imported_cells": imported,
            "expected_cells": want,
            "status": "pass" if imported == want else "fail",
        },
    )
    if imported != want:
        raise RuntimeError(f"extended library imported {imported}, expected {want}")
    rows, best = measure(names, out, lib, reqs)
    ref = witness_report(out)
    plots(out)
    tutorial_results = tutorials.verify(names, out, lib)
    data = summary(out, names, rows, best, ref, env, tutorial_results)
    if out == paths.results("m2"):
        showcase(out)
    print("M2 experimental flow:", data["experimental_flow_status"], flush=True)
    print(
        "Checkpoint ready:", data["checkpoint_ready"], "(see readiness.json; no tag is created)", flush=True
    )
    return 0 if data["experimental_flow_status"] == "pass" else 1
