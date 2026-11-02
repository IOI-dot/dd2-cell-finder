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


COURSE_IMAGE = "dd2-layout-tools"
STA_IMAGE = "dd2-sta"


def course_image() -> dict:
    """Option 1's tools in the course image, and its ngspice stress test (overview 5.1)."""
    import subprocess
    if subprocess.run(["docker", "image", "inspect", COURSE_IMAGE], capture_output=True).returncode:
        return {"status": "missing", "hint": "build it with `make o1-image` (Docker must be running)"}
    script = ("/opt/dd2/stress_test/check_stress.sh; echo STRESS_EXIT=$?; "
              "echo MAGIC=$(magic --version); echo NETGEN=$(netgen -batch quit 2>&1 | grep -m1 -o 'Netgen [0-9.]*')")
    p = subprocess.run(["docker", "run", "--rm", "--network", "none", COURSE_IMAGE, "sh", "-c", script],
                       capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    m = re.search(r"ngspice: (ngspice-[\d.]+)\s+\S+\s+sha256 ([0-9a-f]{64})", out)
    exit_code = re.search(r"STRESS_EXIT=(\d+)", out)
    return {"status": "pass" if exit_code and exit_code.group(1) == "0" else "fail",
            "stress_test": "pass" if "PASS: mobility stress is applied" in out else "fail",
            "ngspice": m.group(1) if m else None, "ngspice_sha256": m.group(2) if m else None,
            "magic": (re.search(r"MAGIC=(\S+)", out) or [None, None])[1],
            "netgen": (re.search(r"NETGEN=(.+)", out) or [None, None])[1]}


def opensta() -> str | None:
    """OpenSTA's version, from its image; there is no arm64 image to pull, see docker/build_sta.sh."""
    import subprocess
    p = subprocess.run(["docker", "run", "--rm", "--network", "none", STA_IMAGE, "sta", "-version"],
                       capture_output=True, text=True, timeout=120)
    return p.stdout.strip().splitlines()[-1] if p.returncode == 0 and p.stdout.strip() else None


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

    # Option 1 reads the HD cells' GDS, SPICE, LEF and Magic views from the PDK
    hd = Path(pdk) / "libs.ref/sky130_fd_sc_hd"
    env["hd_views"] = {}
    for view, f in (("gds", "gds/sky130_fd_sc_hd.gds"), ("spice", "spice/sky130_fd_sc_hd.spice"),
                    ("lef", "lef/sky130_fd_sc_hd.lef"), ("mag", "mag/sky130_fd_sc_hd__inv_1.mag")):
        present = (hd / f).is_file()
        env["hd_views"][view] = {"path": paths.rel(hd / f), "present": present,
                                 "sha256": provenance.sha256(hd / f) if present and view in ("gds", "spice") else None}
        if not present:
            problems.append(f"PDK view missing: {hd / f} (reinstall the sky130_fd_sc_hd library with ciel)")

    env["liberty_import"] = {}
    for name, want in EXPECTED_CELLS.items():
        lib = given / name
        if not lib.is_file() or not env["tools"]["yosys"]:
            continue
        got = liberty_import_count(lib, paths.build("check", f"read_{name}.log"))
        env["liberty_import"][name] = got
        if got != want:
            problems.append(f"Yosys imported {got} cell types from {name}, expected {want}")

    if os.environ.get("DD2_IN_CONTAINER"):
        notes.append("inside the dd2-flow container: the course image and its ngspice stress test "
                     "are checked by `make check` on the host")
    else:
        env["course_image"] = course_image()
        ci = env["course_image"]
        if ci["status"] != "pass":
            problems.append(f"course image {COURSE_IMAGE}: {ci.get('hint') or 'ngspice stress test failed'}")
        env["opensta"] = opensta()
        if not env["opensta"]:
            problems.append(f"OpenSTA missing: build image {STA_IMAGE} with `make o1-sta` (Table 5 needs it)")

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
