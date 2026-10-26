"""make demo IN=<design.v>: the M1 front end on one design, written only to build/demo/<name>/."""
from collections import Counter
from pathlib import Path

from . import aig, boolfn as bf, cutflow, liberty, mapping, paths, provenance, redundancy
from .designs import Design


def run(src: Path, top: str | None, sv: bool, given: Path, pdk: Path) -> int:
    src = Path(src).absolute()
    if not src.is_file():
        print(f"design not found: {src}")
        return 2
    d = Design(src.stem, top or src.stem, required=False, sv=sv)
    out = paths.build("demo", d.name)
    ok = True
    areas = {}
    for lib in mapping.LIBRARIES:
        for s in mapping.SCRIPTS:
            r = mapping.run_mapping(d, lib, s, out / "baseline", given, src)
            ok &= r["run"]["status"] == "pass"
            areas[f"{lib}/{s}"] = r.get("area_um2")
            print(f"map {lib:8s} {s}: {r.get('area_um2', 'FAIL')}")
    arts = aig.extract_design(d, given, out / "aigs", src)
    idx = redundancy.HdIndex(liberty.read_cells(paths.full_hd_lib(pdk)))
    summary = {"design": str(src), "top": d.top, "areas_um2": areas, "variants": {}}
    for v, a in arts.items():
        ok &= a["run"]["status"] == "pass"
        if a["run"]["status"] != "pass":
            continue
        s = cutflow.process(out / "aigs" / d.name / f"{v}.aig", out / "cuts", out / "cuts" / f"{v}.jsonl.gz", v)
        ok &= s["run"]["status"] == "pass"
        four = Counter({k: n for k, n in s["pn_histogram"].items() if k.startswith("4:")})
        classes = Counter()
        for key, n in four.items():
            classes[redundancy.classify(int(key[2:], 16), 4, idx)["class"]] += n
        summary["variants"][v] = {"ands": a["header"]["A"], "cuts": s["cuts_total"],
                                  "failures": len(s["failures"]), "pn_classes": s["pn_classes"],
                                  "four_input_pn_classes": len(four),
                                  "four_input_cuts_by_redundancy_class": dict(classes),
                                  "top_new_4input": [k for k in four if redundancy.classify(
                                      int(k[2:], 16), 4, idx)["class"] == "New"][:10]}
        print(f"{v}: ANDs {a['header']['A']} cuts {s['cuts_total']} failures {len(s['failures'])} "
              f"4-input cuts by class {dict(classes)}")
    summary["status"] = "pass" if ok else "fail"
    provenance.write_json(out / "demo_summary.json", summary)
    print(f"demo: {summary['status']} ({paths.rel(out / 'demo_summary.json')})")
    return 0 if ok else 1
