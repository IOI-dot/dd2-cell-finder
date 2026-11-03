"""The course tools (Magic, Netgen, ngspice) in the dd2-layout-tools image.

The PDK is mounted read-only at /pdk/sky130A and the work directory read-write at /w; nothing else
is visible to the tools. Every call keeps its raw log beside its result.
"""
import json
import os
import re
import subprocess
import time
from itertools import count
from pathlib import Path

from dd2 import paths

IMAGE = "dd2-layout-tools"
PDK = "/pdk/sky130A"
MAGICRC = f"{PDK}/libs.tech/magic/sky130A.magicrc"
NETGEN_SETUP = f"{PDK}/libs.tech/netgen/sky130A_setup.tcl"
HD_GDS = f"{PDK}/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"
HD_SPICE = f"{PDK}/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice"
MODELS = f"{PDK}/libs.tech/ngspice/sky130.lib.spice"


_steps = count(1)
LABEL = "dd2.run"                      # containers of one agent run, so that cancelling can find them


def trace(step: str, title: str, state: str = "ok", detail: str = "", stage: str = "", data=None) -> None:
    """One line of live progress on stdout, read by the agent's tool wrapper. Off unless DD2_TRACE is set.
    stage names the pipeline step in the web app; data is real output for its tables and graphs."""
    if os.environ.get("DD2_TRACE"):
        print("@@ " + json.dumps({"id": step, "title": title, "state": state, "detail": detail, "stage": stage, "data": data}), flush=True)


def _title(argv, log: Path) -> str:
    names = {"magic": "Magic", "netgen": "Netgen", "ngspice": "ngspice"}
    return f"{names.get(argv[0], argv[0])}: {Path(log).stem.replace('_', ' ')}"


STEPS = {"drc_standalone": ("drc", "Magic DRC: the cell alone"), "drc_side": ("abutment", "Magic DRC: beside HD cells"),
         "drc_mirror": ("abutment", "Magic DRC: mirrored"), "drc_self": ("abutment", "Magic DRC: next to itself"),
         "drc_flip": ("abutment", "Magic DRC: flipped onto a shared rail"), "extract": ("extract", "Magic: extract the circuit"),
         "lvs_schematic": ("lvs", "Netgen: LVS against the schematic"), "extract_rc": ("rc", "Magic: extract R and C"),
         "lvs_rc": ("rc_lvs", "Netgen: RC-LVS"), "spice_dc": ("spice", "ngspice: DC, every input row"),
         "spice_tran": ("spice", "ngspice: transient, every toggle"), "lvs_installed": ("lvs", "Netgen: LVS against the installed cell"),
         "extract_installed_rc": ("rc", "Magic: extract the installed cell")}


def run(workdir: Path, argv, log: Path, timeout=1800) -> int:
    pdk = Path(paths.ROOT / "pdk").resolve()
    cmd = ["docker", "run", "--rm", "--network", "none", "--label", f"{LABEL}={os.environ.get('DD2_RUN', 'none')}", "-e", f"PDK_ROOT=/pdk",
           "-v", f"{pdk}:{PDK}:ro", "-v", f"{Path(workdir).resolve()}:/w", "-w", "/w", IMAGE, *argv]
    stage, title = STEPS.get(Path(log).stem, ("", _title(argv, log)))
    step, t0 = f"tool{next(_steps)}", time.time()
    call = {"command": " ".join(str(a) for a in argv)[:400], "log": Path(log).name}
    trace(step, title, "running", call["command"][:140], stage, call)
    with open(log, "w") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        try:
            code = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            f.write("\n[cellgen] timeout\n")
            code = 124
    trace(step, title, "ok" if code == 0 else "bad", f"exit {code} in {time.time() - t0:.1f} s", stage, call)
    return code


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
    # every reason Magic prints, "{text (rule)} {{boxes}}": keep the rule tag, or the whole text if
    # there is none, so no error can slip past a rule-name filter
    rules = []
    for reason in re.findall(r"\{([^{}]+)\}\s*\{\{", why.group(1)) if why else []:
        tag = re.search(r"\(([^()]+)\)\s*$", reason.strip())
        rules.append(tag.group(1) if tag else reason.strip())
    bb = re.search(r"DRC_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", log)
    bbox = [round(int(v) * 0.005, 3) for v in bb.groups()] if bb else None   # Magic internal unit 5 nm
    # `drc list count total` can say 0 for an error inside a subcell that `listall why` does report:
    # the larger of the two counts, so that a row fixture cannot hide one
    boxes = len(re.findall(r"\{-?\d+ -?\d+ -?\d+ -?\d+\}", why.group(1))) if why else 0
    return {"errors": max(int(m.group(1)), boxes) if m else None, "rules": sorted(set(rules)), "bbox_um": bbox}


def extract_script(gds: str, cell: str, rc: bool = False) -> str:
    """Magic extraction: plain LVS netlist, or an RC netlist with every capacitance and resistor.
    `extresist simplify off` keeps the resistors: by default Magic drops every net whose R is small
    next to the transistors' on-resistance, and its `tolerance` option no longer does anything."""
    lines = [f"gds read {gds}", f"load {cell}", "select top cell", "extract path /w"]
    lines += ["extract do resistance"] if rc else []
    lines += ["extract all"]
    if rc:
        lines += ["ext2sim labels on", "ext2sim", "extresist simplify off", "extresist all",
                  "ext2spice lvs", "ext2spice cthresh 0", "ext2spice extresist on",
                  f"ext2spice -p /w -o /w/{cell}_rc.spice"]
    else:
        lines += ["ext2spice lvs", f"ext2spice -p /w -o /w/{cell}.spice"]
    return "\n".join(lines)


def count_caps_once(netlist: str, substrate: str = "VNB") -> str:
    """extresist writes each net's substrate capacitance twice: whole on the net, and again in parts
    on its subnodes (A.n0, A.t1). The parts stay where they are, and the net keeps the rest, so the
    total is what the .ext file says."""
    pat = re.compile(rf"^(C\S*) (\S+) {substrate} ([\d.e+-]+)f$")
    parts = {}
    for line in netlist.splitlines():
        m = pat.match(line)
        if m and "." in m.group(2):
            base = m.group(2).split(".")[0]
            parts[base] = parts.get(base, 0.0) + float(m.group(3))
    out = []
    for line in netlist.splitlines():
        m = pat.match(line)
        if m and m.group(2) in parts:
            rest = max(0.0, float(m.group(3)) - parts[m.group(2)])
            line = f"{m.group(1)} {m.group(2)} {substrate} {rest:.6g}f"
        out.append(line)
    return "\n".join(out) + "\n"


def rc_for_lvs(netlist: str) -> str:
    """The RC netlist for RC-LVS: each resistor is a wire (its two nodes become one net), each
    capacitor is left out, so what Netgen compares is the devices and their connections."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    keep = []
    lines = netlist.splitlines()
    ports = set()
    for line in lines:
        if line.lower().startswith(".subckt"):
            ports = set(line.split()[2:])
        m = re.match(r"^R\S* (\S+) (\S+) ", line)
        if m:
            a, b = find(m.group(1)), find(m.group(2))
            if a != b:
                # a port's name survives
                parent[b if a in ports else a] = a if a in ports else b
    for line in lines:
        if re.match(r"^[RrCc]\S* ", line):
            continue
        if line.startswith("X"):
            f = line.split()
            f[1:5] = [find(n) for n in f[1:5]]
            line = " ".join(f)
        keep.append(line)
    return "\n".join(keep) + "\n"


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
