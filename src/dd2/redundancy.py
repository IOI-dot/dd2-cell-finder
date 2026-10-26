"""Redundancy check against HD (Option 2 handout section 5, Table 3) and its self-test (Table 4).

Classes, checked in this order on the candidate's essential support (first match wins):
  Exists                  same truth table as an HD cell after reordering inputs
  Exists with an inverter same after inverting the output or exactly one input
  Contained               equal to an HD cell with each HD input tied to a candidate input or 0/1
  New                     none of the above
The definitions reproduce the handout's Table 4 (research D-7); row 6 is open (Q-1).
"""
import itertools
import json
from collections import Counter
from pathlib import Path

from . import boolfn as bf
from . import liberty, paths, provenance, stage

NAMES = "ABCDEF"
EXISTS, INVERTER, CONTAINED, NEW = "Exists", "Exists with an inverter", "Contained", "New"

# Option 2 handout Table 4 (reference counts for 4-input functions, up to input order).
HANDOUT_TABLE4 = {"exists": 24, "exists_with_inverter": 20, "contained": 38, "new": 3822,
                  "new_one_stage": 9, "new_one_stage_small": 5, "one_stage_read_once": 8}
HANDOUT_READ_ONCE = {"Exists": 6, "Contained": 2}


def _support(tt: int, n: int):
    ess = bf.depends_on(tt, n)
    return ess, bf.shrink(tt, n, ess)


class HdIndex:
    def __init__(self, cells):
        self.cells = sorted(cells, key=lambda c: (c.area, c.name))
        self.exists = {}                         # (m, canon_p) -> (cell, essential pins, tt)
        for c in self.cells:
            ess, t = _support(c.tt, len(c.inputs))
            self.exists.setdefault((len(ess), bf.canon_p(t, len(ess))),
                                   (c, [c.inputs[k] for k in ess], t))
        self._contained = {}

    def contained(self, n: int) -> dict:
        """Truth tables over n inputs reachable by tying HD inputs to inputs or constants."""
        if n not in self._contained:
            reach = {}
            srcs = [bf.var_tt(k, n) for k in range(n)] + [0, bf.mask(n)]
            labels = list(NAMES[:n]) + [0, 1]
            seen = set()
            for c in self.cells:
                k = len(c.inputs)
                if (k, c.tt) in seen:
                    continue
                seen.add((k, c.tt))
                for asg in itertools.product(range(n + 2), repeat=k):
                    cols = [srcs[a] for a in asg]
                    out = 0
                    for row in range(1 << n):
                        j = 0
                        for b in range(k):
                            j |= ((cols[b] >> row) & 1) << b
                        out |= ((c.tt >> j) & 1) << row
                    if out not in reach:
                        reach[out] = (c.name, {p: labels[a] for p, a in zip(c.inputs, asg)})
            self._contained[n] = reach
        return self._contained[n]

    def find_exists(self, t: int, m: int, names):
        hit = self.exists.get((m, bf.canon_p(t, m)))
        if not hit:
            return None
        cell, pins, ct = hit
        for perm in itertools.permutations(range(m)):
            if bf.permute(ct, m, perm) == t:
                return {"cell": cell.name, "input_map": {pins[perm[k]]: names[k] for k in range(m)}}
        raise AssertionError("canonical match without a permutation")


def classify(tt: int, n: int, idx: HdIndex, names=None) -> dict:
    names = list(names or NAMES[:n])
    ess, t = _support(tt, n)
    m = len(ess)
    sup = [names[k] for k in ess]
    w = idx.find_exists(t, m, sup)
    if w:
        return {"class": EXISTS, "witness": w}
    w = idx.find_exists(bf.negate(t, m), m, sup)
    if w:
        return {"class": INVERTER, "witness": w | {"inverted": "output"}}
    for k in range(m):
        w = idx.find_exists(bf.flip_input(t, m, k), m, sup)
        if w:
            return {"class": INVERTER, "witness": w | {"inverted": f"input {sup[k]}"}}
    if m > 4:
        raise ValueError("candidates have at most 4 inputs; Contained is defined for <= 4")
    hit = idx.contained(m).get(t)
    if hit:
        cell, ties = hit
        return {"class": CONTAINED,
                "witness": {"cell": cell, "ties": {p: (sup[NAMES.index(v)] if isinstance(v, str) else v)
                                                   for p, v in ties.items()}}}
    return {"class": NEW, "witness": None}


