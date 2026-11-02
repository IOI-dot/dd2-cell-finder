"""Paired Euler-path gate ordering (Uehara and van Cleemput; Option 1 handout, step 4).

Each gate is one vertical poly stripe, so the NMOS and the PMOS rows use one gate sequence. A stage
is ordered on its own: every distinct sequence of its stripes is tried (bounded), and a row is
fitted to a sequence by dynamic programming over which transistor sits at each stripe and which
way round, for the fewest diffusion breaks. A stripe may have no device in one row when folding
gives that input more fingers in the other row; the poly stops short of that row. Stages are then
placed left to right, each possibly mirrored, sharing the rails where they meet.
"""
import itertools
import random
from dataclasses import dataclass, field
from functools import lru_cache
from math import factorial
from typing import NamedTuple

SEARCH_LIMIT = 20000
KEEP = 12


class Slot(NamedTuple):
    left: str
    right: str
    w: float = 0.0
    stage: int = 0


@dataclass
class Ordering:
    gates: list
    rows: dict                       # "n"/"p" -> list of segments, each a list of nets
    breaks: int
    slots: dict = None               # "n"/"p" -> one Slot or None per gate
    row_breaks: dict = field(default_factory=dict)


def _segments(slots) -> list:
    segs = []
    for s in slots:
        if s is None:
            continue
        if segs and segs[-1][-1] == s.left:
            segs[-1].append(s.right)
        else:
            segs.append([s.left, s.right])
    return segs


def _fit(gates: tuple, devices: tuple, rail: str) -> tuple:
    """Place devices (kept by type) on the stripes, fewest breaks, then rails at the row ends:
    (breaks, slots)."""
    types = sorted(set(devices))
    counts = tuple(devices.count(t) for t in types)
    later = {}
    for i in range(len(gates) - 1, -1, -1):
        later[i] = sum(1 for g in gates[i + 1:] if g == gates[i])

    @lru_cache(maxsize=None)
    def go(i, last, left):
        if i == len(gates):
            return ((0, 2 * (last != rail)), ()) if not any(left) else None
        best = None
        here = [k for k, t in enumerate(types) if t[0] == gates[i] and left[k]]
        for k in here:
            _, a, b, w, st = types[k]
            nxt = left[:k] + (left[k] - 1,) + left[k + 1:]
            for x, y in ((a, b), (b, a)) if a != b else ((a, b),):
                sub = go(i + 1, y, nxt)
                if sub is not None:
                    c = (sub[0][0] + (last is not None and last != x), sub[0][1] + 3 * (last is None and x != rail))
                    if best is None or c < best[0]:
                        best = (c, (Slot(x, y, w, st),) + sub[1])
        if sum(left[k] for k in here) <= later[i]:          # no device at this stripe in this row
            sub = go(i + 1, last, left)
            if sub is not None and (best is None or sub[0] < best[0]):
                best = (sub[0], (None,) + sub[1])
        return best

    r = go(0, None, counts)
    if r is None:
        raise ValueError(f"cannot place {devices} on {gates}")
    return r[0][0], list(r[1])


def _types(ts) -> tuple:
    return tuple(sorted((t.gate, t.drain, t.source, t.w, t.stage) for t in ts))


def _sequences(multiset, seed_orders=()):
    """Distinct stripe sequences, bounded: all of them when few, else a fixed random sample."""
    total = factorial(len(multiset))
    for g in set(multiset):
        total //= factorial(multiset.count(g))
    if total <= SEARCH_LIMIT:
        yield from sorted(set(itertools.permutations(sorted(multiset)))) if len(multiset) <= 9 else _distinct(multiset)
        return
    yield from seed_orders
    rng = random.Random(0)                                   # the search stays deterministic
    seen = set()
    groups = sorted(set(multiset))
    for _ in range(SEARCH_LIMIT):
        if rng.random() < 0.5:                               # keep each input's fingers together
            rng.shuffle(groups)
            q = tuple(g for x in groups for g in [x] * multiset.count(x))
        else:
            q = list(multiset)
            rng.shuffle(q)
            q = tuple(q)
        if q not in seen:
            seen.add(q)
            yield q


def _distinct(multiset):
    counts = {g: multiset.count(g) for g in sorted(set(multiset))}

    def rec(prefix):
        if len(prefix) == len(multiset):
            yield tuple(prefix)
            return
        for g in counts:
            if counts[g]:
                counts[g] -= 1
                prefix.append(g)
                yield from rec(prefix)
                prefix.pop()
                counts[g] += 1
    return rec([])


