"""k-feasible cut enumeration (references 10, 11) with bit-parallel truth tables.

A cut of node v is a set of leaves such that every path from a combinational input to v passes
through a leaf. Cuts of an AND node are merges of its fanins' cuts with at most k leaves; a cut
that is a superset of another cut of the same node is dominated and dropped. Combinational inputs
(primary inputs and latch outputs) only have their trivial cut. Truth tables are over the leaves
in ascending order, leaf 0 being the LSB of the row index (Appendix A).
"""
from functools import lru_cache


@lru_cache(maxsize=None)
def _rowmap(pos: tuple, n: int) -> tuple:
    """For each row of the n-leaf union, the row index of the sub-cut whose leaves sit at pos."""
    return tuple(sum(((r >> p) & 1) << b for b, p in enumerate(pos)) for r in range(1 << n))


@lru_cache(maxsize=1 << 20)
def _expand(tt: int, pos: tuple, n: int) -> int:
    out = 0
    for r, j in enumerate(_rowmap(pos, n)):
        if (tt >> j) & 1:
            out |= 1 << r
    return out


def _lift(leaves, tt, union, compl):
    pos = tuple(union.index(l) for l in leaves)
    n = len(union)
    t = _expand(tt, pos, n)
    return t ^ ((1 << (1 << n)) - 1) if compl else t


def enumerate_cuts(g, k: int = 4) -> dict:
    """var -> list of (leaves, tt): non-trivial cuts sorted by leaves, then the trivial cut."""
    cuts = {0: [((), 0)]}
    for v in range(1, g.I + g.L + 1):
        cuts[v] = [((v,), 0b10)]
    for lhs, r0, r1 in g.ands:
        v = lhs >> 1
        found = {}
        for la, ta in cuts[r0 >> 1]:
            for lb, tb in cuts[r1 >> 1]:
                union = tuple(sorted(set(la) | set(lb)))
                if len(union) > k or union in found:
                    continue
                found[union] = _lift(la, ta, union, r0 & 1) & _lift(lb, tb, union, r1 & 1)
        sets = sorted(found, key=len)
        kept = []
        for u in sets:
            su = set(u)
            if not any(set(w) < su for w in kept):
                kept.append(u)
        cuts[v] = sorted((u, found[u]) for u in kept) + [((v,), 0b10)]
    return cuts
