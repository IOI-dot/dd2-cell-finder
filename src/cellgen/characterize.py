"""Characterization (Option 1 handout, section 5) and its Liberty view.

Every setup value comes from the shipped HD Liberty, read here and never typed in: table index
values, thresholds, voltage, temperature. HD's timing groups carry no `when`, so each arc uses its
slowest side-input setting, as the handout says the TT library does. Tables are indexed by the
20-80% slew: the input ramp is the slew over the threshold span.

One ngspice run per arc alters the load and the ramp between transients, so the models load once.
`engine` is "fixed" (course image) or "stock" (the host's unpatched build); results of the two are
kept apart, and each Liberty file records the build that made it.
"""
import hashlib
import itertools
import re
import shutil
import statistics
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from dd2 import paths

from . import eda, simulate

HD = "sky130_fd_sc_hd__"
TABLES = {("rise", "delay"): "cell_rise", ("fall", "delay"): "cell_fall",
          ("rise", "transition"): "rise_transition", ("fall", "transition"): "fall_transition"}


@lru_cache(maxsize=2)
def _lib_text(path: str) -> str:
    return Path(path).read_text()


def _lib() -> str:
    return _lib_text(str(paths.full_hd_lib()))


def _attr(text, name) -> float:
    return float(re.search(rf"\b{name}\s*:\s*\"?([-\d.e]+)", text).group(1))


def _block(text: str, start: int) -> str:
    """The { } group that opens at or after start."""
    i = text.index("{", start)
    depth, j = 0, i
    while True:
        c = text[j]
        depth += (c == "{") - (c == "}")
        j += 1
        if depth == 0:
            return text[i:j]


def _cell_text(hd_cell: str) -> str:
    text = _lib()
    return _block(text, text.index(f'cell ("{HD}{hd_cell}")'))


def read_setup(sample=("inv_1", "nand2_1", "nor2_1", "nand3_1", "a21oi_1", "o21ai_1")) -> dict:
    head = _lib()[:_lib().index("cell (")]
    has_when = any(re.search(r"\bwhen\s*:", t) for c in sample for t in _timings(_cell_text(c)))
    return {"voltage": _attr(head, "nom_voltage"), "temperature": _attr(head, "nom_temperature"),
            "process": _attr(head, "nom_process"),
            "slew_lower": _attr(head, "slew_lower_threshold_pct_rise"),
            "slew_upper": _attr(head, "slew_upper_threshold_pct_rise"),
            "slew_lower_fall": _attr(head, "slew_lower_threshold_pct_fall"),
            "slew_upper_fall": _attr(head, "slew_upper_threshold_pct_fall"),
            "slew_derate": _attr(head, "slew_derate_from_library"),
            "input_threshold": _attr(head, "input_threshold_pct_rise"),
            "output_threshold": _attr(head, "output_threshold_pct_rise"),
            "side_rule": "as written in each when" if has_when else "slowest",
            "library": paths.full_hd_lib().name}


def _timings(cell_text: str) -> list:
    return [_block(cell_text, m.start()) for m in re.finditer(r"\btiming\s*\(\s*\)", cell_text)]


def _numbers(s: str) -> list:
    return [float(v) for v in re.findall(r"[-\d.eE+]+", s)]