def _spread(seq) -> int:
    """Same-input stripes that are not neighbours: each one needs a wire instead of a poly bridge."""
    runs = sum(1 for i, g in enumerate(seq) if i == 0 or seq[i - 1] != g)
    return runs - len(set(seq))


def stage_orders(ns, ps, keep=KEEP) -> list:
    """The best gate sequences of one stage: (key, gates, n slots, p slots), best first."""
    nt, pt = _types(ns), _types(ps)
    gates = sorted({t.gate for t in ns} | {t.gate for t in ps})
    multiset = [g for g in gates for _ in range(max(sum(t.gate == g for t in ns), sum(t.gate == g for t in ps)))]
    out = []
    for seq in _sequences(multiset):
        nb, nslots = _fit(seq, nt, "VGND")
        pb, pslots = _fit(seq, pt, "VPWR")
        first = lambda sl, rail: next((s.left for s in sl if s), None) != rail     # noqa: E731
        key = (nb + pb, _spread(seq), first(nslots, "VGND"), first(pslots, "VPWR"))
        out.append((key, list(seq), nslots, pslots))
    out.sort(key=lambda r: (r[0], r[1]))
    return out[:keep]


def _flip(gates, slots):
    return gates[::-1], {r: [None if s is None else Slot(s.right, s.left, s.w, s.stage) for s in sl[::-1]]
                         for r, sl in slots.items()}


def _breaks(slots) -> int:
    return len(_segments(slots)) - 1


def _make(gates, slots) -> Ordering:
    rb = {r: _breaks(sl) for r, sl in slots.items()}
    return Ordering(list(gates), {r: _segments(sl) for r, sl in slots.items()}, sum(rb.values()), slots, rb)


def _join(parts) -> tuple:
    """Concatenate stage orders, mirroring stages for the fewest breaks where they meet."""
    best = None
    choices = itertools.product((False, True), repeat=len(parts)) if len(parts) <= 8 else [(False,) * len(parts)]
    for flips in choices:
        gates, slots = [], {"n": [], "p": []}
        for flip, (g, sl) in zip(flips, parts):
            g2, s2 = _flip(g, sl) if flip else (g, sl)
            gates += g2
            for r in slots:
                slots[r] = slots[r] + s2[r]
        key = sum(_breaks(sl) for sl in slots.values())
        if best is None or key < best[0]:
            best = (key, gates, slots)
    return best[1], best[2]


def candidates(net, keep=KEEP) -> list:
    """Orderings to try, best first; the layout takes the first that routes."""
    stages = sorted({t.stage for t in net.transistors})
    per = []
    for s in stages:
        ns = [t for t in net.transistors if t.stage == s and t.kind == "n"]
        ps = [t for t in net.transistors if t.stage == s and t.kind == "p"]
        per.append([(o[1], {"n": o[2], "p": o[3]}) for o in stage_orders(ns, ps, keep)])
    if len(per) == 1:
        return [_make(g, sl) for g, sl in per[0]]
    out, seen = [], set()
    pools = [p[:3] for p in per]
    for combo in itertools.islice(itertools.product(*pools), 64):
        for stage_seq in (list(combo), list(combo)[::-1]):
            g, sl = _join(stage_seq)
            o = _make(g, sl)
            key = (tuple(o.gates), str(o.rows))
            if key not in seen:
                seen.add(key)
                out.append(o)
    out.sort(key=lambda o: o.breaks)
    return out[:max(keep, 24)]


def order(net) -> Ordering:
    return candidates(net)[0]


def validate(net, o: Ordering) -> list:
    """Each row must hold exactly the network's transistors, at stripes of their own gates."""
    errs = []
    for kind in ("n", "p"):
        want = sorted((t.gate, tuple(sorted((t.drain, t.source)))) for t in net.transistors if t.kind == kind)
        got = []
        if o.slots:
            if len(o.slots[kind]) != len(o.gates):
                errs.append(f"{kind}: {len(o.slots[kind])} slots for {len(o.gates)} gates")
            for g, s in zip(o.gates, o.slots[kind]):
                if s is not None:
                    got.append((g, tuple(sorted((s.left, s.right)))))
        else:
            k = 0
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
