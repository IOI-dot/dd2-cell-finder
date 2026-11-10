#!/usr/bin/env python3
"""Import published M3 evidence from the WSL checkout that ran the experiment."""

import argparse
import csv
import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGNS = {
    "cpu8", "dsp8", "arlet6502", "uart_apb", "risc8", "fir10",
    "spm", "multiplier", "pic16", "p16c5x",
}
REQUIRED_MAPPING_FILES = ("mapping.log", "mapped.v", "cec.log", "equivalence.json", "timing.log")


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def safe_response_file(directory, value):
    path = (directory / value).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        raise ValueError(f"Missing or external response file: {value}")
    return path


def verify_mapping_tree(directory, label):
    with (directory / f"table5_{label}.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    keys = {(row["design"], row["script"]) for row in rows}
    if len(rows) != 20 or keys != {(d, s) for d in DESIGNS for s in ("A", "B")}:
        raise ValueError(f"Incomplete mapping table: {directory}")
    for row in rows:
        for side in ("baseline", "extended"):
            if row[f"{side}_equivalence"] != "pass" or row[f"{side}_timing_status"] != "pass":
                raise ValueError(f"Mapping check failed: {directory} {row['design']} {row['script']} {side}")
            work = directory / "mapping" / row["design"] / side / row["script"]
            for name in REQUIRED_MAPPING_FILES:
                if not (work / name).is_file():
                    raise ValueError(f"Missing verification evidence: {work / name}")


def copy_evidence(source, dest):
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        if any(part.startswith(".") or part.startswith(("trial_", "curve_"))
               or part == "failed_trial" for part in rel.parts):
            continue
        if (not path.is_file() or path.is_symlink() or path.suffix in {".il", ".vvp", ".vcd"}
                or re.fullmatch(r"(gold|mapped|(gold|gate)_state(_named)?)\.json", path.name)
                or ".sqlite" in path.name):
            continue
        if path.stat().st_size > 50_000_000:
            raise ValueError(f"File exceeds the submission limit: {path}")
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="original repo or extracted WSL evidence directory")
    args = parser.parse_args()
    m3 = args.source.resolve() / "results/m3"
    estimated = m3 / "estimated-best"
    real = m3 / "real"
    responses = m3 / "cellweaver-responses"
    try:
        requests = read_json(estimated / "requests.json")
        if requests != read_json(ROOT / "results/m3/estimated-best/requests.json"):
            raise ValueError("The WSL selection differs from the published M3 selection.")
        cells = read_json(real / "generator_cells.json")
        expected = {r["request_id"]: r["name"] for r in requests}
        returned = {r["request_id"]: r["name"] for r in cells}
        records = {r["request_id"]: r for r in read_json(responses / "responses.json")}
        if len(requests) != 10 or returned != expected or set(records) != set(expected):
            raise ValueError("The M3 run and response bundle must cover the same ten requests.")
        for cell in cells:
            response = records[cell["request_id"]]
            if response["status"] != "pass" or response["cell"] != cell["name"]:
                raise ValueError(f"Invalid generator response for {cell['name']}")
            for value in response["files"].values():
                safe_response_file(responses, value)
            if digest(safe_response_file(responses, response["files"]["liberty"])) != cell["liberty_sha256"]:
                raise ValueError(f"Liberty hash mismatch for {cell['name']}")
        for directory, label in ((estimated, "estimated"), (real, "real"), (real / "sensitivity", "sensitivity")):
            verify_mapping_tree(directory, label)
        for path in (estimated / "baseline_mappings.json", estimated / "hd_extended_estimated.lib",
                     real / "hd_extended_real.lib", real / "cell_curve.pdf", real / "sensitivity.json",
                     real / "tutorial_simulations.json", m3 / "real-run.log"):
            if not path.is_file():
                raise ValueError(f"Missing M3 deliverable: {path}")

        for directory in (estimated, real):
            copy_evidence(directory, ROOT / "results/m3" / directory.name)
        copy_evidence(responses, ROOT / "libs/cellweaver")
        shutil.copy2(m3 / "real-run.log", ROOT / "results/m3")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Import stopped: {error}\n")
    print("Imported all ten CellWeaver responses and the estimated, real and sensitivity evidence.")


if __name__ == "__main__":
    main()
