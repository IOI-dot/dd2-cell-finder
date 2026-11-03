"""Step 0: the tools and supplied inputs Option 2 needs, recorded with their versions."""

import re
import sys

from dd2 import designs, envcheck, paths, provenance, tools


def check(out, strict=False):
    versions = tools.versions()
    problems = []
    notes = []
    needed = [paths.given() / p for p in ["hd_reduced.lib", "hd_usable.lib", "scripts/map.sh"]]
    needed += [paths.given() / "designs" / f"{d.name}.v" for d in designs.required()]
    full = paths.full_hd_lib()
    needed.append(full)
    for p in needed:
        if not p.is_file():
            problems.append(f"missing {paths.rel(p)}; run make setup")
    if sys.version_info < (3, 11):
        problems.append("Python >=3.11 required")
    for key in ["yosys", "yosys-abc", "iverilog", "sta"]:
        if not versions.get(key):
            problems.append(f"{key} missing")
    imports = {}
    if versions.get("yosys"):
        for name, count in [("hd_reduced.lib", 189), ("hd_usable.lib", 307)]:
            p = paths.given() / name
            if p.is_file():
                imports[name] = envcheck.liberty_import_count(p, paths.build("check", name + ".log"))
                if imports[name] != count:
                    problems.append(f"{name}: expected {count} cells, got {imports[name]}")

    def version_tuple(text):
        m = re.search(r"(\d+)\.(\d+)", text or "")
        return tuple(map(int, m.groups())) if m else (0, 0)

    overview = {
        "python_3_11_or_newer": sys.version_info >= (3, 11),
        "yosys_0_34_or_newer": version_tuple(versions.get("yosys")) >= (0, 34),
        "iverilog_13_or_newer": version_tuple(versions.get("iverilog")) >= (13, 0),
        "opensta_recent": bool(versions.get("sta")),
    }
    if not overview["yosys_0_34_or_newer"]:
        notes.append(
            "Yosys 0.33 is the Option 2 Table 1 reference version; overview lists >=0.34. Keep a separate reference executable."
        )
    if not overview["iverilog_13_or_newer"]:
        notes.append("Overview lists Icarus >=13; install before checkpoint validation.")
    if strict and not all(overview.values()):
        problems.append("overview minimum tool versions not all satisfied")
    data = {
        "status": "fail" if problems else "pass",
        "tools": versions,
        "overview_versions": overview,
        "liberty_import": imports,
        "problems": problems,
        "notes": notes,
        "inputs": provenance.hash_inputs([p for p in needed if p.is_file()]),
        "checked": provenance.now(),
        "scope": "Option 2 native CLI; no Option 1 GDS/SPICE checks are claimed",
    }
    provenance.write_json(out, data)
    for p in problems:
        print("FAIL", p)
    for p in notes:
        print("NOTE", p)
    print("Option 2 environment:", data["status"], flush=True)
    return not problems
