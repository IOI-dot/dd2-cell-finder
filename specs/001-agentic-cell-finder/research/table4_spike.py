# Research spike (not project code): can Table 4 of the Option 2 handout be reproduced?
import re, sys, itertools
from collections import Counter

LIB = sys.argv[1]
N = 4
FULL = (1 << (1 << N)) - 1

def var_tt(k, n):  # truth table of input k over n inputs, input 0 = LSB of index
    return sum(1 << i for i in range(1 << n) if (i >> k) & 1)

# ---- Liberty: single-output combinational cells and their output function ----
def cells(text):
    for m in re.finditer(r'\n\s*cell\s*\(\s*"?([\w]+)"?\s*\)\s*\{', text):
        start = m.end(); depth = 1; i = start
        while depth:
            c = text[i]; depth += (c == '{') - (c == '}'); i += 1
        yield m.group(1), text[start:i]

def pins(body):
    for m in re.finditer(r'\n\s*pin\s*\(\s*"?([\w]+)"?\s*\)\s*\{', body):
        start = m.end(); depth = 1; i = start
        while depth:
            c = body[i]; depth += (c == '{') - (c == '}'); i += 1
        yield m.group(1), body[start:i]

def tokenize(s):
    return re.findall(r"[A-Za-z_][\w]*|[!&|^()'*+01]", s)

def eval_fn(expr, names):  # returns tt over len(names) inputs
    n = len(names); full = (1 << (1 << n)) - 1
    env = {nm: var_tt(k, n) for k, nm in enumerate(names)}
    toks = tokenize(expr); pos = 0
    def peek(): return toks[pos] if pos < len(toks) else None
    def take():
        nonlocal pos; t = toks[pos]; pos += 1; return t
    def prim():
        t = take()
        if t == '!': v = full ^ prim()
        elif t == '(': v = orx(); assert take() == ')'
        elif t == '0': v = 0
        elif t == '1': v = full
        else: v = env[t]
        while peek() == "'": take(); v ^= full
        return v
    def andx():
        v = prim()
        while peek() in ('&', '*') or (peek() not in (None, ')', '|', '+', '^')):
            if peek() in ('&', '*'): take()
            v &= prim()
        return v
    def xorx():
        v = andx()
        while peek() == '^': take(); v ^= andx()
        return v
    def orx():
        v = xorx()
        while peek() in ('|', '+'): take(); v |= xorx()
        return v
    v = orx(); assert pos == len(toks), expr
    return v

text = open(LIB).read()
hd = []
for name, body in cells(text):
    if re.search(r'\b(ff|latch|statetable)\s*\(', body): continue
    ps = list(pins(body))
    ins = [p for p, b in ps if re.search(r'direction\s*:\s*"?input', b)]
    outs = [(p, b) for p, b in ps if re.search(r'direction\s*:\s*"?output', b)]
    if len(outs) != 1: continue
    fm = re.search(r'\n\s*function\s*:\s*"([^"]*)"', outs[0][1])
    if not fm or not ins: continue
    if re.search(r'three_state', outs[0][1]): continue
    hd.append((name, ins, eval_fn(fm.group(1), ins)))
print("single-output combinational HD cells:", len(hd))

# ---- permutation machinery ----
def permute(tt, n, perm):  # new input k = old input perm[k]
    out = 0
    for i in range(1 << n):
        j = 0
        for k in range(n):
            if (i >> k) & 1: j |= 1 << perm[k]
        if (tt >> j) & 1: out |= 1 << i
    return out

PERMS4 = list(itertools.permutations(range(4)))
def pclass(tt): return min(permute(tt, 4, p) for p in PERMS4)

def depends_all(tt, n):
    for k in range(n):
        m = var_tt(k, n)
        if ((tt & m) >> (1 << k)) == (tt & ~m & ((1 << (1 << n)) - 1)): return False
    return True

# HD cells as 4-input functions (only those with exactly 4 essential inputs can be "Exists")
exists4 = set()
for name, ins, tt in hd:
    if len(ins) == 4 and depends_all(tt, 4): exists4.add(pclass(tt))

