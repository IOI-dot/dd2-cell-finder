"""Option 2's side of Option 3: map the designs onto the cells Option 1 really built.

Only a response with status pass is used (Appendix A). Its Liberty cell group, with the real area and the
characterized tables, takes the place of the estimated group of src/dd2m2/library.py. The designs are then
mapped with and without the new cells by the same steps as M2, on this machine's tools, into
results/option3/. The M2 evidence in results/m2/ is never touched.
"""
import json
import re
from pathlib import Path

from dd2 import designs, liberty, paths, provenance

from . import flow


def _group(text: str, kind: str, name: str) -> str:
    """The text of one Liberty group, braces matched, such as cell ("x") { ... }."""
    m = re.search(rf'{kind}\s*\(\s*"?{re.escape(name)}"?\s*\)\s*{{', text)
    if not m:
        raise ValueError(f"no {kind} {name} in the delivered Liberty")
    depth, i = 0, m.end() - 1
    for i in range(m.end() - 1, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            break
    return text[m.start():i + 1]


def real_library(base: Path, out: Path, pairs) -> list:
    """pairs: (request, response). Writes base plus every passing delivered cell; returns the requests used."""
    text = Path(base).read_text()
    groups, templates, used = [], {}, []
    for req, resp in pairs:
        if resp.get("status") != "pass":
            continue
        lib = Path(resp["files"]["liberty"])
        lib = lib if lib.is_absolute() else paths.ROOT / lib
        cell = {c.name: c for c in liberty.read_cells(lib)}.get(req["name"])
        if cell is None or cell.tt != int(req["truth_table"], 16):
            raise ValueError(f"{req['name']}: the delivered Liberty function does not match the requested truth table")
        lt = lib.read_text()
        for t in re.findall(r'lu_table_template\s*\(\s*"?([\w]+)"?\s*\)', lt):
            templates[t] = _group(lt, "lu_table_template", t)
        groups.append(_group(lt, "cell", req["name"]))
        used.append(req | {"area_um2": resp["area_um2"]})
    if liberty.cell_names(base) & {r["name"] for r in used}:
        raise ValueError("a delivered cell has the name of a baseline cell")
    pos = text.rfind("}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(text[:pos] + "\n".join(templates.values()) + "\n" + "\n".join(groups) + "\n" + text[pos:])
    return used


def compare_row(req: dict, resp: dict) -> dict:
    est, real = req["estimated_area_um2"], resp.get("area_um2") or 0
    ok = resp.get("status") == "pass"
    return {"request_id": req["request_id"], "cell": req["name"], "status": resp.get("status", "missing"), "estimated_area_um2": est,
            "real_area_um2": real if ok else None, "area_error_pct": round(100 * (real - est) / est, 2) if ok else None,
            "reason": resp.get("reason") or ""}


def run(out: Path | None = None, m2: Path | None = None) -> int:
    out = Path(out or paths.results("option3")).absolute()
    m2 = Path(m2 or paths.results("m2"))
    out.mkdir(parents=True, exist_ok=True)
    pairs = []
    for req in json.loads((m2 / "requests.json").read_text()):
        p = paths.ROOT / "cells" / req["name"] / "response.json"
        pairs.append((req, json.loads(p.read_text()) if p.is_file() else {"status": "missing", "reason": "Option 1 has not answered"}))
    flow.write_csv(out / "cells.csv", [compare_row(q, r) for q, r in pairs])
    lib = out / "hd_extended_real.lib"
    used = real_library(paths.given() / "hd_reduced.lib", lib, pairs)
    provenance.write_json(out / "requests_used.json", used)
    if not used:
        print("No delivered cell passed, so there is nothing to map with.")
        return 1
    names = [d.name for d in designs.required()]
    flow.baseline(names, out)
    rows, best = flow.measure(names, out, lib, used)
    provenance.write_json(out / "summary.json", {"cells_requested": len(pairs), "cells_used": len(used),
                                                 "mappings": len(rows), "equivalence_all_pass": all(r["extended_equivalence"] == "pass" for r in rows),
                                                 "best_of_both": best, "toolchain": "this machine's Yosys, ABC and OpenSTA, same on both sides"})
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
