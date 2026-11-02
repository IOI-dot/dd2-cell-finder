"""A small li1 maze router (Option 1 handout, step 5: "route the nets on li1").

Wires are LI_W wide. A wire's centreline may only visit grid points whose LI_W square keeps
LI_SP from every shape of another net (obstacles are inflated by LI_SP + LI_W/2) and stays inside
the allowed window. The search runs on the Hanan grid of the obstacle and terminal edges, which
holds a shortest rectilinear path, and costs length plus a penalty per bend. Terminals join the
growing tree nearest first, and each straight run becomes one rectangle.
"""
import heapq

from . import rules

G = rules.GRID.value
HALF = rules.LI_W.value / 2
BEND = 40


def _q(v: float) -> int:
    return int(round(v / G))


class Router:
    def __init__(self, window, obstacles, half=HALF, space=rules.LI_SP.value):
        """window: (x0, y0, x1, y1) for centrelines; obstacles: rects of other nets."""
        self.x0, self.y0, self.x1, self.y1 = (_q(v) for v in window)
        self.nx, self.ny = max(self.x1 - self.x0 + 1, 0), max(self.y1 - self.y0 + 1, 0)
        grow = space + half
        self.by_x = [bytearray(self.ny) for _ in range(self.nx)]    # blocked, column by column
        self.by_y = [bytearray(self.nx) for _ in range(self.ny)]    # and row by row
        self.tracks = (set(), set())
        for a, b, c, d in obstacles:
            ia, ib = _q(a - grow) + 1, _q(c + grow) - 1
            ja, jb = _q(b - grow) + 1, _q(d + grow) - 1
            self.tracks[0].update((ia - 1, ib + 1))
            self.tracks[1].update((ja - 1, jb + 1))
            i0, i1, j0, j1 = max(ia, self.x0), min(ib, self.x1), max(ja, self.y0), min(jb, self.y1)
            if i0 > i1 or j0 > j1:
                continue
            fill_y, fill_x = b"\x01" * (j1 - j0 + 1), b"\x01" * (i1 - i0 + 1)
            for i in range(i0, i1 + 1):
                self.by_x[i - self.x0][j0 - self.y0:j1 - self.y0 + 1] = fill_y
            for j in range(j0, j1 + 1):
                self.by_y[j - self.y0][i0 - self.x0:i1 - self.x0 + 1] = fill_x

    def free(self, i, j) -> bool:
        if not (self.x0 <= i <= self.x1 and self.y0 <= j <= self.y1):
            return False
        return not self.by_x[i - self.x0][j - self.y0]

    def _clear_h(self, j, a, b) -> bool:
        return self.by_y[j - self.y0].find(1, a - self.x0, b - self.x0 + 1) < 0

    def _clear_v(self, i, a, b) -> bool:
        return self.by_x[i - self.x0].find(1, a - self.y0, b - self.y0 + 1) < 0

    @staticmethod
    def span(rect):
        """Centreline grid range of a wire that lies inside rect."""
        a, b, c, d = rect
        xa, xb = _q(a + HALF), _q(c - HALF)
        ya, yb = _q(b + HALF), _q(d - HALF)
        if xa > xb:
            xa = xb = _q((a + c) / 2)
        if ya > yb:
            ya = yb = _q((b + d) / 2)
        return xa, ya, xb, yb

    def path(self, sources, targets):
        """Shortest centreline path from any source rect to any target rect (grid points), or None."""
        src, dst = [self.span(r) for r in sources], [self.span(r) for r in targets]
        xs = {self.x0, self.x1} | {v for t in self.tracks[0] for v in (t,)}
        ys = {self.y0, self.y1} | {v for t in self.tracks[1] for v in (t,)}
        for a, b, c, d in src + dst:
            xs.update((a, c, (a + c) // 2))
            ys.update((b, d, (b + d) // 2))
        xs = sorted(v for v in xs if self.x0 <= v <= self.x1)
        ys = sorted(v for v in ys if self.y0 <= v <= self.y1)
        inside = lambda spans, i, j: any(a <= i <= c and b <= j <= d for a, b, c, d in spans)    # noqa: E731
        heap, best, prev = [], {}, {}
        for ix, i in enumerate(xs):
            for iy, j in enumerate(ys):
                if inside(src, i, j) and self.free(i, j):
                    for d in range(4):
                        best[(ix, iy, d)] = 0
                        heapq.heappush(heap, (0, ix, iy, d))
        while heap:
            g, ix, iy, d = heapq.heappop(heap)
            if g > best.get((ix, iy, d), 1 << 60):
                continue
            if inside(dst, xs[ix], ys[iy]):
                out = []
                key = (ix, iy, d)
                while True:
                    out.append((xs[key[0]], ys[key[1]]))
                    if key not in prev:
                        return out[::-1]
                    key = prev[key]
            for nd, (dx, dy) in enumerate(((1, 0), (0, 1), (-1, 0), (0, -1))):
                nx, ny = ix + dx, iy + dy
                if not (0 <= nx < len(xs) and 0 <= ny < len(ys)):
                    continue
                if dy == 0:
                    a, b = sorted((xs[ix], xs[nx]))
                    if not self._clear_h(ys[iy], a, b):
                        continue
                else:
                    a, b = sorted((ys[iy], ys[ny]))
                    if not self._clear_v(xs[ix], a, b):
                        continue
                ng = g + (b - a) + (BEND if nd != d else 0)
                if ng < best.get((nx, ny, nd), 1 << 60):
                    best[(nx, ny, nd)] = ng
                    prev[(nx, ny, nd)] = (ix, iy, d)
                    heapq.heappush(heap, (ng, nx, ny, nd))
        return None


def to_rects(path, half=HALF):
    """Straight runs of a centreline path as wire rectangles (um), LI_W wide by default."""
    corners = [path[0]]
    for a, b, c in zip(path, path[1:], path[2:]):
        if (a[0] == b[0]) != (b[0] == c[0]):
            corners.append(b)
    corners.append(path[-1])
    return [(rules.snap(min(p[0], q[0]) * G - half), rules.snap(min(p[1], q[1]) * G - half),
             rules.snap(max(p[0], q[0]) * G + half), rules.snap(max(p[1], q[1]) * G + half))
            for p, q in zip(corners, corners[1:])]


def _touch(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def connect(terminals, window, obstacles):
    """Join terminal rect groups (lists of rects) into one net, nearest terminal first; returns the
    wire rects or None."""
    wires, parts = connect_parts(terminals, window, obstacles)
    return wires if len(parts) == 1 else None


def connect_parts(terminals, window, obstacles) -> tuple:
    """As far as li1 goes: the wires, and the connected pieces left (one piece: the net is done)."""
    r = Router(window, obstacles)
    todo = [list(t) for t in terminals]
    wires, parts = [], []
    while todo:
        tree = todo.pop(0)
        while todo:
            hit = [t for t in todo if any(_touch(a, b) for a in t for b in tree)]
            if hit:
                for t in hit:
                    tree += t
                    todo.remove(t)
                continue
            p = r.path(tree, [x for t in todo for x in t])
            if p is None:
                break
            rects = to_rects(p) if len(p) > 1 else []
            wires += rects
            tree += rects
        parts.append(tree)
    return wires, parts


def jump(parts, window, obstacles, half, space) -> list | None:
    """Join li1 pieces on the next layer up: [(wire rects, via centres in um)], or None."""
    tree, todo, out = list(parts[0]), [list(p) for p in parts[1:]], []
    used = list(obstacles)
    while todo:
        p = None
        for t in sorted(todo, key=len):
            p = Router(window, used, half, space).path(tree, t)
            if p:
                break
        if p is None:
            return None
        rects = to_rects(p, half) if len(p) > 1 else []
        vias = [(p[0][0] * G, p[0][1] * G), (p[-1][0] * G, p[-1][1] * G)]
        out.append((rects, vias))
        used += rects
        tree += t
        todo.remove(t)
    return out
