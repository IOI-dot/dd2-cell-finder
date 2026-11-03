"""Liberty writer. Estimated timing/capacitance are explicit placeholders."""

from pathlib import Path
import re
from dd2 import interface, liberty


def cell_group(r):
    errors = interface.validate_request(r)
    if errors:
        raise ValueError("; ".join(errors))
    ins = r["inputs"]
    tt = int(r["truth_table"], 16)
    lines = [
        f'cell ("{r["name"]}") {{',
        f'  area : {r["estimated_area_um2"]:.7f};',
        "  /* Estimated area; placeholder capacitance and timing. Not characterized. */",
    ]
    for p in ins:
        lines.append(f'  pin ("{p}") {{ direction : input; capacitance : 0.0024; }}')
    lines += [
        f'  pin ("{r["output"]}") {{',
        "    direction : output;",
        f'    function : "{r["expression"]}";',
    ]
    for k, p in enumerate(ins):
        up = down = False
        for row in range(1 << len(ins)):
            if row >> k & 1:
                continue
            a = (tt >> row) & 1
            b = (tt >> (row | (1 << k))) & 1
            up |= a < b
            down |= a > b
        sense = "non_unate" if up and down else "negative_unate" if down else "positive_unate"
        lines += ["    timing () {", f'      related_pin : "{p}";', f"      timing_sense : {sense};"]
        for field in ["cell_rise", "cell_fall", "rise_transition", "fall_transition"]:
            lines.append(f'      {field} (scalar) {{ values ("0.10"); }}')
        lines.append("    }")
    return "\n".join(lines + ["  }", "}"])


def write_library(base, out, requests):
    base = Path(base)
    out = Path(out)
    text = base.read_text()
    clean = liberty._strip_comments(text)
    if not re.search(r"lu_table_template\s*\(\s*scalar\s*\)", clean):
        template = '\n  lu_table_template (scalar) { variable_1 : input_net_transition; index_1 ("0.1"); }\n'
    else:
        template = ""
    pos = text.rfind("}")
    if pos < 0:
        raise ValueError("base Liberty has no library group")
    groups = [cell_group(r) for r in requests]
    if len({r["name"] for r in requests}) != len(requests):
        raise ValueError("duplicate new cell names")
    if liberty.cell_names(base) & {r["name"] for r in requests}:
        raise ValueError("new cell clashes with baseline")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text[:pos] + template + "\n" + "\n".join(groups) + "\n" + text[pos:])
    parsed = {c.name: c for c in liberty.read_cells(out)}
    for r in requests:
        if parsed[r["name"]].tt != int(r["truth_table"], 16):
            raise ValueError("Liberty truth table mismatch")