def read_cell(hd_cell: str) -> dict:
    """The shipped view of a cell: input capacitances and every delay and transition table."""
    text = _cell_text(hd_cell)
    out = {"area": _attr(text, "area"), "capacitance": {}, "rise_capacitance": {}, "fall_capacitance": {},
           "tables": [], "output": None}
    for m in re.finditer(r'\bpin\s*\("(\w+)"\)', text):
        pin = m.group(1)
        body = _block(text, m.start())
        if re.search(r'direction\s*:\s*"?input', body):
            head = re.sub(r"internal_power\s*\(\s*\)\s*\{.*", "", body, flags=re.S)
            for key in ("capacitance", "rise_capacitance", "fall_capacitance"):
                out[key][pin] = _attr(body if key != "capacitance" else head, key)
        else:
            out["output"] = pin
            for t in _timings(body):
                related = re.search(r'related_pin\s*:\s*"(\w+)"', t).group(1)
                sense = re.search(r'timing_sense\s*:\s*"?(\w+)', t).group(1)
                for name in TABLES.values():
                    g = re.search(rf"\b{name}\s*\(", t)
                    if not g:
                        continue
                    b = _block(t, g.start())
                    i1 = _numbers(re.search(r'index_1\s*\("([^"]+)"', b).group(1))
                    i2 = _numbers(re.search(r'index_2\s*\("([^"]+)"', b).group(1))
                    vals = _numbers(",".join(re.findall(r'"([^"]+)"', b[b.index("values"):])))
                    rows = [vals[k * len(i2):(k + 1) * len(i2)] for k in range(len(i1))]
                    out["tables"].append({"pin": related, "table": name, "sense": sense, "index_1": i1,
                                          "index_2": i2, "values": rows})
    return out


def full_ramp(slew: float, setup: dict, broken_full_ramp: bool = False) -> float:
    """Ramp time of an input whose lower-upper slew is `slew`. broken_full_ramp is Table 5's broken
    case: it reads the index as the whole ramp."""
    if broken_full_ramp:
        return slew
    return slew * setup["slew_derate"] / ((setup["slew_upper"] - setup["slew_lower"]) / 100)


def arcs(inputs, tt: int) -> list:
    """Every input to output arc, one per pair of edges, with the side-input rows that sensitize it."""
    n = len(inputs)
    found = {}
    for k, pin in enumerate(inputs):
        for row in simulate.sensitizing(inputs, tt, k):
            y_low = (tt >> row) & 1              # Y with the pin at 0
            pairs = (("rise", "rise"), ("fall", "fall")) if not y_low else (("rise", "fall"), ("fall", "rise"))
            sense = "positive_unate" if not y_low else "negative_unate"
            for i, o in pairs:
                found.setdefault((k, i, o, sense), []).append(row)
    assert n >= 1
    return [{"pin": inputs[k], "k": k, "in_edge": i, "out_edge": o, "sense": s, "sides": rows}
            for (k, i, o, s), rows in sorted(found.items())]


class Engine:
    """One ngspice build: where its model library is and how it runs."""

    def __init__(self, name: str):
        if name not in ("fixed", "stock"):
            raise ValueError(name)
        self.name = name
        self.models = eda.MODELS if name == "fixed" else str((paths.ROOT / "pdk").resolve() / "libs.tech/ngspice/sky130.lib.spice")

    def run(self, workdir: Path, deck: str, log: Path) -> int:
        if self.name == "fixed":
            return eda.run(workdir, ["ngspice", "-b", deck], log)
        with open(log, "w") as f:
            return subprocess.run([shutil.which("ngspice"), "-b", deck], cwd=workdir, stdout=f, stderr=subprocess.STDOUT,
                                  timeout=1800).returncode

    def identity(self, workdir: Path) -> dict:
        Path(workdir).mkdir(parents=True, exist_ok=True)
        if self.name == "fixed":
            log = Path(workdir) / "ngspice_id.log"
            eda.run(workdir, ["sh", "-c", 'ngspice -v | grep -m1 ngspice-; sha256sum "$(readlink -f "$(command -v ngspice)")"'], log)
            text = log.read_text()
            return {"version": re.search(r"ngspice-\d+", text).group(0), "sha256": re.search(r"\b[0-9a-f]{64}\b", text).group(0),
                    "build": "course image dd2-layout-tools (BSIM4 stress fix)"}
        path = Path(shutil.which("ngspice")).resolve()
        ver = subprocess.run([path, "-v"], capture_output=True, text=True).stdout
        return {"version": re.search(r"ngspice-\d+", ver).group(0), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "build": "stock host build"}


