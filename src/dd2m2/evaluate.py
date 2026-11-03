"""Identical A/B mapping recipes, RTL correctness checks and OpenSTA evidence."""

from pathlib import Path
import json
import re
from dd2 import aig, mapping, paths, provenance, tools


def disambiguate_symbols(path):
    """ABC rejects a latch and a primary output with the same AIGER symbol.
    Prefix each port role after decoding the binary AND section; preserve all
    logic, initial states, ordering and original signal names within each role.
    """
    path = Path(path)
    data = path.read_bytes()
    end = data.index(b"\n")
    h = data[:end].split()
    if h[0] != b"aig":
        raise ValueError("expected binary AIGER")
    _, i, l, o, a = map(int, h[1:6])
    extra = list(map(int, h[6:])) + [0, 0, 0, 0]
    pos = end + 1
    for _ in range(l + o + extra[0] + extra[1]):
        pos = data.index(b"\n", pos) + 1
    for _ in range(2 * a):
        _, pos = aig._decode(data, pos)
    suffix = data[pos:].decode("ascii")
    prefixes = {"i": "pi__", "l": "state__", "o": "po__"}
    suffix = re.sub(r"^([ilo]\d+) (.*)$", lambda m: m[1] + " " + prefixes[m[1][0]] + m[2], suffix, flags=re.M)
    path.write_bytes(data[:pos] + suffix.encode("ascii"))


def align_symbols(a, b):
    """Match signal aliases shared by gold and mapped AIGs, never latch order.
    Mapping introduces additional aliases and can reorder registers. Use a
    bijection of common names within each port role and save it for inspection.
    Missing matches fail closed instead of silently comparing states by order.
    A bounded separate sequential diagnostic is recorded independently.
    """

    def read(path):
        data = Path(path).read_bytes()
        end = data.index(b"\n")
        h = data[:end].split()
        _, i, l, o, n = map(int, h[1:6])
        ex = list(map(int, h[6:])) + [0, 0]
        pos = end + 1
        for _ in range(l + o + ex[0] + ex[1]):
            pos = data.index(b"\n", pos) + 1
        for _ in range(2 * n):
            _, pos = aig._decode(data, pos)
        suffix = data[pos:].decode("ascii")
        symbols = {}
        for m in re.finditer(r"^([ilo])(\d+) (.*)$", suffix, re.M):
            symbols[(m[1], int(m[2]))] = set(m[3].split())
        return data[:pos], suffix, symbols

    pa, sa, aa = read(a)
    pb, sb, bb = read(b)
    replacements_a = {}
    replacements_b = {}
    records = []
    for role in "ilo":
        ga = sorted(k for k in aa if k[0] == role)
        gb = sorted(k for k in bb if k[0] == role)
        edges = {x: [y for y in gb if aa[x] & bb[y]] for x in ga}
        matched = {}

        def augment(x, seen):
            for y in edges[x]:
                if y in seen:
                    continue
                seen.add(y)
                if y not in matched or augment(matched[y], seen):
                    matched[y] = x
                    return True
            return False

        for x in sorted(ga, key=lambda x: len(edges[x])):
            if not augment(x, set()):
                raise RuntimeError(f"cannot align AIG {role} aliases: {sorted(aa[x])}")
        if len(matched) != len(gb):
            raise RuntimeError(f"different number of named {role} cutpoints")
        for y, x in matched.items():
            label = f"dd2_{role}_{x[1]}"
            replacements_a[x] = label
            replacements_b[y] = label
            records.append(
                {
                    "role": role,
                    "gold_index": x[1],
                    "mapped_index": y[1],
                    "shared_aliases": sorted(aa[x] & bb[y]),
                }
            )

    def write(path, prefix, suffix, repl):
        suffix = re.sub(
            r"^([ilo])(\d+) (.*)$", lambda m: m[1] + m[2] + " " + repl[(m[1], int(m[2]))], suffix, flags=re.M
        )
        Path(path).write_bytes(prefix + suffix.encode("ascii"))

    write(a, pa, sa, replacements_a)
    write(b, pb, sb, replacements_b)
    provenance.write_json(Path(a).parent / "aiger_signal_alignment.json", records)


def quote(p):
    p = str(p)
    if any(c in p for c in ["\n", "\r", '"', ";"]):
        raise ValueError("unsupported character in tool path")
    return '"' + p + '"'


