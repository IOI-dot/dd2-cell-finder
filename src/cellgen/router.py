"""A small li1 maze router (Option 1 handout, step 5: "route the nets on li1").

Wires are LI_W wide. A wire's centreline may only visit grid points whose LI_W square keeps
LI_SP from every shape of another net (obstacles are inflated by LI_SP + LI_W/2) and stays inside
the allowed window. Terminals are joined one at a time to the growing tree with an A* search
(Manhattan distance, a penalty per bend), then each straight run becomes one rectangle.
"""
import heapq

from . import rules

G = rules.GRID.value
HALF = rules.LI_W.value / 2


def _q(v: float) -> int:
    return int(round(v / G))


class Router:
    def __init__(self, window, obstacles):
        """window: (x0, y0, x1, y1) for centrelines; obstacles: rects of other nets."""
        self.x0, self.y0, self.x1, self.y1 = (_q(v) for v in window)
        grow = rules.LI_SP.value + HALF
        self.blocked = [(_q(a - grow) + 1, _q(b - grow) + 1, _q(c + grow) - 1, _q(d + grow) - 1)
                        for a, b, c, d in obstacles]

    def free(self, i, j) -> bool:
        if not (self.x0 <= i <= self.x1 and self.y0 <= j <= self.y1):
            return False
        return not any(a <= i <= c and b <= j <= d for a, b, c, d in self.blocked)

    @staticmethod
    def points(rect):
        """Centreline grid points of a wire that lies inside rect."""
        a, b, c, d = rect
        xa, xb = _q(a + HALF), _q(c - HALF)
        ya, yb = _q(b + HALF), _q(d - HALF)
        if xa > xb:
            xa = xb = _q((a + c) / 2)
        if ya > yb:
            ya = yb = _q((b + d) / 2)
        return {(i, j) for i in range(xa, xb + 1) for j in range(ya, yb + 1)}

    def path(self, sources, targets, bend=40, limit=400_000):
        tset = set(targets)
        tx = [p[0] for p in tset]
        ty = [p[1] for p in tset]
        bx = (min(tx), max(tx), min(ty), max(ty))

        def h(i, j):
            dx = 0 if bx[0] <= i <= bx[1] else min(abs(i - bx[0]), abs(i - bx[1]))
            dy = 0 if bx[2] <= j <= bx[3] else min(abs(j - bx[2]), abs(j - bx[3]))
            return dx + dy

        heap, best, prev = [], {}, {}
        for s in sources:
            if self.free(*s):
                for d in range(4):
                    best[(s, d)] = 0
                    heapq.heappush(heap, (h(*s), 0, s, d))
        steps = ((1, 0), (0, 1), (-1, 0), (0, -1))
        n = 0
        while heap:
            f, g, p, d = heapq.heappop(heap)
            if g > best.get((p, d), 1 << 60):
                continue
            if p in tset:
                out = [p]
                key = (p, d)
                while key in prev:
                    key = prev[key]
                    out.append(key[0])
                return out[::-1]
            n += 1
            if n > limit:
                break
            for nd, (di, dj) in enumerate(steps):
                q = (p[0] + di, p[1] + dj)
                if not self.free(*q):
                    continue
                ng = g + 1 + (bend if nd != d else 0)
                if ng < best.get((q, nd), 1 << 60):
                    best[(q, nd)] = ng
                    prev[(q, nd)] = (p, d)
                    heapq.heappush(heap, (ng + h(*q), ng, q, nd))
        return None


def to_rects(path):
    """Straight runs of a centreline path as LI_W-wide rectangles (um)."""
    rects, start = [], 0
    for k in range(1, len(path) + 1):
        end_run = k == len(path) or (k >= 2 and (path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
                                      != (path[k - 1][0] - path[k - 2][0], path[k - 1][1] - path[k - 2][1]))
        if end_run:
            seg = path[start:k]
            xs = [p[0] * G for p in seg]
            ys = [p[1] * G for p in seg]
            rects.append((rules.snap(min(xs) - HALF), rules.snap(min(ys) - HALF),
                          rules.snap(max(xs) + HALF), rules.snap(max(ys) + HALF)))
            start = k - 1
    return rects


def connect(terminals, window, obstacles):
    """Join terminal rect groups (lists of rects) into one net; returns the wire rects or None."""
    r = Router(window, obstacles)
    tree = set().union(*(r.points(x) for x in terminals[0]))
    wires = []
    for term in terminals[1:]:
        tgt = set().union(*(r.points(x) for x in term))
        if tree & tgt:
            tree |= tgt
            continue
        p = r.path(tree, tgt)
        if p is None:
            return None
        rects = to_rects(p)
        wires += rects
        for x in rects:
            tree |= r.points(x)
        tree |= tgt
    return wires
