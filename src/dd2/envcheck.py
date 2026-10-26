"""make check: tool versions, PDK and supplied inputs. Writes results/m1/environment.json."""
import os
import re
import sys
from pathlib import Path

from . import designs, paths, provenance, tools

REDUCED, USABLE = "hd_reduced.lib", "hd_usable.lib"
EXPECTED_CELLS = {REDUCED: 189, USABLE: 307}
TABLE1_YOSYS = designs.HANDOUT_YOSYS


def liberty_import_count(lib: Path, log: Path) -> int | None:
    code, _ = tools.run(tools.yosys_cmd() + ["-p", f"read_liberty -lib {lib}"], log, timeout=600)
    m = re.search(r"Imported (\d+) cell types", log.read_text())
    return int(m.group(1)) if code == 0 and m else None


def pdk_version(pdk: Path) -> str:
    """ciel installs each PDK under versions/<commit>; record that commit."""
    # Inside the dd2-flow container the PDK is a plain mount; the Makefile passes the host path.
    real = os.environ.get("DD2_PDK_REALPATH") or str(Path(pdk).resolve())
    m = re.search(r"versions/([0-9a-f]{7,40})", real)
    return f"ciel {m.group(1)}" if m else "unknown (not a ciel install)"


def check(given: Path, pdk: Path, out: Path) -> int:
    problems, notes = [], []
    env = {"tools": tools.versions(), "given": paths.rel(given), "pdk": paths.rel(pdk),
           "pdk_version": pdk_version(pdk)}

    if sys.version_info < (3, 11):
        problems.append(f"Python {sys.version.split()[0]} is older than 3.11; run make setup")
    if not env["tools"]["yosys"]:
        problems.append("yosys not found on PATH (or $DD2_YOSYS)")
    elif TABLE1_YOSYS not in env["tools"]["yosys"].split()[1]:
        notes.append(f"yosys is {env['tools']['yosys'].split()[1]}, not {TABLE1_YOSYS}: Table 1 will "
                     "differ from the handout; use `make m1-docker` (Linux Yosys 0.33) for evidence")
    if not env["tools"]["iverilog"]:
        problems.append("iverilog not found")

    needed = [given / REDUCED, given / USABLE, given / "scripts/map.sh"]
    needed += [given / "designs" / f"{d.name}.v" for d in designs.ALL]
    missing = [p for p in needed if not p.is_file()]
    if missing:
        problems.append("missing supplied files (run make setup, GIVEN=<pack>/given): "
                        + ", ".join(str(p) for p in missing))

    full = paths.full_hd_lib(pdk)
    if full.is_file():
        env["full_hd_lib"] = {"path": paths.rel(full), "sha256": provenance.sha256(full),
                              "cells": len(re.findall(r"\n\s*cell\s*\(", full.read_text()))}
    else:
        problems.append(f"full HD Liberty not found at {full} (PDK_ROOT must contain sky130A)")

    env["liberty_import"] = {}
    for name, want in EXPECTED_CELLS.items():
        lib = given / name
        if not lib.is_file() or not env["tools"]["yosys"]:
            continue
        got = liberty_import_count(lib, paths.build("check", f"read_{name}.log"))
        env["liberty_import"][name] = got
        if got != want:
            problems.append(f"Yosys imported {got} cell types from {name}, expected {want}")

    if not env["tools"]["sta"]:
        notes.append("OpenSTA (sta) missing: required from M2 (worst delay in Table 5), not for M1")
    notes.append("ngspice stress test runs in the dd2-layout-tools image (Option 1); not checked here")

    env["problems"], env["notes"] = problems, notes
    env["status"] = "fail" if problems else "pass"
    env["checked"] = provenance.now()
    provenance.write_json(out, env)
    for p in problems:
        print(f"FAIL  {p}")
    for n in notes:
        print(f"NOTE  {n}")
    print(f"check: {env['status']} ({paths.rel(out)})")
    return 1 if problems else 0
