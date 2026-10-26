"""Independent cut check: simulate the cut's cone one input assignment at a time.

Deliberately shares no code with cuts.py: it walks the AIG from the root down to the leaves for
each of the 2^k leaf assignments and compares every bit with the stored truth table.
"""


def check(g, root: int, leaves, tt: int, fanins: dict | None = None) -> bool:
    fanins = fanins if fanins is not None else g.fanins()
    leaves = tuple(leaves)
    for row in range(1 << len(leaves)):
        values = {leaf: (row >> b) & 1 for b, leaf in enumerate(leaves)}
        values.setdefault(0, 0)                         # constant-false literal

        def value(var):
            if var in values:
                return values[var]
            if var not in fanins:                       # a combinational input outside the cut
                raise LookupError(var)
            a, b = fanins[var]
            values[var] = (value(a >> 1) ^ (a & 1)) & (value(b >> 1) ^ (b & 1))
            return values[var]

        try:
            bit = value(root)
        except LookupError:
            return False
        except RecursionError:
            return False
        if bit != (tt >> row) & 1:
            return False
    return True