# Contained: each HD input -> one of the 4 candidate inputs or 0/1
contained = set()
for name, ins, tt in hd:
    n = len(ins)
    srcs = [var_tt(k, 4) for k in range(4)] + [0, FULL]
    for asg in itertools.product(range(6), repeat=n):
        cols = [srcs[a] for a in asg]
        out = 0
        for i in range(16):
            j = 0
            for k in range(n):
                if (cols[k] >> i) & 1: j |= 1 << k
            if (tt >> j) & 1: out |= 1 << i
        contained.add(out)

def classify(tt):
    if pclass(tt) in exists4: return "Exists"
    if pclass(tt ^ FULL) in exists4: return "Exists with an inverter"
    for k in range(4):
        m = var_tt(k, 4)
        flipped = ((tt & m) >> (1 << k)) | ((tt & ~m & FULL) << (1 << k))
        if pclass(flipped) in exists4: return "Exists with an inverter"
    if tt in contained: return "Contained"
    return "New"

reps = sorted({pclass(t) for t in range(1 << 16) if depends_all(t, 4)})
print("P-classes depending on all 4 inputs:", len(reps))
cls = {r: classify(r) for r in reps}
print(Counter(cls.values()))

# HD self-test: every HD cell, as a candidate of its own arity, is Exists (perm of itself)
def pclass_n(tt, n): return min(permute(tt, n, p) for p in itertools.permutations(range(n)))
hd_set = {}
for name, ins, tt in hd: hd_set.setdefault(len(ins), set()).add(pclass_n(tt, len(ins)))
bad = [nm for nm, ins, tt in hd if pclass_n(tt, len(ins)) not in hd_set[len(ins)]]
print("HD self-test failures:", len(bad))

# ---- one-stage costing: monotone F, Y = !F; SP formulas with repeated literals ----
# state: tt -> set of (literals, n_series, p_series); AND: n adds, p max; OR: n max, p adds
from functools import lru_cache
MAXL = 8
by_size = {1: {(var_tt(k, 4), 1, 1) for k in range(4)}}
for L in range(2, MAXL + 1):
    s = set()
    for a in range(1, L // 2 + 1):
        for (ta, na, pa) in by_size[a]:
            for (tb, nb, pb) in by_size[L - a]:
                s.add((ta & tb, na + nb, max(pa, pb)))
                s.add((ta | tb, max(na, nb), pa + pb))
    by_size[L] = s
def one_stage(tt):  # Y = tt negative unate <=> F = !tt positive unate; SP form always exists
    F = tt ^ FULL
    for k in range(4):
        m = var_tt(k, 4)
        lo = F & ~m & FULL; hi = (F & m) >> (1 << k)
        if lo & ~hi & FULL: return False
    return True
def small(tt, maxser=3, maxtr=12):
    F = tt ^ FULL
    return any(t == F and n <= maxser and p <= maxser and 2 * L <= maxtr
               for L in range(1, maxtr // 2 + 1) for (t, n, p) in by_size[L])
def read_once_ok(tt):
    F = tt ^ FULL
    return any(t == F and n <= 3 and p <= 3 for (t, n, p) in by_size[4])

new = [r for r in reps if cls[r] == "New"]
print("New one-stage:", sum(one_stage(r) for r in new))
print("New one-stage <=3 series <=12T:", sum(one_stage(r) and small(r) for r in new))
ro = [r for r in reps if read_once_ok(r)]
print("read-once <=3 series:", len(ro), Counter(cls[r] for r in ro))

print("--- the 9 new one-stage classes: (literals, n_series, p_series) Pareto points ---")
for r in new:
    if not one_stage(r): continue
    F = r ^ FULL
    pts = sorted({(L, n, p) for L in by_size for (t, n, p) in by_size[L] if t == F})
    minL = pts[0][0]
    pareto = [x for x in pts if not any(y != x and y[0] <= x[0] and y[1] <= x[1] and y[2] <= x[2] for y in pts)]
    print(f"Y=0x{r:04X}  minLits={minL}  minLit-forms={[x for x in pareto if x[0]==minL]}  pareto={pareto}")
