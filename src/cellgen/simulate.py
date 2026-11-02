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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dd2 import paths

from . import eda

VDD = 1.8
SLOT_NS = 2.0


def hd_table_point(lib: Path | None = None, slew_target=0.1, load_target=0.01, hd_cell="inv_1") -> dict:
    """The index point of an HD cell's cell_rise table nearest the targets, with the table's
    variables and HD's slew thresholds, all read from the Liberty file."""
    text = Path(lib or paths.full_hd_lib()).read_text()
    cell = text[text.index(f'cell ("sky130_fd_sc_hd__{hd_cell}")'):]
    m = re.search(r'cell_rise\s*\("([^"]+)"\)\s*\{\s*index_1\("([^"]+)"\);\s*index_2\("([^"]+)"\)', cell)
    template, i1, i2 = m.group(1), [float(v) for v in m.group(2).split(",")], [float(v) for v in m.group(3).split(",")]
    tm = re.search(rf'lu_table_template \("{re.escape(template)}"\)\s*\{{\s*variable_1 : "(\w+)";\s*variable_2 : "(\w+)"', text)
    if tm.group(1) != "input_net_transition" or tm.group(2) != "total_output_net_capacitance":
        raise ValueError(f"unexpected table variables {tm.groups()} in {template}")
    th = {k: float(v) for k, v in re.findall(r"\n\s*(slew_(?:lower|upper)_threshold_pct_rise)\s*:\s*([\d.]+)", text)}
    return {"table": "cell_rise", "template": template, "variable_1": tm.group(1), "variable_2": tm.group(2),
            "slew_ns": min(i1, key=lambda v: abs(v - slew_target)),
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


def _header(cell, ports, netlist_in_container, point, title, out="Y"):
    conn = {"VNB": "VGND", "VPB": "VPWR"}
    return [f"* {cell}: {title} (generated)", f".lib {eda.MODELS} tt", f".include {netlist_in_container}",
            ".temp 25", f"VDD VPWR 0 {VDD}", "VSS VGND 0 0", f"CL {out} 0 {point['load_pf']}p",
            f"X1 {' '.join(conn.get(p, p) for p in ports)} {cell}"]


def dc_testbench(cell: str, ports, inputs, netlist_in_container: str, point: dict, out="Y") -> str:
    lines = _header(cell, ports, netlist_in_container, point, "DC operating point of every input row", out)
    lines += [f"V{name} {name} 0 dc 0" for name in inputs] + [".control"]
    for row in range(1 << len(inputs)):
        lines += [f"alter V{name} dc = {VDD * (row >> k & 1)}" for k, name in enumerate(inputs)]
        lines += ["op", f"let vy = v({out})", f"echo DC {row} $&vy"]
    return "\n".join(lines + [".endc", ".end"]) + "\n"


def testbench(cell: str, ports, inputs, netlist_in_container: str, point: dict, out="Y") -> str:
    ramp = point["slew_ns"] / ((point["slew_upper_pct"] - point["slew_lower_pct"]) / 100)  # full ramp
    seq = sequence(len(inputs))
    lines = _header(cell, ports, netlist_in_container, point, "transient through every state and toggle", out)
    for k, name in enumerate(inputs):
        pts = [f"0 {VDD * (seq[0] >> k & 1)}"]
        for i in range(1, len(seq)):
            a, b = seq[i - 1] >> k & 1, seq[i] >> k & 1
            if a != b:
                t = i * SLOT_NS
                pts += [f"{t:.4f}n {VDD * a}", f"{t + ramp:.4f}n {VDD * b}"]
        lines.append(f"V{name} {name} 0 PWL({' '.join(pts)})")
    lines += [".control", "set wr_singlescale", "set wr_vecnames",
              f"tran 2p {len(seq) * SLOT_NS}n", f"wrdata /w/tran.txt v({out})", ".endc", ".end"]
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


def spice(workdir: Path, cell: str, netlist: Path, inputs, tt: int, point: dict | None = None, out="Y") -> dict:
    """Run the DC and transient checks on `netlist` (inside workdir) in the course image."""
    point = point or hd_table_point()
    ports = subckt_ports(Path(netlist).read_text(), cell)
    inc = f"/w/{Path(netlist).name}"
    (Path(workdir) / "tb_dc.spice").write_text(dc_testbench(cell, ports, inputs, inc, point, out))
    (Path(workdir) / "tb_tran.spice").write_text(testbench(cell, ports, inputs, inc, point, out))
    (Path(workdir) / "tran.txt").unlink(missing_ok=True)
    with ThreadPoolExecutor(2) as pool:              # independent runs: together they take as long as the longer one
        pool.submit(eda.run, workdir, ["ngspice", "-b", "tb_dc.spice"], Path(workdir) / "spice_dc.log")
        code = pool.submit(eda.run, workdir, ["ngspice", "-b", "tb_tran.spice"], Path(workdir) / "spice_tran.log").result()
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


def verilog_model(cell: str, inputs, tt: int, out="Y") -> str:
    n = len(inputs)
    bits = 1 << n
    sel = ", ".join(reversed(inputs)) if n > 1 else inputs[0]
    return (f"// {cell}: functional model generated from the truth table (A = bit 0)\n"
            f"module {cell} ({', '.join(inputs)}, {out});\n"
            f"  input {', '.join(inputs)};\n  output {out};\n"
            f"  wire [{bits - 1}:0] T = {bits}'h{tt:0{max(1, bits // 4)}X};\n"
            f"  assign {out} = T[{{{sel}}}];\nendmodule\n")


def verilog_check(model: Path, cell: str, inputs, tt: int, workdir: Path, out="Y") -> dict:
    """Icarus: drive every input combination and compare Y with the truth table."""
    n = len(inputs)
    tb = [f"module tb; reg [{n - 1}:0] v; wire {out}; integer i;",
          f"  {cell} dut ({', '.join(f'.{x}(v[{k}])' for k, x in enumerate(inputs))}, .{out}({out}));",
          f"  initial begin for (i = 0; i < {1 << n}; i = i + 1) begin v = i; #1 $display(\"ROW %0d %b\", i, {out}); end end",
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


def sensitizing(inputs, tt, k: int) -> list:
    """Side-input rows (input k at 0) for which Y depends on input k."""
    n = len(inputs)
    return [r for r in range(1 << n) if not (r >> k) & 1 and ((tt >> r) ^ (tt >> (r | 1 << k))) & 1]


def delays(workdir: Path, cell: str, netlist: Path, inputs, tt: int, point: dict | None = None, out="Y") -> list:
    """50% delay and 20-80% output transition of every input arc, for both input edges, at the HD
    table point; every sensitizing side-input assignment is measured (a report, not a Liberty)."""
    point = point or hd_table_point()
    ports = subckt_ports(Path(netlist).read_text(), cell)
    ramp = point["slew_ns"] / ((point["slew_upper_pct"] - point["slew_lower_pct"]) / 100)
    lo, hi = VDD * point["slew_lower_pct"] / 100, VDD * point["slew_upper_pct"] / 100
    arcs = []
    for k, pin in enumerate(inputs):
        for side in sensitizing(inputs, tt, k):
            name = f"arc_{pin}_{side}"
            lines = _header(cell, ports, f"/w/{Path(netlist).name}", point, f"delay {pin} side {side}", out)
            for j, other in enumerate(inputs):
                if j == k:
                    lines.append(f"V{other} {other} 0 PWL(0 0 1n 0 {1 + ramp:.4f}n {VDD} 4n {VDD} {4 + ramp:.4f}n 0)")
                else:
                    lines.append(f"V{other} {other} 0 dc {VDD * (side >> j & 1)}")
            lines += [".control", "tran 1p 8n",
                      f"meas tran tin_r WHEN v({pin})={VDD / 2} RISE=1", f"meas tran tin_f WHEN v({pin})={VDD / 2} FALL=1",
                      f"meas tran ty1 WHEN v({out})={VDD / 2} CROSS=1", f"meas tran ty2 WHEN v({out})={VDD / 2} CROSS=2",
                      f"meas tran a1 WHEN v({out})={lo} CROSS=1", f"meas tran b1 WHEN v({out})={hi} CROSS=1",
                      f"meas tran a2 WHEN v({out})={lo} CROSS=2", f"meas tran b2 WHEN v({out})={hi} CROSS=2",
                      ".endc", ".end"]
            (Path(workdir) / f"{name}.spice").write_text("\n".join(lines) + "\n")
            eda.run(workdir, ["ngspice", "-b", f"{name}.spice"], Path(workdir) / f"{name}.log")
            m = {a: float(b) for a, b in re.findall(r"^(\w+)\s*=\s*([-\d.eE+]+)", (Path(workdir) / f"{name}.log").read_text(), re.M)}
            out_rise = ((tt >> (side | 1 << k)) & 1) == 1        # Y after the input rises
            row = {"pin": pin, "side_inputs": side, "input_rise_gives": "rise" if out_rise else "fall"}
            if all(x in m for x in ("tin_r", "tin_f", "ty1", "ty2", "a1", "b1", "a2", "b2")):
                row.update(delay_in_rise_ns=round((m["ty1"] - m["tin_r"]) * 1e9, 5),
                           transition_in_rise_ns=round(abs(m["b1"] - m["a1"]) * 1e9, 5),
                           delay_in_fall_ns=round((m["ty2"] - m["tin_f"]) * 1e9, 5),
                           transition_in_fall_ns=round(abs(m["b2"] - m["a2"]) * 1e9, 5))
            else:
                row["error"] = f"measurement failed, see {name}.log"
            arcs.append(row)
    return arcs