def _deck_head(cell, ports, netlist, inputs, out, engine, setup, pin, side, cap=False) -> list:
    v = setup["voltage"]
    conn = {"VNB": "VGND", "VPB": "VPWR"}
    lines = [f"* {cell}: characterization of {pin} (generated)", f".lib {engine.models} tt", f".include {netlist}",
             f".temp {setup['temperature']:g}", ".options reltol=1e-4 abstol=1e-13 vntol=1e-7 gmin=1e-15",
             f"VDD VPWR 0 {v}", "VSS VGND 0 0", f"Cload {out} 0 1f",
             f"X1 {' '.join(conn.get(p, p) for p in ports)} {cell}"]
    for j, other in enumerate(inputs):
        if other == pin:
            lines.append(f"Vin {pin} 0 PWL(0 0 1n 0)")
        else:
            lines.append(f"V{other} {other} 0 dc {v * ((side >> j) & 1)}")
    return lines


def _point(lines, arc, slew, load, i, j, setup, out, broken):
    v = setup["voltage"]
    ramp = full_ramp(slew, setup, broken)
    a, b = (0.0, v) if arc["in_edge"] == "rise" else (v, 0.0)
    t0 = 1.0
    stop = t0 + 1.5 * ramp + 2.0 + 120.0 * load
    edge = arc["out_edge"].upper()
    lo, hi = v * setup["slew_lower"] / 100, v * setup["slew_upper"] / 100
    th_in, th_out = v * setup["input_threshold"] / 100, v * setup["output_threshold"] / 100
    first, last = (lo, hi) if arc["out_edge"] == "rise" else (hi, lo)
    lines += [f"alter cload = {load * 1e-12:.6e}",
              f"alter @vin[pwl] = [ 0 {a} {t0:.6f}n {a} {t0 + ramp:.6f}n {b} {stop + 1:.6f}n {b} ]",
              f"tran {stop / 12000:.6f}n {stop:.5f}n",
              f"echo POINT {i} {j}",
              f"meas tran tin WHEN v({arc['pin']})={th_in} CROSS=1",
              f"meas tran tout WHEN v({out})={th_out} {edge}=1",
              f"meas tran ta WHEN v({out})={first} {edge}=1",
              f"meas tran tb WHEN v({out})={last} {edge}=1",
              "destroy all"]


def _parse_points(log: str, setup: dict) -> dict:
    out = {}
    for chunk in log.split("POINT ")[1:]:
        i, j = (int(x) for x in chunk.split()[:2])
        m = {k: float(v) for k, v in re.findall(r"^(tin|tout|ta|tb)\s*=\s*([-\d.eE+]+)", chunk, re.M)}
        if len(m) == 4:
            out[(i, j)] = ((m["tout"] - m["tin"]) * 1e9,
                           abs(m["tb"] - m["ta"]) * 1e9 / setup["slew_derate"])
    return out


