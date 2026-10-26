"""make m1-cuts: enumerate the 4-input cuts of every M1 AIG, check each one exhaustively, and
summarise their classes. Full cut lists go to build/ (gzip); results/ gets summaries and a sample.

Classes are taken over each cut's essential support (leaves the function really depends on), so a
cut with a redundant leaf counts with the smaller function it computes.
"""
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from . import aig as aigmod
from . import boolfn as bf
from . import cutcheck, cuts, designs, paths, provenance

SAMPLE_EVERY = 100


def classify_cut(tt: int, n: int):
    ess = bf.depends_on(tt, n)
    t = bf.shrink(tt, n, ess)
    m = len(ess)
    return m, bf.canon_pn(t, m), bf.canon_npn(t, m)


def process(aig_path: Path, out_dir: Path, full_path: Path, label: str) -> dict:
    g = aigmod.read_aiger(aig_path)
    rec = provenance.RunRecord(argv=["dd2", "cuts", paths.rel(aig_path)],
                               inputs=provenance.hash_inputs([aig_path]))
    c = cuts.enumerate_cuts(g, 4)
    fan = g.fanins()
    total = passed = 0
    failures, pc, pn, npn, by_leaves, by_support = [], Counter(), Counter(), Counter(), Counter(), Counter()
    sample = []
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(full_path, "wt") as full:
        for v in sorted(fan):
            for leaves, tt in c[v][:-1]:                   # the last cut is the trivial one
                n = len(leaves)
                total += 1
                if cutcheck.check(g, v, leaves, tt, fan):
                    passed += 1
                else:
                    failures.append({"root": v, "leaves": list(leaves), "tt": bf.to_hex(tt, n)})
                m, p, q = classify_cut(tt, n)
                pc[f"{m}:{bf.to_hex(bf.canon_p(bf.shrink(tt, n, bf.depends_on(tt, n)), m), m)}"] += 1
                by_leaves[n] += 1
                by_support[m] += 1
                pn[f"{m}:{bf.to_hex(p, m)}"] += 1
                npn[f"{m}:{bf.to_hex(q, m)}"] += 1
                row = {"root": v, "leaves": list(leaves), "tt": bf.to_hex(tt, n),
                       "support": m, "pn": bf.to_hex(p, m)}
                full.write(json.dumps(row) + "\n")
                if total % SAMPLE_EVERY == 1:
                    sample.append(row)
    checked = passed + len(failures)
    with gzip.open(full_path, "rt") as f:                # recount from the file actually written
        in_file = sum(1 for _ in f)
    expected = sum(len(c[v]) - 1 for v in fan)          # counted from the enumeration itself
    rec.finish(1 if failures or not (checked == expected == in_file) or total == 0 else 0)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{label}.sample.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sample))
    summary = {
        "aig": paths.rel(aig_path), "header": {"I": g.I, "L": g.L, "O": g.O, "A": g.A},
        "cuts_total": expected, "cuts_checked": checked, "cuts_passed": passed,
        "cuts_in_full_list": in_file, "failures": failures,
        "max_cuts_per_node": max(len(v) - 1 for v in c.values()),
        "cuts_by_leaves": dict(sorted(by_leaves.items())),
        "cuts_by_support": dict(sorted(by_support.items())),
        "pn_classes": len(pn), "npn_classes": len(npn),
        "pn_classes_4input": sum(1 for k in pn if k.startswith("4:")),
        "npn_classes_4input": sum(1 for k in npn if k.startswith("4:")),
        "p_classes": len(pc), "p_histogram": dict(pc.most_common()),
        "pn_histogram": dict(pn.most_common()), "npn_histogram": dict(npn.most_common()),
        "full_list": {"path": paths.rel(full_path), "sha256": provenance.sha256(full_path)},
        "sample": paths.rel(out_dir / f"{label}.sample.jsonl"), "sample_every": SAMPLE_EVERY,
        "run": rec.asdict(),
    }
    provenance.write_json(out_dir / f"{label}.summary.json", summary)
    return summary


def run_all(aigs: Path, out: Path, full: Path, names=None) -> int:
    names = names or [d.name for d in designs.required()]
    rows, ok = [], True
    for n in names:
        for variant in ("synth", "restructured"):
            s = process(Path(aigs) / n / f"{variant}.aig", Path(out) / n,
                        Path(full) / n / f"{variant}.jsonl.gz", variant)
            ok &= s["run"]["status"] == "pass"
            rows.append([n, variant, s["header"]["A"], s["cuts_total"], s["cuts_checked"],
                         len(s["failures"]), s["pn_classes"], s["npn_classes"],
                         s["pn_classes_4input"], s["npn_classes_4input"], s["run"]["status"]])
            print(f"{n:10s} {variant:12s} ANDs {rows[-1][2]:5d} cuts {rows[-1][3]:6d} "
                  f"failures {rows[-1][5]} PN {rows[-1][6]} NPN {rows[-1][7]} {rows[-1][-1]}")
    with open(Path(out) / "summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["design", "variant", "ands", "cuts", "checked", "failures", "pn_classes",
                    "npn_classes", "pn_classes_4input", "npn_classes_4input", "status"])
        w.writerows(rows)
    return 0 if ok else 1


def _records(path: Path):
    text = gzip.open(path, "rt").read() if path.suffix == ".gz" else path.read_text()
    if path.suffix == ".json":
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    return [json.loads(l) for l in text.splitlines() if l.strip()]


def check_file(aig_path: Path, cuts_path: Path) -> int:
    g = aigmod.read_aiger(aig_path)
    fan = g.fanins()
    bad = 0
    recs = _records(Path(cuts_path))
    if not recs:
        print(f"cutcheck: FAIL, no cuts in {cuts_path}")
        return 1
    for r in recs:
        if not cutcheck.check(g, r["root"], tuple(r["leaves"]), int(r["tt"], 16), fan):
            bad += 1
            print(f"FAIL cut root {r['root']} leaves {r['leaves']}: stored {r['tt']} disagrees "
                  "with simulation")
    print(f"cutcheck: {len(recs) - bad}/{len(recs)} cuts agree")
    return 1 if bad else 0
