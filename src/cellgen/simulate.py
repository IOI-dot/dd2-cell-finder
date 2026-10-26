"""Functional simulation at transistor and model level (Option 1 handout, section 4.2).

Transistor level: ngspice (course image) on the RC-extracted netlist at TT, 1.8 V, 25 C. First the
DC operating point for every input combination; then a transient that visits every combination
and toggles each input once from every state, with the input slew and load of the HD table point
nearest 100 ps / 10 fF (read from the HD Liberty, slew indexed 20-80%). Y must be within 10% of the
correct rail before the next edge and must never cross VDD/2 while it should hold its value.

Model level: the Verilog model is simulated with Icarus for every input combination.
"""
import re
import subprocess
from pathlib import Path

from dd2 import paths

from . import eda

VDD = 1.8
SLOT_NS = 2.0


def hd_table_point(lib: Path | None = None, slew_target=0.1, load_target=0.01) -> dict:
    """Index values of HD's inv_1 tables nearest the targets, and HD's thresholds (from the file)."""
    text = Path(lib or paths.full_hd_lib()).read_text()
    cell = text[text.index('cell ("sky130_fd_sc_hd__inv_1")'):]
    i1 = [float(v) for v in re.search(r'index_1\("([^"]+)"\)', cell).group(1).split(",")]
    i2 = [float(v) for v in re.search(r'index_2\("([^"]+)"\)', cell).group(1).split(",")]
    th = {k: float(v) for k, v in re.findall(r"\n\s*(slew_(?:lower|upper)_threshold_pct_rise)\s*:\s*([\d.]+)", text)}
    return {"slew_ns": min(i1, key=lambda v: abs(v - slew_target)),
            "load_pf": min(i2, key=lambda v: abs(v - load_target)),
            "slew_lower_pct": th["slew_lower_threshold_pct_rise"],
            "slew_upper_pct": th["slew_upper_threshold_pct_rise"]}


def subckt_ports(netlist: str, cell: str) -> list:
    m = re.search(rf"^\.subckt\s+{re.escape(cell)}\s+(.*)$", netlist, re.M | re.I)
    if not m:
        raise ValueError(f"no .subckt {cell} in netlist")
    return m.group(1).split()


def sequence(n: int) -> list:
    """Visit every state and, from each, toggle each input once (returning to the state)."""
    seq = []
    for s in range(1 << n):
        for k in range(n):
            seq += [s, s ^ (1 << k)]
    return seq


def _header(cell, ports, netlist_in_container, point, title):
    conn = {"VNB": "VGND", "VPB": "VPWR"}
    return [f"* {cell}: {title} (generated)", f".lib {eda.MODELS} tt", f".include {netlist_in_container}",
            ".temp 25", f"VDD VPWR 0 {VDD}", "VSS VGND 0 0", f"CL Y 0 {point['load_pf']}p",
            f"X1 {' '.join(conn.get(p, p) for p in ports)} {cell}"]


def dc_testbench(cell: str, ports, inputs, netlist_in_container: str, point: dict) -> str:
    lines = _header(cell, ports, netlist_in_container, point, "DC operating point of every input row")
    lines += [f"V{name} {name} 0 dc 0" for name in inputs] + [".control"]
    for row in range(1 << len(inputs)):
        lines += [f"alter V{name} dc = {VDD * (row >> k & 1)}" for k, name in enumerate(inputs)]
        lines += ["op", "let vy = v(Y)", f"echo DC {row} $&vy"]
    return "\n".join(lines + [".endc", ".end"]) + "\n"


def testbench(cell: str, ports, inputs, netlist_in_container: str, point: dict) -> str:
    ramp = point["slew_ns"] / ((point["slew_upper_pct"] - point["slew_lower_pct"]) / 100)  # full ramp
    seq = sequence(len(inputs))
    lines = _header(cell, ports, netlist_in_container, point, "transient through every state and toggle")
    for k, name in enumerate(inputs):
        pts = [f"0 {VDD * (seq[0] >> k & 1)}"]
        for i in range(1, len(seq)):
            a, b = seq[i - 1] >> k & 1, seq[i] >> k & 1
            if a != b:
                t = i * SLOT_NS
                pts += [f"{t:.4f}n {VDD * a}", f"{t + ramp:.4f}n {VDD * b}"]
        lines.append(f"V{name} {name} 0 PWL({' '.join(pts)})")
    lines += [".control", "set wr_singlescale", "set wr_vecnames",
              f"tran 2p {len(seq) * SLOT_NS}n", "wrdata /w/tran.txt v(Y)", ".endc", ".end"]
    return "\n".join(lines) + "\n"