def _run_arc(cell, ports, netlist, inputs, out, arc, spec, setup, engine, workdir, broken) -> dict:
    tag = f"{arc['pin']}_{arc['in_edge']}_{arc['out_edge']}"
    i1, i2 = spec["index_1"], spec["index_2"]
    mid = (len(i1) // 2, len(i2) // 2)
    side = arc["sides"][0]
    tried = {}
    if len(arc["sides"]) > 1:
        lines = _deck_head(cell, ports, netlist, inputs, out, engine, setup, arc["pin"], side) + [".control"]
        for s_i, s in enumerate(arc["sides"]):
            for j, other in enumerate(inputs):
                if other != arc["pin"]:
                    lines.append(f"alter V{other} dc = {setup['voltage'] * ((s >> j) & 1)}")
            _point(lines, arc, i1[mid[0]], i2[mid[1]], s_i, 0, setup, out, broken)
        (Path(workdir) / f"side_{tag}.spice").write_text("\n".join(lines + [".endc", ".end"]) + "\n")
        engine.run(workdir, f"side_{tag}.spice", Path(workdir) / f"side_{tag}.log")
        got = _parse_points((Path(workdir) / f"side_{tag}.log").read_text(), setup)
        tried = {arc["sides"][k[0]]: v[0] for k, v in got.items()}
        if tried:
            side = max(tried, key=tried.get)
    lines = _deck_head(cell, ports, netlist, inputs, out, engine, setup, arc["pin"], side) + [".control"]
    for i, slew in enumerate(i1):
        for j, load in enumerate(i2):
            _point(lines, arc, slew, load, i, j, setup, out, broken)
    (Path(workdir) / f"arc_{tag}.spice").write_text("\n".join(lines + [".endc", ".end"]) + "\n")
    engine.run(workdir, f"arc_{tag}.spice", Path(workdir) / f"arc_{tag}.log")
    got = _parse_points((Path(workdir) / f"arc_{tag}.log").read_text(), setup)
    missing = [k for k in itertools.product(range(len(i1)), range(len(i2))) if k not in got]
    res = []
    for what, n in (("delay", 0), ("transition", 1)):
        res.append({"pin": arc["pin"], "sense": arc["sense"], "table": TABLES[(arc["out_edge"], what)],
                    "index_1": i1, "index_2": i2, "side": side, "sides_tried": tried, "missing": len(missing),
                    "values": [[got[(i, j)][n] if (i, j) in got else None for j in range(len(i2))] for i in range(len(i1))]})
    return {"tables": res}


def _run_cap(cell, ports, netlist, inputs, out, pin, side, slew, load, engine, setup, workdir, broken) -> dict:
    """Charge into the pin between the Liberty's slew thresholds, on each edge: C = Q / dV, at the
    middle of the table. A tiny load would let the output swing inside the window and add Miller
    charge that a loaded pin does not see."""
    v = setup["voltage"]
    ramp = full_ramp(slew, setup, broken)
    lines = _deck_head(cell, ports, netlist, inputs, out, engine, setup, pin, side)
    lines[lines.index(f"Cload {out} 0 1f")] = f"Cload {out} 0 {load}p"
    t0, t1 = 1.0, 6.0
    lines[lines.index(f"Vin {pin} 0 PWL(0 0 1n 0)")] = \
        f"Vin {pin} 0 PWL(0 0 {t0}n 0 {t0 + ramp:.5f}n {v} {t1}n {v} {t1 + ramp:.5f}n 0)"
    lo, hi = setup["slew_lower"] / 100, setup["slew_upper"] / 100
    edge = lambda t, a, b: (t + ramp * a, t + ramp * b)                     # noqa: E731
    r0, r1 = edge(t0, lo, hi)
    f0, f1 = edge(t1, 1 - hi, 1 - lo)
    lines += [".control", f"tran 0.5p {t1 + ramp + 1:.3f}n",
              f"meas tran qr INTEG i(Vin) from={r0:.5f}n to={r1:.5f}n",
              f"meas tran qf INTEG i(Vin) from={f0:.5f}n to={f1:.5f}n", ".endc", ".end"]
    deck = f"cap_{pin}.spice"
    (Path(workdir) / deck).write_text("\n".join(lines) + "\n")
    engine.run(workdir, deck, Path(workdir) / f"cap_{pin}.log")
    m = {k: float(x) for k, x in re.findall(r"^(qr|qf)\s*=\s*([-\d.eE+]+)", (Path(workdir) / f"cap_{pin}.log").read_text(), re.M)}
    if len(m) < 2:
        return {}
    swing = v * (setup["slew_upper"] - setup["slew_lower"]) / 100
    rise, fall = abs(m["qr"]) / swing * 1e12, abs(m["qf"]) / swing * 1e12
    return {"rise": rise, "fall": fall, "mean": (rise + fall) / 2}


def characterize(cell: str, netlist: Path, inputs, out: str, tt: int, spec: dict, engine: Engine,
                 workdir: Path, setup: dict | None = None, broken_full_ramp=False, jobs=6) -> dict:
    """spec: {"index_1": slews, "index_2": loads}. The netlist is copied next to the decks."""
    setup = setup or read_setup()
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    local = workdir / "cell.spice"
    if Path(netlist).resolve() != local.resolve():
        shutil.copy(netlist, local)
    ports = simulate.subckt_ports(local.read_text(), cell)
    todo = arcs(inputs, tt)
    with ThreadPoolExecutor(jobs) as pool:
        res = list(pool.map(lambda a: _run_arc(cell, ports, local.name, inputs, out, a, spec, setup, engine, workdir,
                                               broken_full_ramp), todo))
        tables = [t for r in res for t in r["tables"]]
        side_of = {}
        for t in tables:
            side_of.setdefault(t["pin"], t["side"])
        slew, load = spec["index_1"][len(spec["index_1"]) // 2], spec["index_2"][len(spec["index_2"]) // 2]
        caps = dict(zip(inputs, pool.map(lambda p: _run_cap(cell, ports, local.name, inputs, out, p, side_of.get(p, 0), slew, load,
                                                            engine, setup, workdir, broken_full_ramp), inputs)))
    return {"tables": tables, "capacitance": caps, "engine": engine.name, "broken_full_ramp": broken_full_ramp}


def compare_tables(ours: list, hd: list) -> dict:
    """Every entry of every table against the shipped value: |ours - hd| / hd."""
    errs = []
    for h in hd:
        for o in (x for x in ours if x["pin"] == h["pin"] and x["table"] == h["table"]
                  and x.get("sense", h.get("sense")) == h.get("sense", x.get("sense"))):
            for i, row in enumerate(h["values"]):
                for j, v in enumerate(row):
                    got = o["values"][i][j]
                    if got is None:
                        errs.append((float("inf"), h["pin"], h["table"], i, j, None, v))
                    elif v:
                        errs.append((abs(got - v) / abs(v) * 100, h["pin"], h["table"], i, j, got, v))
    pct = [e[0] for e in errs]
    w = max(errs)
    tag = hd[0]
    return {"entries": len(errs), "median_abs_pct": round(statistics.median(pct), 3), "max_abs_pct": round(w[0], 3),
            "worst": {"pin": w[1], "table": w[2], "slew_ns": tag["index_1"][w[3]], "load_pf": tag["index_2"][w[4]],
                      "ours": w[5], "shipped": w[6]}, "errors_pct": pct}


# ---- Liberty ------------------------------------------------------------------------------------

def _primes(tt: int, n: int) -> list:
    """A cover of the on-set by prime implicants: (care mask, value)."""
    on = [r for r in range(1 << n) if (tt >> r) & 1]
    terms = {((1 << n) - 1, r) for r in on}
    primes = set()
    while terms:
        merged, used = set(), set()
        for (ca, va), (cb, vb) in itertools.combinations(sorted(terms), 2):
            d = va ^ vb
            if ca == cb and bin(d).count("1") == 1:
                merged.add((ca & ~d, va & ~d))
                used |= {(ca, va), (cb, vb)}
        primes |= terms - used
        terms = merged
    cover, left = [], set(on)
    for p in sorted(primes, key=lambda p: bin(p[0]).count("1")):
        hits = {r for r in left if r & p[0] == p[1]}
        if hits:
            cover.append(p)
            left -= hits
    return cover


def function_text(tt: int, inputs) -> str:
    n = len(inputs)
    parts = []
    for care, val in _primes(tt, n):
        lits = [("" if (val >> k) & 1 else "!") + x for k, x in enumerate(inputs) if (care >> k) & 1]
        parts.append("(" + "&".join(lits) + ")")
    return " | ".join(parts)


def _table(name, t, tmpl) -> str:
    fmt = lambda xs: ", ".join(f"{v:.10f}" for v in xs)                        # noqa: E731
    rows = ", \\\n                        ".join(f'"{fmt(r)}"' for r in t["values"])
    return (f'                {name} ("{tmpl}") {{\n                    index_1("{fmt(t["index_1"])}");\n'
            f'                    index_2("{fmt(t["index_2"])}");\n                    values({rows});\n                }}\n')


def cell_group(name, inputs, out, tt, area, caps, tables, tmpl="dd2_tmpl") -> str:
    pins = "".join(f'''        pin ("{p}") {{
            direction : "input";
            capacitance : {caps[p]["mean"]:.10f};
            rise_capacitance : {caps[p]["rise"]:.10f};
            fall_capacitance : {caps[p]["fall"]:.10f};
            related_ground_pin : "VGND";
            related_power_pin : "VPWR";
        }}
''' if isinstance(caps[p], dict) else f'''        pin ("{p}") {{
            direction : "input";
            capacitance : {caps[p]:.10f};
            related_ground_pin : "VGND";
            related_power_pin : "VPWR";
        }}
''' for p in inputs)
    groups = {}
    for t in tables:
        groups.setdefault((t["pin"], t["sense"]), []).append(t)
    timing = "".join(f'''            timing () {{
                related_pin : "{p}";
                timing_sense : "{s}";
                timing_type : "combinational";
{"".join(_table(t["table"], t, tmpl) for t in ts)}            }}
''' for (p, s), ts in groups.items())
    pg = "".join(f'''        pg_pin ("{n}") {{
            pg_type : "{t}";
            voltage_name : "{n}";
        }}
''' for n, t in (("VGND", "primary_ground"), ("VNB", "pwell"), ("VPB", "nwell"), ("VPWR", "primary_power")))
    return f'''    cell ("{name}") {{
        area : {area:.10f};
{pg}{pins}        pin ("{out}") {{
            direction : "output";
            function : "{function_text(tt, inputs)}";
            related_ground_pin : "VGND";
            related_power_pin : "VPWR";
{timing}        }}
    }}
'''


def template(tables, tmpl="dd2_tmpl") -> str:
    n1, n2 = len(tables[0]["index_1"]), len(tables[0]["index_2"])
    return (f'    lu_table_template ("{tmpl}") {{\n        variable_1 : "input_net_transition";\n'
            f'        variable_2 : "total_output_net_capacitance";\n'
            f'        index_1("{", ".join(f"{i}" for i in range(1, n1 + 1))}");\n'
            f'        index_2("{", ".join(f"{i}" for i in range(1, n2 + 1))}");\n    }}\n')


def header(name: str, setup: dict, sim: dict) -> str:
    return f'''/* {name}: characterized with {sim["version"]}, SHA256 {sim["sha256"]}, {sim.get("build", "")} */
library ("{name}") {{
    comment : "simulator {sim["version"]} sha256 {sim["sha256"]}";
    technology("cmos");
    delay_model : "table_lookup";
    time_unit : "1ns";
    voltage_unit : "1V";
    current_unit : "1mA";
    pulling_resistance_unit : "1kohm";
    leakage_power_unit : "1nW";
    capacitive_load_unit(1.0000000000, "pf");
    nom_process : {setup["process"]:.10f};
    nom_temperature : {setup["temperature"]:.10f};
    nom_voltage : {setup["voltage"]:.10f};
    slew_derate_from_library : {setup["slew_derate"]:.10f};
    slew_lower_threshold_pct_rise : {setup["slew_lower"]:.10f};
    slew_upper_threshold_pct_rise : {setup["slew_upper"]:.10f};
    slew_lower_threshold_pct_fall : {setup["slew_lower_fall"]:.10f};
    slew_upper_threshold_pct_fall : {setup["slew_upper_fall"]:.10f};
    input_threshold_pct_rise : {setup["input_threshold"]:.10f};
    input_threshold_pct_fall : {setup["input_threshold"]:.10f};
    output_threshold_pct_rise : {setup["output_threshold"]:.10f};
    output_threshold_pct_fall : {setup["output_threshold"]:.10f};
    voltage_map ("VGND", 0.0);
    voltage_map ("VNB", 0.0);
    voltage_map ("VPB", {setup["voltage"]:.10f});
    voltage_map ("VPWR", {setup["voltage"]:.10f});
    operating_conditions ("tt_025C_1v80") {{
        process : {setup["process"]:.10f};
        temperature : {setup["temperature"]:.10f};
        voltage : {setup["voltage"]:.10f};
    }}
    default_operating_conditions : "tt_025C_1v80";
'''


def liberty_text(name, inputs, out, tt, area, caps, tables, setup, sim) -> str:
    """A Liberty file that holds exactly one cell group, in HD's units (handout 3.3)."""
    return header(f"{name}_lib", setup, sim) + template(tables) + cell_group(name, inputs, out, tt, area, caps, tables) + "}\n"
