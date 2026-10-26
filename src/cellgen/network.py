"""Single static CMOS stages: Y = !F with F positive unate (Option 1 handout, section 3.1).

The pull-down network is a series-parallel formula for F over the inputs (an input may occur more
than once): AND is series, OR is parallel. The pull-up is its dual. In a series chain the first
operand sits nearest Y (HD's nand2_1 has A next to Y and B next to VGND). The formula chosen has the
fewest transistors with at most 3 in series in either network.
"""
from dataclasses import dataclass
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


@dataclass
class Network:
    inputs: list
    transistors: list
    formula: tuple = ()


@lru_cache(maxsize=None)
def _trees(n: int, max_lits: int) -> dict:
    """(tt, n_series, p_series, literals) -> first formula tree found, in a fixed order."""
    sizes = {1: {(bf.var_tt(k, n), 1, 1): ("lit", k) for k in range(n)}}
    for size in range(2, max_lits + 1):
        out = {}
        for a in range(1, size):
            for (ta, na, pa), xa in sorted(sizes[a].items()):
                for (tb, nb, pb), xb in sorted(sizes[size - a].items()):
                    out.setdefault((ta & tb, na + nb, max(pa, pb)), ("and", xa, xb))
                    out.setdefault((ta | tb, max(na, nb), pa + pb), ("or", xa, xb))
        sizes[size] = out
    return {(t, ns, ps, size): tree for size, d in sizes.items() for (t, ns, ps), tree in d.items()}


def best_formula(F: int, n: int, max_series: int = MAX_SERIES, max_lits: int = 8):
    cands = [(size, max(ns, ps), ns, ps, tree) for (t, ns, ps, size), tree in _trees(n, max_lits).items()
             if t == F and ns <= max_series and ps <= max_series]
    if not cands:
        return None
    return min(cands, key=lambda c: c[:4])[4]


def _build(tree, near: str, far: str, kind: str, names, counter) -> list:
    """Transistors realising tree between near (Y side) and far; PMOS uses the dual."""
    op = tree[0]
    if op == "lit":
        return [Transistor(kind, names[tree[1]], near, far)]
    series = (op == "and") if kind == "n" else (op == "or")
    a, b = tree[1], tree[2]
    if series:
        counter[0] += 1
        mid = f"{'n' if kind == 'n' else 'p'}{counter[0]}"
        return _build(a, near, mid, kind, names, counter) + _build(b, mid, far, kind, names, counter)
    return _build(a, near, far, kind, names, counter) + _build(b, near, far, kind, names, counter)


def single_stage(tt: int, inputs) -> Network:
    inputs = list(inputs)
    n = len(inputs)
    if not stage.one_stage(tt, n):
        raise ValueError("Y is not negative unate in every input: it needs more than one stage")
    tree = best_formula(bf.negate(tt, n), n)
    if tree is None:
        raise ValueError("no single stage with at most 3 transistors in series")
    counter = [0]
    pdn = _build(tree, "Y", "VGND", "n", inputs, counter)
    pun = _build(tree, "Y", "VPWR", "p", inputs, [0])
    return Network(inputs, pdn + pun, tree)


def max_series(net: Network) -> int:
    """Longest chain of transistors from Y to a rail, in either network."""
    best = 0
    for kind, rail in (("n", "VGND"), ("p", "VPWR")):
        edges = [t for t in net.transistors if t.kind == kind]

        def walk(node, used):
            nonlocal best
            for i, t in enumerate(edges):
                if i in used or node not in (t.drain, t.source):
                    continue
                nxt = t.source if node == t.drain else t.drain
                if nxt == rail:
                    best = max(best, len(used) + 1)
                elif nxt not in ("VGND", "VPWR", "Y"):
                    walk(nxt, used | {i})
        walk("Y", frozenset())
    return best


def switch_check(net: Network, tt: int) -> list:
    """Every input vector: Y driven to exactly one rail, the right one, and no rail-to-rail path."""
    errs = []
    n = len(net.inputs)
    for row in range(1 << n):
        val = {name: (row >> k) & 1 for k, name in enumerate(net.inputs)}
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for t in net.transistors:
            on = val[t.gate] == (1 if t.kind == "n" else 0)
            if on:
                parent[find(t.drain)] = find(t.source)
        up, dn = find("Y") == find("VPWR"), find("Y") == find("VGND")
        want = (tt >> row) & 1
        if find("VPWR") == find("VGND"):
            errs.append(f"row {row} {val}: short from VPWR to VGND")
        elif up and dn:
            errs.append(f"row {row} {val}: Y shorted to both rails")
        elif not up and not dn:
            errs.append(f"row {row} {val}: Y floating")
        elif up != bool(want):
            errs.append(f"row {row} {val}: Y = {int(up)}, expected {want}")
    return errs
