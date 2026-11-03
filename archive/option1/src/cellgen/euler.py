"""Paired Euler-path gate ordering (Uehara and van Cleemput; Option 1 handout, step 4).

Each gate is one vertical poly stripe crossing both diffusion rows, so the NMOS and the PMOS rows
must use one gate sequence. A row is a list of diffusion segments; a segment is the list of nets
along it (len = transistors + 1), and consecutive transistors in a segment share diffusion. A new
segment is a diffusion break. The search tries every gate order (at most 6 transistors per row
for a single stage), orients each transistor to share diffusion where it can, and keeps the order
with the fewest breaks; ties prefer rails at the left end, then the earliest order found.
"""
import itertools
from dataclasses import dataclass


@dataclass
class Ordering:
    gates: list
    rows: dict          # "n"/"p" -> list of segments, each a list of nets
    breaks: int


def _row(edges, rail):
    """Orient edges (in this order) to share diffusion: returns (breaks, segments).
    Among orientations with the fewest breaks, prefer the rail at the left end."""
    best = None
    for flips in itertools.product((0, 1), repeat=len(edges)):
        segs, breaks = [], 0
        for (a, b), f in zip(edges, flips):
            left, right = (b, a) if f else (a, b)
            if segs and segs[-1][-1] == left:
                segs[-1].append(right)
            else:
                if segs:
                    breaks += 1
                segs.append([left, right])
        key = (breaks, segs[0][0] != rail)
        if best is None or key < best[0]:
            best = (key, breaks, segs)
    return best[1], best[2]


def order(net) -> Ordering:
    ns = [t for t in net.transistors if t.kind == "n"]
    ps = [t for t in net.transistors if t.kind == "p"]
    best = None
    for perm in itertools.permutations(range(len(ns))):
        gates = [ns[i].gate for i in perm]
        nb, nsegs = _row([(ns[i].drain, ns[i].source) for i in perm], "VGND")
        # PMOS: same gate sequence; repeated inputs may pair with any same-gate PMOS
        pools = {g: [i for i, t in enumerate(ps) if t.gate == g] for g in set(gates)}
        for choice in itertools.product(*[itertools.permutations(pools[g]) for g in sorted(pools)]):
            pick = dict(zip(sorted(pools), (list(c) for c in choice)))
            seq = [pick[g].pop(0) for g in gates]
            pb, psegs = _row([(ps[i].drain, ps[i].source) for i in seq], "VPWR")
            rails = (nsegs[0][0] != "VGND", psegs[0][0] != "VPWR")
            key = (nb + pb, rails)
            if best is None or key < best[0]:
                best = (key, Ordering(gates, {"n": nsegs, "p": psegs}, nb + pb))
    return best[1]


def validate(net, o: Ordering) -> list:
    """Each row must contain exactly the network's transistors, in the gate order given."""
    errs = []
    for kind in ("n", "p"):
        want = sorted((t.gate, tuple(sorted((t.drain, t.source)))) for t in net.transistors if t.kind == kind)
        got, k = [], 0
        for seg in o.rows[kind]:
            for a, b in zip(seg, seg[1:]):
                if k >= len(o.gates):
                    errs.append(f"{kind}: more transistors than gates")
                    break
                got.append((o.gates[k], tuple(sorted((a, b)))))
                k += 1
        if sorted(got) != want:
            errs.append(f"{kind} row {o.rows[kind]} does not realise the network {want}")
    return errs
