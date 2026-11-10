"""Liberty in the tools (Option 1 handout, Table 5, step 9): Yosys and OpenSTA must load it, and the
six validated cells go into a copy of the HD Liberty to time Tutorial 4's SPM with OpenSTA.

OpenSTA runs from image dd2-sta (docker/build_sta.sh). SPM is not in the student pack: data/designs/spm.v
is the same design from the OpenLane repository (Apache-2.0).
"""
import re
import subprocess
from pathlib import Path

from dd2 import mapping, paths, tools

from .characterize import _block

IMAGE = "dd2-sta"
CLOCK_NS = 10.0            # OpenLane's spm config


def swap_cells(lib: str, groups: dict, tmpl: str) -> str:
    """lib with each named cell group replaced, and the tables' template added before the first cell."""
    for name, text in groups.items():
        key = f'cell ("{name}")'
        if key not in lib:
            raise ValueError(f"{name} is not in the library")
        start = lib.index(key)
        body = _block(lib, start)
        end = lib.index(body, start) + len(body)
        line = lib.rfind("\n", 0, start) + 1
        lib = lib[:line] + text + lib[end:].lstrip("\n")
    first = lib.index("cell (")
    line = lib.rfind("\n", 0, first) + 1
    return lib[:line] + tmpl + lib[line:]


def parse_slack(log: str):
    m = re.search(r"^WS (-?[\d.eE+-]+)", log, re.M)
    return float(m.group(1)) if m else None


def _sta(workdir: Path, script: str, name: str) -> tuple:
    (workdir / f"{name}.tcl").write_text(script)
    p = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{workdir.resolve()}:/w", "-w", "/w", IMAGE,
                        "sta", "-no_init", "-exit", f"{name}.tcl"], capture_output=True, text=True, timeout=600)
    log = p.stdout + p.stderr
    (workdir / f"{name}.log").write_text(log)
    return p.returncode, log


def load_liberty(lib: Path, workdir: Path) -> dict:
    """Table 5, Liberty syntax: no errors in Yosys or OpenSTA."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    local = workdir / Path(lib).name
    if Path(lib).resolve() != local.resolve():
        local.write_text(Path(lib).read_text())
    y = subprocess.run(tools.yosys_cmd() + ["-q", "-p", f"read_liberty -lib {local}"], capture_output=True, text=True)
    code, log = _sta(workdir, f"read_liberty {local.name}\nputs LOADED\n", f"load_{local.stem}")
    bad = re.findall(r"^(?:Error|Warning)[^\n]*", log, re.M)
    return {"yosys": "pass" if y.returncode == 0 else "fail", "yosys_error": y.stderr[-300:] if y.returncode else "",
            "opensta": "pass" if code == 0 and "LOADED" in log and not any(b.startswith("Error") for b in bad) else "fail",
            "opensta_messages": bad[:5]}


def time_design(lib: Path, verilog: Path, top: str, workdir: Path, script: str = "A") -> dict:
    """Map the design on lib, then time it with OpenSTA on the same lib."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    local_lib = workdir / "lib.lib"
    local_lib.write_text(Path(lib).read_text())
    y = mapping.yosys_script(str(Path(verilog).resolve()), top, str(local_lib), script, sv=True)
    p = subprocess.run(tools.yosys_cmd() + ["-q", "-p", y + f"; write_verilog -noattr -noexpr {workdir / 'netlist.v'}"],
                       capture_output=True, text=True, cwd=workdir, timeout=900)
    (workdir / "yosys.log").write_text(p.stdout + p.stderr)
    if p.returncode:
        return {"status": "fail", "error": p.stderr[-400:]}
    text = (f"read_liberty lib.lib\nread_verilog netlist.v\nlink_design {top}\ncreate_clock -period {CLOCK_NS} [get_ports clk]\n"
            f"report_checks -path_delay max -format full\nputs \"WS [expr {{[sta::worst_slack_cmd max] * 1e9}}]\"\n")
    code, log = _sta(workdir, text, "sta")
    ws = parse_slack(log)
    cells = len(re.findall(r"^\s*sky130_fd_sc_hd__\w+ ", (workdir / "netlist.v").read_text(), re.M))
    return {"status": "pass" if ws is not None else "fail", "worst_slack_ns": ws, "clock_ns": CLOCK_NS,
            "worst_delay_ns": round(CLOCK_NS - ws, 4) if ws is not None else None, "cells": cells, "script": script,
            "report": str(paths.rel(workdir / "sta.log"))}