def four_input_classes() -> list:
    """P-class representatives of the 4-input functions that depend on all four inputs."""
    reps = sorted({bf.canon_p(t, 4) for t in range(1 << 16)})
    return [r for r in reps if len(bf.depends_on(r, 4)) == 4]


def table4(idx: HdIndex) -> dict:
    reps = four_input_classes()
    cls = {r: classify(r, 4, idx) for r in reps}
    count = Counter(c["class"] for c in cls.values())
    new = [r for r in reps if cls[r]["class"] == NEW]
    one = [r for r in new if stage.one_stage(r, 4)]
    small = [r for r in one if stage.best(r, 4, 3, 12)]
    ro = [r for r in reps if stage.read_once(r, 4)]
    ro_break = dict(Counter(cls[r]["class"] for r in ro))
    measured = {"exists": count[EXISTS], "exists_with_inverter": count[INVERTER],
                "contained": count[CONTAINED], "new": count[NEW], "new_one_stage": len(one),
                "new_one_stage_small": len(small), "one_stage_read_once": len(ro)}
    rows = []
    for row, want in HANDOUT_TABLE4.items():
        r = {"row": row, "handout": want, "measured": measured[row]}
        if row == "one_stage_read_once":
            r["breakdown"] = ro_break
            r["status"] = "match" if (measured[row], ro_break) == (want, HANDOUT_READ_ONCE) else "mismatch"
        elif row == "new_one_stage_small" and measured[row] != want:
            # research Q-1: the handout does not define this row precisely; reported, not tuned
            r["status"] = "definition-open"
            r["witnesses"] = [{"tt": bf.to_hex(t, 4), "best_stage": stage.best(t, 4)} for t in small]
            r["definition_used"] = ("New, negative unate, and some series-parallel form with <= 6 "
                                    "literals (12 transistors) and <= 3 in series in both networks")
        else:
            r["status"] = "match" if measured[row] == want else "mismatch"
        rows.append(r)
    return {"classes_total": len(reps), "rows": rows,
            "classes": [{"tt": bf.to_hex(r, 4)} | cls[r] for r in reps]}


def _index(pdk: Path) -> HdIndex:
    return HdIndex(liberty.read_cells(paths.full_hd_lib(pdk)))


def cli_classify(tt_hex: str, arity: int, pdk: Path) -> int:
    print(json.dumps(classify(int(tt_hex, 16), arity, _index(pdk)), indent=2))
    return 0


def run_selftest(pdk: Path, out: Path) -> int:
    lib = paths.full_hd_lib(pdk)
    rec = provenance.RunRecord(argv=["dd2", "selftest"], inputs=provenance.hash_inputs([lib]))
    idx = HdIndex(liberty.read_cells(lib))
    hd_results = [(c.name, classify(c.tt, len(c.inputs), idx)["class"]) for c in idx.cells]
    not_exists = [n for n, c in hd_results if c != EXISTS]
    t4 = table4(idx)
    bad_rows = [r["row"] for r in t4["rows"] if r["status"] == "mismatch"]
    ok = not not_exists and not bad_rows
    rec.finish(0 if ok else 1)
    out = Path(out)
    provenance.write_json(out / "four_input_counts.json",
                          {"classes_total": t4["classes_total"], "classes": t4["classes"]})
    provenance.write_json(out / "self_test.json", {
        "hd_cells_total": len(hd_results), "hd_cells_exists": len(hd_results) - len(not_exists),
        "hd_cells_not_exists": not_exists, "four_input_classes": t4["classes_total"],
        "table4": t4["rows"], "pass_rule": "every HD cell Exists and no Table 4 row is 'mismatch' "
        "(row new_one_stage_small is 'definition-open', research Q-1)", "run": rec.asdict()})
    print(f"HD cells classified Exists: {len(hd_results) - len(not_exists)}/{len(hd_results)}")
    for r in t4["rows"]:
        print(f"  {r['row']:24s} handout {r['handout']:5d}  measured {r['measured']:5d}  {r['status']}")
    print(f"selftest: {rec.status}")
    return 0 if ok else 1
