"""Single static CMOS stage costing (research D-7).

A stage computes Y = !F with F positive unate, built as a series-parallel formula over positive
literals (a literal may repeat). Each literal is one NMOS and one PMOS, so transistors = 2 x
literals. In the pull-down network AND is series (depths add) and OR is parallel (max); the
pull-up is the dual (AND parallel, OR series). points() lists every reachable
(literals, n_series, p_series) for F up to max_lits literals.
"""
from functools import lru_cache

from . import boolfn as bf


@lru_cache(maxsize=None)
def _by_size(n: int, max_lits: int) -> tuple:
    sizes = {1: {(bf.var_tt(k, n), 1, 1) for k in range(n)}}
    for size in range(2, max_lits + 1):
        s = set()
        for a in range(1, size // 2 + 1):
            for ta, na, pa in sizes[a]:
                for tb, nb, pb in sizes[size - a]:
                    s.add((ta & tb, na + nb, max(pa, pb)))
                    s.add((ta | tb, max(na, nb), pa + pb))
        sizes[size] = s
    return tuple(sorted(sizes.items()))


def points(F: int, n: int, max_lits: int = 8) -> set:
    return {(size, ns, ps) for size, s in _by_size(n, max_lits) for t, ns, ps in s if t == F}


def one_stage(Y: int, n: int) -> bool:
    """Y is one stage iff it is negative unate in every input (F = !Y positive unate)."""
    F = bf.negate(Y, n)
    for k in range(n):
        # rows with x_k = 1 where F(x_k=0) = 1 but F(x_k=1) = 0
        if bf.flip_input(F, n, k) & ~F & bf.var_tt(k, n):
            return False
    return True


def best(Y: int, n: int, max_series: int = 3, max_transistors: int = 12):
    """Fewest-transistor single stage within the limits, as (literals, n_series, p_series)."""
    if not one_stage(Y, n):
        return None
    ok = [p for p in points(bf.negate(Y, n), n, max_transistors // 2)
          if p[1] <= max_series and p[2] <= max_series]
    return min(ok, key=lambda p: (p[0], max(p[1], p[2]), p)) if ok else None


def read_once(Y: int, n: int, max_series: int = 3) -> bool:
    """One stage using every input exactly once (literals == n) within the series limit."""
    if not one_stage(Y, n) or len(bf.depends_on(Y, n)) != n:
        return False
    return any(p[1] <= max_series and p[2] <= max_series for p in points(bf.negate(Y, n), n, n)
               if p[0] == n)
