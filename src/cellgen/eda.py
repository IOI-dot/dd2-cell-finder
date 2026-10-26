"""The course tools (Magic, Netgen, ngspice) in the dd2-layout-tools image.

The PDK is mounted read-only at /pdk/sky130A and the work directory read-write at /w; nothing else
is visible to the tools. Every call keeps its raw log beside its result.
"""
import re
import subprocess
from pathlib import Path

from dd2 import paths

IMAGE = "dd2-layout-tools"
PDK = "/pdk/sky130A"
MAGICRC = f"{PDK}/libs.tech/magic/sky130A.magicrc"
NETGEN_SETUP = f"{PDK}/libs.tech/netgen/sky130A_setup.tcl"
HD_GDS = f"{PDK}/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"
HD_SPICE = f"{PDK}/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"
MODELS = f"{PDK}/libs.tech/ngspice/sky130.lib.spice"


def run(workdir: Path, argv, log: Path, timeout=1800) -> int:
    pdk = Path(paths.ROOT / "pdk").resolve()
    cmd = ["docker", "run", "--rm", "--network", "none", "-e", f"PDK_ROOT=/pdk",
           "-v", f"{pdk}:{PDK}:ro", "-v", f"{Path(workdir).resolve()}:/w", "-w", "/w", IMAGE, *argv]
    with open(log, "w") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        try:
            return subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            f.write("\n[cellgen] timeout\n")
            return 124


def magic(workdir: Path, script: str, name: str) -> tuple:
    """Run a Magic Tcl script; returns (exit code, log text)."""
    (Path(workdir) / f"{name}.tcl").write_text(script + "\nquit -noprompt\n")
    log = Path(workdir) / f"{name}.log"
    code = run(workdir, ["magic", "-dnull", "-noconsole", "-rcfile", MAGICRC, f"{name}.tcl"], log)
    return code, log.read_text()


def drc_script(gds_files, top: str, placements=None) -> str:
    """Full-style DRC of `top`; with placements [(cell, x_um, mirror)] build that row first.
    mirror: "" none, "x" (left-right), "y" (upside down, the shared-rail flip)."""
    lines = ["drc style drc(full)", f"gds read {HD_GDS}"] + [f"gds read {g}" for g in gds_files]
    if placements:
        lines += [f"load {top} -force"]
        for cell, x, mirror in placements:
            lines += [f"box {x}um 0um {x}um 0um", f"getcell {cell}"]
            if mirror == "x":
                lines.append("sideways")
            elif mirror == "y":
                lines.append("upsidedown")
    else:
        lines.append(f"load {top}")
    lines += ["select top cell", 'puts "DRC_BBOX [box values]"', "drc check", "drc catchup",
              'puts "DRC_COUNT [drc list count total]"', 'puts "DRC_WHY [drc listall why]"']
    return "\n".join(lines)


def parse_drc(log: str) -> dict:
    m = re.search(r"DRC_COUNT (\d+)", log)
    why = re.search(r"DRC_WHY (.*)", log)
    rules = re.findall(r"\(([a-zA-Z0-9_.]+)\)\}", why.group(1)) if why else []
    bb = re.search(r"DRC_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", log)
    bbox = [round(int(v) * 0.005, 3) for v in bb.groups()] if bb else None   # Magic internal unit 5 nm
    return {"errors": int(m.group(1)) if m else None, "rules": sorted(set(rules)), "bbox_um": bbox}


def extract_script(gds: str, cell: str, rc: bool = False) -> str:
    """Magic extraction: plain LVS netlist, or an RC netlist (extresist + all capacitances)."""
    lines = [f"gds read {gds}", f"load {cell}", "select top cell", "extract path /w", "extract all"]
    if rc:
        lines += ["ext2sim labels on", "ext2sim", "extresist tolerance 10", "extresist all",
                  "ext2spice lvs", "ext2spice cthresh 0", "ext2spice extresist on",
                  f"ext2spice -p /w -o /w/{cell}_rc.spice"]
    else:
        lines += ["ext2spice lvs", f"ext2spice -p /w -o /w/{cell}.spice"]
    return "\n".join(lines)


def netgen_lvs(workdir: Path, layout_spice: str, layout_cell: str, ref_spice: str, ref_cell: str,
               name: str) -> dict:
    out = f"{name}.out"
    log = Path(workdir) / f"{name}.log"
    run(workdir, ["netgen", "-batch", "lvs", f"{layout_spice} {layout_cell}", f"{ref_spice} {ref_cell}",
                  NETGEN_SETUP, out], log)
    text = (Path(workdir) / out).read_text() if (Path(workdir) / out).exists() else ""
    # Netgen can report "Circuits match uniquely." after mapping one pin onto another (e.g. layout A
    # onto schematic B): it marks that only with "**Mismatch**" in the pin table. Any such line, a
    # "do not match", or a property (W/L) error is a mismatch.
    match = "Circuits match uniquely." in text and "do not match" not in text and "**Mismatch**" not in text
    props = "Property errors were found" in text
    return {"result": "match" if match and not props else "mismatch", "report": out}
