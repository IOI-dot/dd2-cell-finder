"""BSIM4 stress distances (Option 1 handout, section 5): SA and SB of every finger, from the GDS.

SA and SB run from each side of the gate to the end of its diffusion strip, through any neighbouring
gates. Magic's .ext file gives each device's position and terminals, which ties a line of the
extracted netlist to its gate in the layout. Values are written in um, like W and L in these
netlists, so the PDK's scale applies to all of them.
"""
import re
from pathlib import Path

import klayout.db as kdb

from . import eda

UNIT = 0.005          # Magic .ext coordinates


def measure(gds: Path, cell: str) -> dict:
    """(gate left x, "n"/"p") -> (sa, sb) in um, for each gate in the cell."""
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.cell(cell)
    if top is None:
        raise ValueError(f"{cell} not in {gds}")
    region = lambda l, d: kdb.Region(top.begin_shapes_rec(ly.find_layer(l, d))).merged()      # noqa: E731
    diff, poly = region(65, 20), region(66, 20)
    out = {}
    for g in (diff & poly).each():
        b = g.bbox()
        mid = (b.bottom + b.top) // 2
        line = diff & kdb.Region(kdb.Box(-10 ** 7, mid - 1, 10 ** 7, mid + 1))
        piece = next(s.bbox() for s in line.each() if s.bbox().left <= b.left and b.right <= s.bbox().right)
        kind = "n" if b.center().y * ly.dbu < 1.3 else "p"
        out[(round(b.left * ly.dbu, 3), kind)] = (round((b.left - piece.left) * ly.dbu, 3),
                                                  round((piece.right - b.right) * ly.dbu, 3))
    return out


def _devices(ext: Path) -> list:
    """(model, x, y, gate, (terminal, terminal), w) of each device line of a Magic .ext file."""
    out = []
    pat = r'^device msubckt (\S+) (-?\d+) (-?\d+) \S+ \S+ l=\d+ w=(\d+) "[^"]*" "([^"]+)" \d+ \S+ "([^"]+)" \d+ \S+ "([^"]+)"'
    for m in re.finditer(pat, ext.read_text(), re.M):
        model, x, y, w, gate, a, b = m.groups()
        out.append((model, int(x) * UNIT, int(y) * UNIT, gate, tuple(sorted((a, b))), round(int(w) * UNIT, 3)))
    return out


def _net(node: str) -> str:
    return node.split(".")[0].rstrip("#")


def annotate(netlist: Path, out: Path, gds: Path, cell: str, ext: Path | None = None) -> Path:
    """Copy `netlist` with sa= and sb= on every device line. Fingers with one gate and one pair of
    terminals are interchangeable, so they take their distances in x order. SA is measured on the
    side of the device's first terminal, so that the left and right of a device stay apart."""
    netlist = Path(netlist)
    geom = measure(gds, cell)
    pool = {}
    for model, x, y, gate, terms, w in sorted(_devices(Path(ext or netlist.parent / f"{cell}.ext")), key=lambda d: d[1]):
        kind = "n" if "nfet" in model else "p"
        key = min(geom, key=lambda k: (k[1] != kind, abs(k[0] - round(x, 3))))
        pool.setdefault((model, _net(gate), tuple(sorted(_net(t) for t in terms))), []).append(geom[key])
    lines = []
    for line in netlist.read_text().splitlines():
        m = re.match(r"^(X\S*) (\S+) (\S+) (\S+) \S+ (sky130_fd_pr__\S+)", line)
        if m:
            # extresist splits a net into nodes such as Y.t0: the .ext file knows the net
            key = (m.group(5), _net(m.group(3)), tuple(sorted((_net(m.group(2)), _net(m.group(4))))))
            if not pool.get(key):
                raise ValueError(f"no device in the .ext file for: {line}")
            sa, sb = pool[key].pop(0)
            line = f"{line} sa={sa:g} sb={sb:g}"
        lines.append(line)
    Path(out).write_text(eda.count_caps_once("\n".join(lines) + "\n"))
    return Path(out)