def command(script, log, timeout=1800):
    log = Path(log)
    ys = log.with_suffix(".ys")
    ys.parent.mkdir(parents=True, exist_ok=True)
    ys.write_text(script + "\n")
    code, seconds = tools.run(
        tools.yosys_cmd() + ["-Q", "-T", "-s", str(ys)], log, cwd=paths.ROOT, timeout=timeout
    )
    if code:
        raise RuntimeError(f"Yosys failed; see {paths.rel(log)}")
    return seconds


def map_design(design, src, lib, script, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    text = f"""read_verilog {'-sv ' if design.sv else ''}{quote(src)}
synth -flatten -top {design.top}
write_rtlil {quote(out/'gold.il')}
write_json {quote(out/'gold.json')}
dfflibmap -liberty {quote(lib)}
abc -liberty {quote(lib)} -script {mapping.SCRIPTS[script]}
opt_clean -purge
tee -q -o {out/'stat.json'} stat -json -liberty {quote(lib)}
write_json {quote(out/'mapped.json')}
write_verilog -noattr -noexpr -norename {quote(out/'mapped.v')}
"""
    elapsed = command(text, out / "mapping.log")
    area, num, bytype = mapping.parse_stat(json.loads((out / "stat.json").read_text()), design.top)
    result = dict(
        design=design.name,
        top=design.top,
        script=script,
        area_um2=area,
        cells=num,
        cell_counts=bytype,
        seconds=elapsed,
        inputs=provenance.hash_inputs([src, lib]),
        yosys=tools.version(tools.yosys_cmd() + ["-V"]),
    )
    provenance.write_json(out / "mapping.json", result)
    return result


def verify_mapping(design, lib, out):
    out = Path(out)
    # Restore the actual RTL-derived unmapped gold saved immediately before mapping.
    # Name-bearing symbols let ABC align state cutpoints independently of gate order.
    gold = f"""read_rtlil {quote(out/'gold.il')}
async2sync
dffunmap
aigmap
write_json {quote(out/'gold_state.json')}
"""
    command(gold, out / "gold_aig.log")
    gate = f"""read_liberty -ignore_miss_func {quote(lib)}
read_verilog {quote(out/'mapped.v')}
hierarchy -top {design.top}
flatten
proc
techmap
opt_clean
write_rtlil {quote(out/'gate.il')}
async2sync
dffunmap
aigmap
write_json {quote(out/'gate_state.json')}
"""
    command(gate, out / "gate_aig.log")
    original = json.loads((out / "gold.json").read_text())["modules"][design.top]
    names = sorted(
        name for name, c in original["cells"].items() if "DFF" in c["type"] or "LATCH" in c["type"]
    )
    state_records = {}
    for side in ["gold", "gate"]:
        j = json.loads((out / f"{side}_state.json").read_text())
        mod = j["modules"][design.top]
        record = []
        for name, c in mod["cells"].items():
            if "DFF" not in c["type"] and "LATCH" not in c["type"]:
                continue
            matches = [
                (i, n)
                for i, n in enumerate(names)
                if name == n or name.startswith(n + ".") or name.startswith("$flatten\\" + n + ".")
            ]
            if len(matches) != 1:
                raise RuntimeError(f"cannot trace state instance {name} back to RTL-derived gold")
            i, origin = matches[0]
            for k, bit in enumerate(c["connections"]["Q"]):
                label = f"dd2_state_{i}_{k}"
                mod["netnames"][label] = {"hide_name": 0, "bits": [bit], "attributes": {"keep": "1"}}
                record.append(
                    {"source_instance": origin, "expanded_instance": name, "alias": label, "bit": bit}
                )
        p = out / f"{side}_state_named.json"
        p.write_text(json.dumps(j))
        state_records[side] = record
        command(
            f'read_json {quote(p)}\nwrite_aiger -zinit -symbols {quote(out/(side+".aig"))}',
            out / f"{side}_write_aig.log",
        )
        # -zinit adds one artificial initialization latch with no named HDL wire.
        ap = out / (side + ".aig")
        data = ap.read_bytes()
        h = data[: data.index(b"\n")].split()
        L = int(h[3])
        if L and not re.search(rb"(?m)^l" + str(L - 1).encode() + rb" ", data):
            marker = data.rfind(b"\nc\n")
            line = f"l{L-1} dd2_initialization_latch\n".encode()
            if marker >= 0:
                data = data[: marker + 1] + line + data[marker + 1 :]
            else:
                data += line
            ap.write_bytes(data)
    provenance.write_json(out / "state_instance_alignment.json", state_records)
    align_symbols(out / "gold.aig", out / "gate.aig")
    code, _ = tools.run(
        tools.abc_cmd() + ["-c", f'cec {out/"gold.aig"} {out/"gate.aig"}'],
        out / "cec.log",
        cwd=paths.ROOT,
        timeout=1800,
    )
    cec_ok = code == 0 and "Networks are equivalent" in (out / "cec.log").read_text()
    seq = f"""read_rtlil {quote(out/'gold.il')}
rename {design.top} gold
design -stash reference
read_rtlil {quote(out/'gate.il')}
rename {design.top} gate
design -copy-from reference -as gold gold
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple
equiv_induct -seq 8
equiv_status -assert
"""
    seq_ok = True
    try:
        command(seq, out / "sequential_equivalence.log", timeout=5)
    except RuntimeError:
        seq_ok = False
    result = {
        "abc_cec": "pass" if cec_ok else "fail",
        "yosys_sequential_equivalence": "pass" if seq_ok else "not proven within diagnostic budget",
        "status": "pass" if cec_ok else "fail",
        "scope": "Required ABC CEC of RTL-derived gold vs Liberty-expanded mapping, with bijectively aligned named state/initial-value cutpoints. Extra Yosys induction is a bounded diagnostic, not a claimed proof when it times out.",
    }
    provenance.write_json(out / "equivalence.json", result)
    return result


def timing_script(design, lib, out):
    out = Path(out)
    # A reproducible logic-delay comparison. These are declared comparison constraints,
    # not a signoff timing specification; estimated-cell timing is a placeholder.
    tcl = f"""read_liberty {{{lib}}}
read_verilog {{{out/'mapped.v'}}}
link_design {design.top}
set clock_ports {{}}
set clock_names {{}}
foreach p [all_inputs] {{
  set name [get_full_name $p]
  if {{[regexp -nocase {{^(clk|clock|i_clk|pclk|clk_i|sys_clk)$}} $name]}} {{
    create_clock -name $name -period 100 $p
    lappend clock_ports $p
    lappend clock_names $name
  }}
}}
if {{[llength $clock_ports] == 0}} {{create_clock -name virtual -period 100}}
set data_inputs {{}}
foreach p [all_inputs] {{
  if {{[lsearch -exact $clock_names [get_full_name $p]] < 0}} {{lappend data_inputs $p}}
}}
if {{[llength $data_inputs] > 0}} {{
  set_input_transition 0.1 $data_inputs
  set_input_delay 0 -clock [lindex [all_clocks] 0] $data_inputs
}}
set_clock_transition 0.1 [all_clocks]
set_load 0.01 [all_outputs]
set_output_delay 0 -clock [lindex [all_clocks] 0] [all_outputs]
report_checks -path_delay max -group_path_count 5 -digits 6
set worst -1
# One max path per endpoint, enough group slots to cover the data endpoints.
set endpoint_limit [expr {{[llength [all_registers -data_pins]] + [llength [all_outputs]]}}]
if {{$endpoint_limit < 1}} {{set endpoint_limit 1}}
foreach p [find_timing_paths -path_delay max -group_path_count $endpoint_limit -endpoint_path_count 1] {{
  set points [get_property $p points]
  if {{[llength $points] == 0}} {{error "timing path has no points"}}
  set endpoint_point [lindex $points end]
  set a [get_property $endpoint_point arrival]
  if {{$a > $worst}} {{set worst $a}}
}}
puts "DD2_WORST_ARRIVAL_NS=$worst"
exit
"""
    return tcl


def timing(design, lib, out):
    out = Path(out)
    tcl = timing_script(design, lib, out)
    (out / "timing.tcl").write_text(tcl)
    code, _ = tools.run(
        ["sta", "-exit", str(out / "timing.tcl")], out / "timing.log", cwd=paths.ROOT, timeout=600
    )
    log = (out / "timing.log").read_text()
    m = re.search(r"DD2_WORST_ARRIVAL_NS=([0-9.eE+-]+)", log)
    errors = re.findall(r"^(?:Error(?:\s+\d+)?|Fatal):.*", log, re.M | re.I)
    ok = code == 0 and bool(m) and float(m[1]) >= 0 and not errors
    result = {
        "status": "pass" if ok else "fail",
        "worst_arrival_ns": float(m[1]) if ok else None,
        "errors": errors,
        "tool_exit_code": code,
        "constraints": {
            "clock_period_ns": 100,
            "input_slew_ns": 0.1,
            "clock_slew_ns": 0.1,
            "output_load_pf": 0.01,
        },
        "note": "pre-layout comparison; estimated cells have placeholder timing; no extracted interconnect",
    }
    provenance.write_json(out / "timing.json", result)
    return result
