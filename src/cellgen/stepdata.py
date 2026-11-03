"""Real flow outputs as plain data for the studio's step views.

Nothing here decides a result: the checks in flow.py do. These functions only read what the tools
produced, so that a person can see what each step did.
"""
import re
import subprocess
from pathlib import Path


def switch_rows(net, tt: int) -> list:
    """Every input row: the input values, whether the last stage's pull-up and pull-down conduct,
    the output they give, and the output the truth table asks for."""
    stages = range(len(net.stages)) if net.stages else [None]
    out_rows = []
    for row in range(1 << len(net.inputs)):
        val = {name: (row >> k) & 1 for k, name in enumerate(net.inputs)}
        inputs, up, down = dict(val), False, False
        for s in stages:
            out = net.stages[s].out if s is not None else net.output
            parent = {}

            def find(x):
                parent.setdefault(x, x)
                while parent[x] != x:
                    x = parent[x]
                return x

            for t in net.transistors:
                if (s is None or t.stage == s) and val.get(t.gate) == (1 if t.kind == "n" else 0):
                    parent[find(t.drain)] = find(t.source)
            up, down = find(out) == find("VPWR"), find(out) == find("VGND")
            val[out] = 1 if up else 0
        out_rows.append({"row": row, "inputs": inputs, "up": up, "down": down, "y": 1 if up else 0, "expected": (tt >> row) & 1})
    return out_rows


def orders(candidates) -> list:
    """Each candidate gate order, with the diffusion nets either side of each gate in both rows."""
    def slots(o, row):
        return [{"left": s.left, "right": s.right} if s else None for s in o.slots[row]]
    return [{"gates": list(o.gates), "breaks": o.breaks, "p": slots(o, "p"), "n": slots(o, "n")} for o in candidates]


def devices(netlist: str) -> list:
    """The transistors in an extracted or schematic netlist."""
    out = []
    for m in re.finditer(r"^(X\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+\S+\s+sky130_fd_pr__([np])fet\S*(.*)$", netlist, re.M):
        name, drain, gate, source, kind, rest = m.groups()
        params = dict(re.findall(r"\b([wl])=([\d.]+)", rest))
        out.append({"name": name, "type": kind, "gate": gate, "drain": drain, "source": source,
                    "w": float(params.get("w", 0)), "l": float(params.get("l", 0))})
    return out


def lvs_counts(report: str) -> dict:
    """Netgen's device and net counts for the two circuits, from its last summary table."""
    dev = re.findall(r"Number of devices:\s*(\d+)\s*\|Number of devices:\s*(\d+)", report)
    net = re.findall(r"Number of nets:\s*(\d+)\s*\|Number of nets:\s*(\d+)", report)
    if not dev or not net:
        return {}
    return {"layout": {"devices": int(dev[-1][0]), "nets": int(net[-1][0])},
            "schematic": {"devices": int(dev[-1][1]), "nets": int(net[-1][1])}}


def rc_stats(netlist: str) -> dict:
    """Parasitics by net: series-resistor fragments of a net share its name before the dot."""
    base = lambda node: node.split(".")[0]                                  # noqa: E731
    ohms, ff = {}, {}
    res = re.findall(r"^R\S+\s+(\S+)\s+(\S+)\s+([\d.eE+-]+)", netlist, re.M)
    caps = re.findall(r"^C\S+\s+(\S+)\s+(\S+)\s+([\d.eE+-]+)f", netlist, re.M)
    for a, _, value in res:
        ohms[base(a)] = ohms.get(base(a), 0) + float(value)
    for a, b, value in caps:
        for node in {base(a), base(b)}:
            ff[node] = ff.get(node, 0) + float(value)
    nets = [{"net": k, "ohms": round(ohms.get(k, 0), 3), "ff": round(ff.get(k, 0), 5)} for k in sorted(ohms.keys() | ff.keys())]
    return {"resistors": len(res), "capacitors": len(caps), "nets": nets}


def icarus_rows(work: Path) -> dict:
    """The outputs the compiled Verilog testbench prints: row number to value."""
    sim = Path(work) / "model_sim"
    if not sim.is_file():
        return {}
    r = subprocess.run(["vvp", str(sim)], capture_output=True, text=True)
    return {int(a): b for a, b in re.findall(r"ROW (\d+) ([01xz])", r.stdout)}
