"""Single static CMOS stages: Y = !F with F positive unate (Option 1 handout, section 3.1).

The pull-down network is a series-parallel formula for F over the inputs (an input may occur more
than once): AND is series, OR is parallel. The pull-up is its dual. In a series chain the first
operand sits nearest Y (HD's nand2_1 has A next to Y and B next to VGND). The formula chosen has the
fewest transistors with at most 3 in series in either network.
"""
import itertools
import math
from dataclasses import dataclass, field, replace
from functools import lru_cache

from dd2 import boolfn as bf
from dd2 import stage

MAX_SERIES = 3


@dataclass(frozen=True)
class Transistor:
    kind: str          # "n" or "p"
    gate: str
    drain: str         # the terminal nearer Y
    source: str
    w: float = 0.0     # um; 0 = not sized yet
    stage: int = 0


@dataclass(frozen=True)
class Stage:
    out: str
    tree: tuple        # the stage's F over `leaves` ("lit", k) / ("and"|"or", a, b)
    leaves: tuple      # signal names, inputs or earlier stage outputs


@dataclass
class Network:
    inputs: list
    transistors: list
    formula: tuple = ()
    stages: list = field(default_factory=list)
    output: str = "Y"


@lru_cache(maxsize=None)
def _closure(leaves: tuple, max_lits: int) -> dict:
    """(tt, n_series, p_series) -> (literals, first tree) over signals given as truth tables, keeping
    only trees within MAX_SERIES. Comparing truth tables over the inputs gives every signal's
    don't-cares for free: a formula over (A, B, nor(A, B)) only has to be right where the signals can be."""
    sizes = {1: {(t, 1, 1): ("lit", k) for k, t in reversed(list(enumerate(leaves)))}}
    seen = {key: 1 for key in sizes[1]}
    for size in range(2, max_lits + 1):
        out = {}
        for a in range(1, size // 2 + 1):
            for (ta, na, pa), xa in sorted(sizes[a].items()):
                for (tb, nb, pb), xb in sorted(sizes[size - a].items()):
                    if na + nb <= MAX_SERIES:
                        out.setdefault((ta & tb, na + nb, max(pa, pb)), ("and", xa, xb))
                    if pa + pb <= MAX_SERIES:
                        out.setdefault((ta | tb, max(na, nb), pa + pb), ("or", xa, xb))
        sizes[size] = {k: v for k, v in out.items() if k not in seen}
        seen.update({k: size for k in sizes[size]})
    return {k: (size, tree) for size, d in sizes.items() for k, tree in d.items()}


def _trees(n: int, max_lits: int) -> dict:
    return _closure(tuple(bf.var_tt(k, n) for k in range(n)), max_lits)


def best_formula(F: int, n: int, max_series: int = MAX_SERIES, max_lits: int = 8):
    return _best(tuple(bf.var_tt(k, n) for k in range(n)), F, (1 << (1 << n)) - 1, max_series, max_lits)


def _best(leaves: tuple, F: int, care: int, max_series=MAX_SERIES, max_lits=8):
    """The fewest-literal formula equal to F wherever `care` is set."""
    cands = [(lits, max(ns, ps), ns, ps, tree) for (t, ns, ps), (lits, tree) in _closure(leaves, max_lits).items()
             if (t ^ F) & care == 0 and ns <= max_series and ps <= max_series]
    return min(cands, key=lambda c: c[:4])[4] if cands else None


def _build(tree, near: str, far: str, kind: str, names, counter, stage=0) -> list:
    """Transistors realising tree between near (output side) and far; PMOS uses the dual."""
    op = tree[0]
    if op == "lit":
        return [Transistor(kind, names[tree[1]], near, far, stage=stage)]
    series = (op == "and") if kind == "n" else (op == "or")
    a, b = tree[1], tree[2]
    if series:
        counter[0] += 1
        mid = f"{'n' if kind == 'n' else 'p'}{counter[0]}"
        return _build(a, near, mid, kind, names, counter, stage) + _build(b, mid, far, kind, names, counter, stage)
    return _build(a, near, far, kind, names, counter, stage) + _build(b, near, far, kind, names, counter, stage)


def single_stage(tt: int, inputs) -> Network:
    inputs = list(inputs)
    n = len(inputs)
    if not stage.one_stage(tt, n):
        raise ValueError("Y is not negative unate in every input: it needs more than one stage")
    tree = best_formula(bf.negate(tt, n), n)
    if tree is None:
        raise ValueError("no single stage with at most 3 transistors in series")
    return _assemble(inputs, [Stage("Y", tree, tuple(inputs))])


def _assemble(inputs, stages, pdn_pun=None) -> Network:
    cn, cp, ts = [0], [0], []
    for i, s in enumerate(stages):
        pdn_tree, pun_tree = pdn_pun if pdn_pun else (s.tree, s.tree)
        ts += _build(pdn_tree, s.out, "VGND", "n", s.leaves, cn, i)
    for i, s in enumerate(stages):
        pdn_tree, pun_tree = pdn_pun if pdn_pun else (s.tree, s.tree)
        ts += _build(pun_tree, s.out, "VPWR", "p", s.leaves, cp, i)
    return Network(list(inputs), ts, stages[-1].tree, list(stages))


# ---- step 2: decomposition into stages --------------------------------------------------------

def _monotone_ok(signals, F: int, rows: int) -> bool:
    """Can F be a positive function of these signals? (sig(x) <= sig(x') and F(x)=1 needs F(x')=1.)"""
    vecs = [sum(((s >> r) & 1) << i for i, s in enumerate(signals)) for r in range(rows)]
    on = {vecs[r] for r in range(rows) if (F >> r) & 1}
    off = {vecs[r] for r in range(rows) if not (F >> r) & 1}
    return not any(a & b == a for a in on for b in off)


def _lits(tree) -> int:
    return 1 if tree[0] == "lit" else _lits(tree[1]) + _lits(tree[2])


class _Synth:
    """Signals are truth tables over the cell's inputs, so a signal's don't-cares come for free."""

    def __init__(self, n):
        self.rows, self.mask, self.count = 1 << n, (1 << (1 << n)) - 1, 0

    def name(self) -> str:
        self.count += 1
        return f"_s{self.count}"

    def last(self, sig, tt, bound):
        """The cheapest last stage for tt over sig: (cost, tree, needs_output_inverter) or None."""
        best = None
        for target, extra in ((~tt & self.mask, 0), (tt, 2)):
            lits = min(8, (bound - extra) // 2)
            if lits >= 1 and _monotone_ok(sig, target, self.rows):
                tree = _best(tuple(sig), target, self.mask, max_lits=lits)
                if tree is not None and (best is None or 2 * _lits(tree) + extra < best[0]):
                    best = (2 * _lits(tree) + extra, tree, extra)
        return best

    def pool(self, sig):
        """Stage outputs available over sig: tt -> (cost, tree), up to 4 literals, cheapest first."""
        out = {}
        for (t, _, _), (lits, tree) in _closure(tuple(sig), 4).items():
            y = ~t & self.mask
            if y and y != self.mask and y not in sig and (y not in out or 2 * lits < out[y][0]):
                out[y] = (2 * lits, tree)
        return sorted(((c, y, tree) for y, (c, tree) in out.items()), key=lambda h: h[:2])

    def plan(self, tt, names, sig, out) -> list:
        """Stages that make `out` = tt from the signals (names, sig)."""
        best = self.last(sig, tt, 44)
        chosen = (best, ()) if best else (None, ())
        cost = best[0] if best else 10 ** 9
        if cost > 8:
            helpers = self.pool(sig)
            for c, y, tree in helpers:                            # one helper stage
                if c + 2 < cost and (r := self.last(sig + (y,), tt, cost - c - 1)) and c + r[0] < cost:
                    cost, chosen = c + r[0], (r, ((y, tree, len(sig)),))
            if chosen[0] is None:
                for (ca, ya, ta), (cb, yb, tb) in itertools.combinations(helpers, 2):   # two helpers
                    if ca + cb + 2 < cost and (r := self.last(sig + (ya, yb), tt, cost - ca - cb - 1)):
                        if ca + cb + r[0] < cost:
                            cost, chosen = ca + cb + r[0], (r, ((ya, ta, len(sig)), (yb, tb, len(sig))))
                for c, y, tree in helpers:                        # a helper and its inverse (nand4)
                    if c + 4 < cost:
                        inv = ~y & self.mask
                        if (r := self.last(sig + (y, inv), tt, cost - c - 3)) and c + 2 + r[0] < cost:
                            cost, chosen = c + 2 + r[0], (r, ((y, tree, len(sig)), (inv, ("lit", len(sig)), len(sig) + 1)))
        if chosen[0] is None:
            return self.split(tt, names, sig, out)
        (_, tree, extra), helpers = chosen
        stages, names, sig = [], tuple(names), tuple(sig)
        for y, htree, nleaves in helpers:
            h = self.name()
            stages.append(Stage(h, htree, names[:nleaves]))
            names, sig = names + (h,), sig + (y,)
        if extra:
            mid = self.name()
            stages.append(Stage(mid, tree, names))
            return stages + [Stage(out, ("lit", len(names)), names + (mid,))]
        return stages + [Stage(out, tree, names)]

    def _vec(self, sig, r, skip=()):
        return tuple((s >> r) & 1 for i, s in enumerate(sig) if i not in skip)

    def split(self, tt, names, sig, out) -> list:
        """Y = f(g(a, b), rest) when such a g exists; else Shannon's expansion on one signal."""
        for a, b in itertools.combinations(range(len(sig)), 2):
            cols = {}
            for r in range(self.rows):
                pair = ((sig[a] >> r) & 1, (sig[b] >> r) & 1)
                cols.setdefault(pair, {})[self._vec(sig, r, (a, b))] = (tt >> r) & 1
            classes = []
            for pair, col in sorted(cols.items()):
                for members, merged in classes:
                    if all(merged.get(k, v) == v for k, v in col.items()):
                        members.append(pair)
                        merged.update(col)
                        break
                else:
                    classes.append(([pair], dict(col)))
            if len(classes) != 2 or len(sig) < 3:
                continue
            g = sum(1 << r for r in range(self.rows) if ((sig[a] >> r) & 1, (sig[b] >> r) & 1) in classes[1][0])
            if g in (0, self.mask):
                continue
            g_out = self.name()
            keep = [i for i in range(len(sig)) if i not in (a, b)]
            return self.plan(g, tuple(names[i] for i in (a, b)), (sig[a], sig[b]), g_out) + \
                self.plan(tt, tuple(names[i] for i in keep) + (g_out,), tuple(sig[i] for i in keep) + (g,), out)
        k = next(i for i in range(len(sig)) if self._matters(tt, sig, i))
        keep = [i for i in range(len(sig)) if i != k]
        y0, y1 = self._cofactor(tt, sig, k, 0), self._cofactor(tt, sig, k, 1)
        rest = (tuple(names[i] for i in keep), tuple(sig[i] for i in keep))
        nx, m0, m1, mid = self.name(), self.name(), self.name(), self.name()
        stages = [Stage(nx, ("lit", k), tuple(names))]
        stages += self.plan(y0, *rest, m0) + self.plan(y1, *rest, m1)
        leaves = tuple(names) + (nx, m0, m1)
        m = len(names)
        mux = ("or", ("and", ("lit", m + 1), ("lit", m)), ("and", ("lit", m + 2), ("lit", k)))
        return stages + [Stage(mid, mux, leaves), Stage(out, ("lit", m + 3), leaves + (mid,))]

    def _matters(self, tt, sig, k) -> bool:
        seen = {}
        for r in range(self.rows):
            key = self._vec(sig, r, (k,))
            bit = (tt >> r) & 1
            if seen.setdefault(key, bit) != bit:
                return True
        return False

    def _cofactor(self, tt, sig, k, v) -> int:
        """tt with signal k fixed to v: no longer a function of k."""
        table = {self._vec(sig, r, (k,)): (tt >> r) & 1 for r in range(self.rows) if (sig[k] >> r) & 1 == v}
        return sum(table.get(self._vec(sig, r, (k,)), 0) << r for r in range(self.rows))


def synthesize(tt: int, inputs) -> Network:
    """One stage when Y allows it; otherwise the fewest transistors found over: up to two helper
    stages (inverters on inputs, small stages such as xor2's nor2) with an optional output
    inverter; then a disjoint split g(a, b); then Shannon's expansion, which always ends."""
    inputs = list(inputs)
    n = len(inputs)
    sig = tuple(bf.var_tt(k, n) for k in range(n))
    mask = (1 << (1 << n)) - 1
    if tt in (0, mask) or tt in sig:
        raise ValueError("a constant or a single input is a wire, not a cell")
    if unused := [x for k, x in enumerate(inputs) if k not in bf.depends_on(tt, n)]:
        raise ValueError(f"the function does not depend on input {', '.join(unused)}")
    if stage.one_stage(tt, n) and (tree := best_formula(bf.negate(tt, n), n)) is not None:
        return _assemble(inputs, [Stage("Y", tree, tuple(inputs))])
    stages = _Synth(n).plan(tt, tuple(inputs), sig, "Y")
    return _assemble(inputs, _prune(stages))


def _prune(stages) -> list:
    """Drop stages nothing reads, and renumber nothing: names stay as planned."""
    keep, need = [], {"Y"}
    for s in reversed(stages):
        if s.out in need:
            keep.append(s)
            need |= {s.leaves[k] for k in _used(s.tree)}
    return keep[::-1]


def _used(tree) -> set:
    return {tree[1]} if tree[0] == "lit" else _used(tree[1]) | _used(tree[2])


# ---- reference cells: the installed series order and sizes -------------------------------------

def _variants(tree):
    """Every series and parallel order of a formula tree."""
    if tree[0] == "lit":
        yield tree
        return
    for a in _variants(tree[1]):
        for b in _variants(tree[2]):
            yield (tree[0], a, b)
            yield (tree[0], b, a)


def same_topology(ours, theirs) -> bool:
    return _rename(ours, theirs) is not None


def _rename(ours, theirs):
    """A mapping of our internal nets onto theirs that makes the two device sets equal, or None."""
    fixed = lambda t, rails: [x for x in t if x in rails]                # noqa: E731
    keep = {"VGND", "VPWR"} | {t.gate for t in ours}
    keep |= {"Y"}
    a = sorted({x for t in ours for x in (t.drain, t.source)} - keep)
    b = sorted({x for t in theirs for x in (t.drain, t.source)} - keep)
    if len(a) != len(b):
        return None
    want = sorted((t.kind, t.gate, tuple(sorted((t.drain, t.source)))) for t in theirs)
    for perm in itertools.permutations(b):
        m = dict(zip(a, perm))
        got = sorted((t.kind, t.gate, tuple(sorted((m.get(t.drain, t.drain), m.get(t.source, t.source))))) for t in ours)
        if got == want:
            return m
    return None


def match_installed(tt: int, inputs, installed) -> Network:
    """The generated network with the installed cell's series order and W (handout 4.1): the formula
    is the generator's; only the order of its commutative operands is read from the netlist."""
    net = single_stage(tt, inputs)
    seen = set()
    for pdn in _variants(net.formula):
        for pun in _variants(net.formula):
            if (pdn, pun) in seen:
                continue
            seen.add((pdn, pun))
            cand = _assemble(inputs, net.stages, (pdn, pun))
            m = _rename(cand.transistors, installed)
            if m is None:
                continue
            w = {(t.kind, t.gate, tuple(sorted((t.drain, t.source)))): t.w for t in installed}
            cand.transistors = [replace(t, w=w[(t.kind, t.gate, tuple(sorted((m.get(t.drain, t.drain), m.get(t.source, t.source)))))])
                                for t in cand.transistors]
            return cand
    raise ValueError("no series order of the generated formula matches the installed netlist")


# ---- step 3: sizing -----------------------------------------------------------------------------

WMAX = {"n": 0.65, "p": 1.0}          # one finger fits the HD diffusion bands (plan_hd.json reference)


def _depth(net: Network, t: Transistor) -> int:
    """Longest series chain from the stage output to a rail through transistor t."""
    out = net.stages[t.stage].out if net.stages else "Y"
    rail = "VGND" if t.kind == "n" else "VPWR"
    devs = [x for x in net.transistors if x.kind == t.kind and x.stage == t.stage]
    best = 0

    def walk(node, used):
        nonlocal best
        for x in devs:
            if x in used or node not in (x.drain, x.source):
                continue
            nxt = x.source if node == x.drain else x.drain
            if nxt == rail:
                if t in used | {x}:
                    best = max(best, len(used) + 1)
            elif nxt != out:
                walk(nxt, used | {x})
    walk(out, frozenset())
    return max(best, 1)


def size(net: Network, policy: str = "hd", wn: float = 0.65, wp: float = 1.0) -> Network:
    """hd: every finger wn/wp. stack: W times the stack depth, folded into fingers that fit the
    frame, in the last complex stage; inner stages and inverters stay x1 (handout step 3)."""
    if policy not in ("hd", "stack"):
        raise ValueError(f"unknown sizing policy {policy!r}")
    base = {"n": wn, "p": wp}
    last = len(net.stages) - 1
    # an output inverter is x1, so the stage before it is an inner stage as well
    ts = []
    for t in net.transistors:
        if t.w:
            ts.append(t)
            continue
        s = net.stages[t.stage]
        scaled = policy == "stack" and t.stage == last and s.tree[0] != "lit"
        total = base[t.kind] * (_depth(net, t) if scaled else 1)
        fingers = math.ceil(round(total / WMAX[t.kind], 6))
        ts += [replace(t, w=round(total / fingers, 3)) for _ in range(fingers)]
    return replace_transistors(net, ts)


def replace_transistors(net: Network, ts) -> Network:
    return Network(net.inputs, ts, net.formula, net.stages, net.output)


def rename_output(net: Network, name: str) -> Network:
    """HD calls the output X in cells with an output buffer."""
    swap = lambda x: name if x == net.output else x                             # noqa: E731
    return Network(net.inputs, [replace(t, drain=swap(t.drain), source=swap(t.source), gate=swap(t.gate))
                                for t in net.transistors],
                   net.formula, [replace(s, out=swap(s.out)) for s in net.stages], name)


def max_series(net: Network) -> int:
    """Most transistors in series from a stage output to a rail, in either network. A path visits
    each net once, so parallel fingers of one transistor count once."""
    best = 0
    outs = {s.out for s in net.stages} or {"Y"}
    for kind, rail in (("n", "VGND"), ("p", "VPWR")):
        for out in outs:
            edges = [t for t in net.transistors if t.kind == kind and (not net.stages or net.stages[t.stage].out == out)]

            def walk(node, seen, depth):
                nonlocal best
                for t in edges:
                    if node not in (t.drain, t.source):
                        continue
                    nxt = t.source if node == t.drain else t.drain
                    if nxt == rail:
                        best = max(best, depth + 1)
                    elif nxt not in seen and nxt not in ("VGND", "VPWR", out):
                        walk(nxt, seen | {nxt}, depth + 1)
            walk(out, {out}, 0)
    return best


def switch_check(net: Network, tt: int) -> list:
    """Every input vector, stage by stage: each stage output driven to exactly one rail, Y to the
    right one, and never a path from VPWR to VGND."""
    errs = []
    n = len(net.inputs)
    stages = range(len(net.stages)) if net.stages else [None]
    for row in range(1 << n):
        val = {name: (row >> k) & 1 for k, name in enumerate(net.inputs)}
        shown = dict(val)
        for s in stages:
            out = net.stages[s].out if s is not None else "Y"
            parent = {}

            def find(x):
                parent.setdefault(x, x)
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for t in net.transistors:
                if s is not None and t.stage != s:
                    continue
                if t.gate not in val:
                    errs.append(f"row {row} {shown}: gate {t.gate} is read before it is driven")
                    continue
                if val[t.gate] == (1 if t.kind == "n" else 0):
                    parent[find(t.drain)] = find(t.source)
            up, dn = find(out) == find("VPWR"), find(out) == find("VGND")
            if find("VPWR") == find("VGND"):
                errs.append(f"row {row} {shown}: short from VPWR to VGND")
            elif up and dn:
                errs.append(f"row {row} {shown}: {out} shorted to both rails")
            elif not up and not dn:
                errs.append(f"row {row} {shown}: {out} floating")
            val[out] = int(up)
        want = (tt >> row) & 1
        if "Y" in val and val["Y"] != want and not any(e.startswith(f"row {row} ") for e in errs):
            errs.append(f"row {row} {shown}: Y = {val['Y']}, expected {want}")
    return errs
