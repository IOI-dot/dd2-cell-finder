"""Reporting: the figures, readiness.json and summary.md, the TA_M2/ folder, and the M1 summary.
Nothing here measures: it reads what the steps saved."""

import csv
import json
import re
from pathlib import Path

from dd2 import designs, paths, provenance

from . import reference as table4, tutorials


def plots(out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with (out / "area_model_fit.csv").open() as f:
        fit = list(csv.DictReader(f))
    fig, ax = plt.subplots(figsize=(6, 5))
    x = [float(r["area_um2"]) for r in fit]
    y = [float(r["loo_predicted_um2"]) for r in fit]
    for label in ["single stage", "multiple stages"]:
        rows = [i for i, r in enumerate(fit) if (int(r["stages"]) == 1) == (label == "single stage")]
        ax.scatter([x[i] for i in rows], [y[i] for i in rows], label=label, alpha=0.75)
    hi = max(x + y)
    ax.plot([0, hi], [0, hi], color="black", linestyle="--", linewidth=1)
    ax.set(
        xlabel="HD area (um²)",
        ylabel="Held-out predicted area (um²)",
        title="Area model: leave-one-out validation",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "area_model_validation.png", dpi=180)
    plt.close(fig)
    with (out / "best_of_both_estimated.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if r["design"] != "TOTAL"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar([r["design"] for r in rows], [float(r["reduction_pct"]) for r in rows], color="#236b8e")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set(ylabel="Area reduction (%)", title="Measured best-of-both savings: estimated cells")
    fig.tight_layout()
    fig.savefig(out / "area_reduction_estimated.png", dpi=180)
    plt.close(fig)
    cs = json.loads((out / "candidates.json").read_text())
    cs = [r for r in cs if r["eligible"]][:10]
    if cs:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh([r["key"] for r in cs][::-1], [r["estimated_best_of_both_saving_um2"] for r in cs][::-1])
        ax.set(
            xlabel="Estimated aggregate saving (um²)",
            title="Candidate ranking heuristic; overlap may change savings",
        )
        fig.tight_layout()
        fig.savefig(out / "candidate_ranking.png", dpi=180)
        plt.close(fig)


def summary(out, names, rows, best, reference, env, tutorial_results=None):
    valid = all(r["baseline_equivalence"] == "pass" and r["extended_equivalence"] == "pass" for r in rows)
    timing_ok = all(
        r["baseline_timing_status"] == "pass" and r["extended_timing_status"] == "pass" for r in rows
    )
    checks = {
        "mapping_equivalence": valid,
        "timing_runs": timing_ok,
        "reference_table4_agrees": reference["status"] == "match",
        "reference_table4_resolved": reference["status"] in {"match", "TA accepted recorded difference"},
        "overview_tool_versions": all(env["overview_versions"].values()),
        "all_six_required_designs": set(names) >= {d.name for d in designs.required()},
    }
    tutorial_status = {
        n: (tutorial_results or {}).get(
            n, {"rtl_supplied": tutorials.supplied(n), "mapping_and_gate_simulation_verified": False}
        )
        for n in tutorials.SPECS
    }
    checks["tutorial_designs_mapped_and_simulated"] = all(
        r["mapping_and_gate_simulation_verified"] for r in tutorial_status.values()
    )
    if not checks["tutorial_designs_mapped_and_simulated"]:
        valid = False
    remaining = []
    if not checks["mapping_equivalence"]:
        remaining.append("Every baseline and extended mapping must pass CEC.")
    if not checks["timing_runs"]:
        remaining.append("Every OpenSTA run must pass without tool errors.")
    if not checks["all_six_required_designs"]:
        remaining.append("All six required benchmark designs must be measured.")
    if not checks["tutorial_designs_mapped_and_simulated"]:
        remaining.append(
            "Original tutorial RTL and all four A/B baseline/extended gate simulations must pass."
        )
    if not checks["overview_tool_versions"]:
        remaining.append("Overview minimum tool versions must be satisfied.")
    if not checks["reference_table4_resolved"]:
        remaining.append(
            "Table 4 has a missing or unresolved reference result."
        )
    data = {
        "experimental_flow_status": "pass" if valid and timing_ok else "fail",
        "checkpoint_ready": all(ok for name, ok in checks.items() if name != "reference_table4_agrees"),
        "checks": checks,
        "table4_disposition": reference["status"],
        "tutorial_inputs": tutorial_status,
        "remaining": remaining,
        "final_only": [
            "real-cell generator results",
            "final greedy selection",
            "30-percent experiment",
            "final reports",
        ],
        "written": provenance.now(),
    }
    provenance.write_json(out / "readiness.json", data)
    lines = [
        "# Option 2 M2 measured evidence",
        "",
        f'Experimental flow: **{data["experimental_flow_status"]}**.',
        f'Checkpoint ready: **{data["checkpoint_ready"]}**. See `readiness.json` for blockers.',
        "",
        "Area values below use estimated cells; their timing/capacitances are placeholders.",
        "",
        "| Design | Baseline best (um²) | Extended best (um²) | Reduction |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f'| {r["design"]} | {r["baseline_best_um2"]:.4f} | {r["extended_best_um2"]:.4f} | {r["reduction_pct"]:.3f}% |'
        for r in best
    ]
    lines += [
        "",
        "## Evidence",
        "",
        "- `ranked_candidates.csv`, `redundancy_report.csv`, `candidate_occurrences.jsonl.gz`",
        "- `area_model.json`, `area_model_fit.csv`, `area_model_validation.png`",
        "- `requests/`, `requests.json`, `selection.json`, `extended_library.json`",
        "- `table5_estimated.csv`, `best_of_both_estimated.csv`, `area_reduction_estimated.png`",
        "- `mapping/`: scripts, netlists, hashes, mapping/CEC/sequential-equivalence/timing logs",
        "- `reference_count_review.json`, `reference_count_witnesses.csv`",
        "",
        "## Limitations",
        "",
        "- Ranking is a heuristic; the remapped area, not occurrence frequency, is the measured result.",
        "- Cost features describe explicit Boolean realizations, not transistor extraction from installed HD cells.",
        f'- Table 4 disposition: {reference["status"]}. See reference_count_review.json.',
        "- Tutorial sources/testbenches are unchanged earlier submissions, installed outside git. GLS is functional, with no SDF or timing-check claim.",
        "- TOTAL and the ranking objective cover the six required benchmark designs; tutorial rows are shown separately.",
        "- Final reports, real-cell results and sensitivity/greedy experiments are not M2 outputs.",
    ]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return data


def showcase(out):
    """Small TA-facing copies of existing evidence; never recompute measurements."""
    import shutil

    out = Path(out)
    dest = paths.ROOT / "TA_M2"
    copies = {
        "figures/01_area_model_validation.png": out / "area_model_validation.png",
        "figures/02_candidate_ranking.png": out / "candidate_ranking.png",
        "figures/03_measured_area_reduction.png": out / "area_reduction_estimated.png",
        "tables/01_m1_reference_table.csv": paths.results("m1", "table1.csv"),
        "tables/02_ranked_candidates.csv": out / "ranked_candidates.csv",
        "tables/03_area_model_fit.csv": out / "area_model_fit.csv",
        "tables/04_table5_estimated.csv": out / "table5_estimated.csv",
        "tables/05_best_of_both.csv": out / "best_of_both_estimated.csv",
        "tables/06_tutorial_aigs_and_cuts.csv": out / "tutorial_aig_cuts.csv",
        "TABLE4_CLARIFICATION.md": out / "reference_count_question.md",
        "table4_witnesses.csv": out / "reference_count_witnesses.csv",
        "readiness.json": out / "readiness.json",
    }
    for name in ["tests.log", "tool_versions.log"]:
        p = paths.results("validation", name)
        if p.is_file():
            copies["validation/" + name] = p
    missing = [str(src) for src in copies.values() if not src.is_file()]
    if missing:
        raise ValueError("Cannot prepare complete TA folder; missing: " + ", ".join(missing))
    model = json.loads((out / "area_model.json").read_text())
    ready = json.loads((out / "readiness.json").read_text())
    library = json.loads((out / "extended_library.json").read_text())
    with (out / "best_of_both_estimated.csv").open() as f:
        best = list(csv.DictReader(f))
    with paths.results("m1", "cuts/summary.csv").open() as f:
        cuts = list(csv.DictReader(f))
    checks = {}
    for label, pattern in [
        ("CEC", "mapping/**/equivalence.json"),
        ("OpenSTA", "mapping/**/timing.json"),
        ("Tutorial simulations", "tutorial_simulations/**/simulation.json"),
    ]:
        records = [json.loads(p.read_text()) for p in out.glob(pattern)]
        checks[label] = f'{sum(r.get("status")=="pass" for r in records)}/{len(records)} pass'
    manifest = []
    for rel, src in copies.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, p)
        manifest.append({"copy": rel, "source": paths.rel(src), "sha256": provenance.sha256(src)})
    provenance.write_json(dest / "evidence_sources.json", manifest)
    lines = [
        "# GB4 — Option 2, Milestone 2",
        "",
        "**Start here for the TA meeting.** Figures and tables are copies of the saved run; full evidence is in [results/m2](../results/m2/).",
        "",
        f'Experimental flow: **{ready["experimental_flow_status"]}**. Full checkpoint ready: **{ready["checkpoint_ready"]}**.',
        f'Table 4: {ready["table4_disposition"]}. The recorded counts remain visible.',
        "See [the clarification and six examples](TABLE4_CLARIFICATION.md).",
        "",
        "## What was verified",
        "",
        f'- M1 cuts independently checked: {sum(int(r["checked"]) for r in cuts):,}.',
        f'- Extended Liberty import: {library["imported_cells"]}/{library["expected_cells"]} cells.',
        f'- Area model: {model["training_cells"]} HD x1 cells; leave-one-out mean absolute percentage error {model["loo_mean_absolute_percent_error"]:.2f}%.',
    ]
    lines += [f"- {label}: {status}." for label, status in checks.items()]
    testlog = paths.results("validation", "tests.log")
    if testlog.is_file():
        summaries = [
            line.strip() for line in testlog.read_text().splitlines() if re.search(r"\b\d+ passed\b", line)
        ]
        if summaries:
            lines.append("- Tests: " + summaries[-1] + ". See [saved test log](validation/tests.log).")
    lines += [
        "",
        "## Measured best-of-both area",
        "",
        "| Design | Baseline (µm²) | Extended (µm²) | Area reduction |",
        "|---|---:|---:|---:|",
    ]
    for r in best:
        lines.append(
            f'| {r["design"]} | {float(r["baseline_best_um2"]):.4f} | {float(r["extended_best_um2"]):.4f} | {float(r["reduction_pct"]):.4f}% |'
        )
    lines += [
        "",
        "TOTAL covers the six required benchmarks. Tutorial rows are separate. A negative reduction means area increased.",
        "M1 reproduces the Yosys 0.33 reference table; M2 uses the newer recorded toolchain with identical A/B commands on each side.",
        "These areas use estimated cells. New-cell timing/capacitance values are placeholders; OpenSTA results are pre-layout comparisons.",
        "",
        "## Figures",
        "",
        "### 1. Area-model validation",
        "",
        "Held-out predictions against the HD cell areas; the dashed line represents exact predictions.",
        "",
        "![Area-model validation](figures/01_area_model_validation.png)",
        "",
        "### 2. Candidate ranking",
        "",
        "Heuristic predicted savings used for ranking. Overlapping cuts and actual remapping can change the outcome.",
        "",
        "![Candidate ranking](figures/02_candidate_ranking.png)",
        "",
        "### 3. Measured area reduction",
        "",
        "Measured from the baseline and extended mappings, taking the smaller A/B area on each side.",
        "",
        "![Measured area reduction](figures/03_measured_area_reduction.png)",
        "",
        "## Tables",
        "",
    ]
    lines += [f"- [{Path(rel).name}]({rel})" for rel in copies if rel.startswith("tables/")]
    lines += [
        "",
        "## Still open",
        "",
        *["- " + s for s in ready["remaining"]],
        "",
        "Final milestone: real generator cells, final greedy selection, real-area reruns, cell-by-cell curve, 30% experiment, final reports and full unseen-design demo.",
        "",
        "Copies are refreshed by `make ta` and after `make m2`. `evidence_sources.json` records their source hashes.",
    ]
    (dest / "README.md").write_text("\n".join(lines) + "\n")
    print("TA meeting folder: TA_M2/README.md", flush=True)
    return dest


def m1_summary():
    m1 = paths.results("m1")
    checks = []

    def load(name):
        return json.loads((m1 / name).read_text())

    with (m1 / "table1.csv").open() as f:
        table = list(csv.DictReader(f))
    with (m1 / "cuts/summary.csv").open() as f:
        cuts = list(csv.DictReader(f))
    st = load("redundancy/self_test.json")
    hd = load("hd_classes.json")
    checks = [
        ("Table 1", len(table) == 12 and all(r["matches_handout"] == "yes" for r in table)),
        ("AIG manifest", load("aigs/manifest.json")["status"] == "pass"),
        (
            "Cuts checked",
            len(cuts) == 12
            and all(
                r["status"] == "pass" and int(r["failures"]) == 0 and int(r["cuts"]) == int(r["checked"])
                for r in cuts
            ),
        ),
        ("HD class table", hd["run"]["status"] == "pass"),
        ("HD cells recognized", st["hd_cells_exists"] == st["hd_cells_total"]),
        ("Table 4 resolved", table4.disposition(st["table4"]) in {"match", "TA accepted recorded difference"}),
    ]
    text = ["# Option 2 M1 evidence", "", "| Requirement | Status |", "|---|---|"]
    text += [f'| {n} | {"pass" if ok else "OPEN / FAIL"} |' for n, ok in checks]
    text += [
        "",
        f'Checked cuts: {sum(int(r["checked"]) for r in cuts)}.',
        f'Table 4: {table4.disposition(st["table4"])}. The original counts are preserved.',
    ]
    (m1 / "summary.md").write_text("\n".join(text) + "\n")
    print("\n".join(text))
    return 0 if all(ok for _, ok in checks) else 1