def check_waveform(times, ys, inputs, tt) -> list:
    """The two transient rules of section 4.2, slot by slot."""
    seq = sequence(len(inputs))
    errs = []
    for i, state in enumerate(seq):
        t0, t1 = i * SLOT_NS * 1e-9, (i + 1) * SLOT_NS * 1e-9
        want = VDD * ((tt >> state) & 1)
        window = [y for t, y in zip(times, ys) if t0 <= t < t1]
        end = [y for t, y in zip(times, ys) if t1 - 20e-12 <= t < t1]
        if end and abs(end[-1] - want) > 0.1 * VDD:
            errs.append(f"slot {i} state {state}: Y = {end[-1]:.3f} V before the next edge, want {want:.1f}")
        holding = i > 0 and ((tt >> seq[i - 1]) & 1) == ((tt >> state) & 1)
        if holding and window:
            crossed = min(window) < VDD / 2 if want else max(window) > VDD / 2
            if crossed:
                errs.append(f"slot {i} state {state}: Y crossed VDD/2 while holding {int(want > 0)}")
    return errs


def spice(workdir: Path, cell: str, netlist: Path, inputs, tt: int, point: dict | None = None) -> dict:
    """Run the DC and transient checks on `netlist` (inside workdir) in the course image."""
    point = point or hd_table_point()
    ports = subckt_ports(Path(netlist).read_text(), cell)
    inc = f"/w/{Path(netlist).name}"
    (Path(workdir) / "tb_dc.spice").write_text(dc_testbench(cell, ports, inputs, inc, point))
    (Path(workdir) / "tb_tran.spice").write_text(testbench(cell, ports, inputs, inc, point))
    (Path(workdir) / "tran.txt").unlink(missing_ok=True)
    eda.run(workdir, ["ngspice", "-b", "tb_dc.spice"], Path(workdir) / "spice_dc.log")
    code = eda.run(workdir, ["ngspice", "-b", "tb_tran.spice"], Path(workdir) / "spice_tran.log")
    log = (Path(workdir) / "spice_dc.log").read_text()
    dc = {int(r): float(v) for r, v in re.findall(r"^DC (\d+) ([-\d.eE+]+)", log, re.M)}
    errs = []
    for row in range(1 << len(inputs)):
        want = VDD * ((tt >> row) & 1)
        if row not in dc:
            errs.append(f"DC row {row}: no result")
        elif abs(dc[row] - want) > 0.1 * VDD:
            errs.append(f"DC row {row}: Y = {dc[row]:.3f} V, want {want:.1f}")
    tran = Path(workdir) / "tran.txt"
    if not tran.exists():
        errs.append(f"transient did not run (ngspice exit {code})")
    else:
        rows = [l.split() for l in tran.read_text().splitlines()[1:] if l.strip()]
        errs += check_waveform([float(r[0]) for r in rows], [float(r[1]) for r in rows], inputs, tt)
    return {"status": "pass" if not errs else "fail", "dc_volts": dc, "errors": errs[:20],
            "point": point, "slots": len(sequence(len(inputs))),
            "files": ["tb_dc.spice", "spice_dc.log", "tb_tran.spice", "spice_tran.log", "tran.txt"]}


def verilog_model(cell: str, inputs, tt: int) -> str:
    n = len(inputs)
    bits = 1 << n
    sel = ", ".join(reversed(inputs)) if n > 1 else inputs[0]
    return (f"// {cell}: functional model generated from the truth table (A = bit 0)\n"
            f"module {cell} ({', '.join(inputs)}, Y);\n"
            f"  input {', '.join(inputs)};\n  output Y;\n"
            f"  wire [{bits - 1}:0] T = {bits}'h{tt:0{max(1, bits // 4)}X};\n"
            f"  assign Y = T[{{{sel}}}];\nendmodule\n")


def verilog_check(model: Path, cell: str, inputs, tt: int, workdir: Path) -> dict:
    """Icarus: drive every input combination and compare Y with the truth table."""
    n = len(inputs)
    tb = [f"module tb; reg [{n - 1}:0] v; wire Y; integer i;",
          f"  {cell} dut ({', '.join(f'.{x}(v[{k}])' for k, x in enumerate(inputs))}, .Y(Y));",
          f"  initial begin for (i = 0; i < {1 << n}; i = i + 1) begin v = i; #1 $display(\"ROW %0d %b\", i, Y); end end",
          "endmodule"]
    (Path(workdir) / "tb_model.v").write_text("\n".join(tb) + "\n")
    out = Path(workdir) / "model_sim"
    p = subprocess.run(["iverilog", "-o", str(out), str(model), str(Path(workdir) / "tb_model.v")],
                       capture_output=True, text=True)
    if p.returncode:
        return {"status": "fail", "errors": [p.stderr.strip()]}
    r = subprocess.run(["vvp", str(out)], capture_output=True, text=True)
    got = {int(a): b for a, b in re.findall(r"ROW (\d+) ([01xz])", r.stdout)}
    errs = [f"row {i}: model gives {got.get(i)}, truth table {(tt >> i) & 1}"
            for i in range(1 << n) if got.get(i) != str((tt >> i) & 1)]
    return {"status": "pass" if not errs else "fail", "errors": errs}
