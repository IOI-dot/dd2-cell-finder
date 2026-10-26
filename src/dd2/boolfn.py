"""Truth tables as ints: input k is bit k of the row index, so A (input 0) is the LSB (Appendix A).

Canonical forms are the minimum table over a transformation group:
  P   input permutations                       (Table 4, "up to input order"; Exists)
  PN  permutations and output inversion        (the handout's classes, section 4 step 3)
  NPN permutations, input and output inversion (counted separately)
"""
import itertools
import re
from functools import lru_cache


def mask(n: int) -> int:
    return (1 << (1 << n)) - 1


def var_tt(k: int, n: int) -> int:
    return sum(1 << i for i in range(1 << n) if (i >> k) & 1)


def to_hex(tt: int, n: int) -> str:
    return f"0x{tt:0{max(1, (1 << n) // 4)}X}"


def _gather(tt: int, rowmap) -> int:
    out = 0
    for i, j in enumerate(rowmap):
        if (tt >> j) & 1:
            out |= 1 << i
    return out


@lru_cache(maxsize=None)
def _perm_rowmap(n: int, perm: tuple) -> tuple:
    rows = []
    for i in range(1 << n):
        j = 0
        for k in range(n):
            if (i >> k) & 1:
                j |= 1 << perm[k]
        rows.append(j)
    return tuple(rows)


def permute(tt: int, n: int, perm) -> int:
    """New input k is old input perm[k]."""
    return _gather(tt, _perm_rowmap(n, tuple(perm)))


def flip_input(tt: int, n: int, k: int) -> int:
    return _gather(tt, tuple(i ^ (1 << k) for i in range(1 << n)))


def negate(tt: int, n: int) -> int:
    return tt ^ mask(n)


def depends_on(tt: int, n: int) -> list:
    """Indices of the inputs the function actually depends on."""
    return [k for k in range(n) if flip_input(tt, n, k) != tt]


def shrink(tt: int, n: int, keep) -> int:
    """Re-express tt over the inputs in keep (the others must be inessential)."""
    keep = list(keep)
    out = 0
    for i in range(1 << len(keep)):
        j = sum(1 << keep[b] for b in range(len(keep)) if (i >> b) & 1)
        if (tt >> j) & 1:
            out |= 1 << i
    return out


@lru_cache(maxsize=None)
def _group(n: int, kind: str) -> tuple:
    """Row maps of the input transformations of a group; output negation is handled separately."""
    perms = list(itertools.permutations(range(n)))
    flips = range(1 << n) if kind == "npn" else (0,)
    maps = set()
    for p in perms:
        base = _perm_rowmap(n, p)
        for m in flips:
            maps.add(tuple(j ^ m for j in base))
    return tuple(sorted(maps))


def _canon_brute(tt: int, n: int, kind: str) -> int:
    cands = [_gather(tt, rm) for rm in _group(n, kind)]
    if kind != "p":
        cands += [c ^ mask(n) for c in cands]
    return min(cands)


@lru_cache(maxsize=None)
def _table(n: int, kind: str) -> list:
    """Canonical form of every n-input table, built orbit by orbit (n <= 4)."""
    table = [-1] * (1 << (1 << n))
    group = _group(n, kind)
    for t in range(len(table)):
        if table[t] >= 0:
            continue
        orbit = {_gather(t, rm) for rm in group}
        if kind != "p":
            orbit |= {o ^ mask(n) for o in orbit}
        m = min(orbit)
        for o in orbit:
            table[o] = m
    return table


def _canon(tt: int, n: int, kind: str) -> int:
    if not 0 <= tt <= mask(n):
        raise ValueError(f"truth table {tt:#x} does not fit {n} inputs")
    return _table(n, kind)[tt] if n <= 4 else _canon_brute(tt, n, kind)


def canon_p(tt: int, n: int) -> int:
    return _canon(tt, n, "p")


def canon_pn(tt: int, n: int) -> int:
    return _canon(tt, n, "pn")


def canon_npn(tt: int, n: int) -> int:
    return _canon(tt, n, "npn")


# ---- expressions: Liberty function syntax (! ' & * | + ^ ( ) 0 1, juxtaposition = AND) ----
_TOKEN = re.compile(r"\s*(?:([A-Za-z_][A-Za-z0-9_\[\]]*)|([!'&*|+^()01]))")


def tokenize(expr: str) -> list:
    toks, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m or m.end() == pos:
            raise ValueError(f"unexpected character {expr[pos:pos + 1]!r} at {pos} in {expr!r}")
        toks.append(m.group(1) or m.group(2))
        pos = m.end()
        while pos < len(expr) and expr[pos].isspace():
            pos += 1
    return toks


def eval_expr(expr: str, names) -> int:
    """Truth table of a Boolean expression over the ordered input names."""
    names = list(names)
    n = len(names)
    full = mask(n)
    env = {nm: var_tt(k, n) for k, nm in enumerate(names)}
    toks = tokenize(expr)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def take(expected=None):
        nonlocal pos
        if pos >= len(toks):
            raise ValueError(f"unexpected end of {expr!r}")
        t = toks[pos]
        if expected and t != expected:
            raise ValueError(f"expected {expected!r}, got {t!r} in {expr!r}")
        pos += 1
        return t

    def starts_unary(t):
        return t is not None and (t in ("!", "(", "0", "1") or t[0].isalpha() or t[0] == "_")

    def unary():
        t = take()
        if t == "!":
            v = full ^ unary()
        elif t == "(":
            v = orx()
            take(")")
        elif t == "0":
            v = 0
        elif t == "1":
            v = full
        elif t in env:
            v = env[t]
        else:
            raise ValueError(f"unknown name {t!r} in {expr!r}; inputs are {names}")
        while peek() == "'":
            take()
            v ^= full
        return v

    def andx():
        v = unary()
        while peek() in ("&", "*") or starts_unary(peek()):
            if peek() in ("&", "*"):
                take()
            v &= unary()
        return v

    def xorx():
        v = andx()
        while peek() == "^":
            take()
            v ^= andx()
        return v

    def orx():
        v = xorx()
        while peek() in ("|", "+"):
            take()
            v |= xorx()
        return v

    v = orx()
    if pos != len(toks):
        raise ValueError(f"unexpected {toks[pos]!r} in {expr!r}")
    return v
