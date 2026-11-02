"""Abutment fixtures (Option 1 handout, step 6): the cell in rows of real HD cells.

Each fixture is a GDS assembled with KLayout instance transforms, then checked by Magic's full
DRC. Rows always contain a tap cell (a lone logic cell fails nwell.4 by design).
  side      tap | X | inv_1 | fill_1
  mirror    tap | X mirrored left-right | inv_1 | fill_1
  self      tap | X | X mirrored | X | tap     (the cell next to itself both ways; two taps, as a
            real row has, so that three wide cells stay within the latch-up distance of a tap)
  flip      the side row, a row flipped upside down above it (sharing VPWR) and one below it
            (sharing VGND)
"""
from pathlib import Path

import klayout.db as kdb

HD = "sky130_fd_sc_hd__"
ROW_H = 2.72


def build(hd_gds: Path, cell_gds: Path, cell: str, width: float, out: Path) -> dict:
    ly = kdb.Layout()
    ly.read(str(hd_gds))
    ly.read(str(cell_gds))
    dbu = ly.dbu
    u = lambda v: int(round(v / dbu))                                      # noqa: E731
    idx = {n: ly.cell(n).cell_index() for n in (cell, HD + "tapvpwrvgnd_1", HD + "inv_1", HD + "fill_1")}
    w = {cell: width, HD + "tapvpwrvgnd_1": 0.46, HD + "inv_1": 1.38, HD + "fill_1": 0.46}

    def row(top, names, y=0.0, flip=False, mirror=()):
        x = 0.0
        for i, n in enumerate(names):
            if i in mirror:                       # mirror left-right in place: x -> x0 + w - x
                t = kdb.Trans(kdb.Trans.M90, u(x + w[n]), u(y))
            elif flip:                            # upside down: y -> y0 + ROW_H - (y - y0)
                t = kdb.Trans(kdb.Trans.M0, u(x), u(y + ROW_H))
            else:
                t = kdb.Trans(u(x), u(y))
            top.insert(kdb.CellInstArray(idx[n], t))
            x += w[n]

    base = [HD + "tapvpwrvgnd_1", cell, HD + "inv_1", HD + "fill_1"]
    specs = {
        "side": [(base, 0.0, False, ())],
        "mirror": [(base, 0.0, False, (1,))],
        "self": [([HD + "tapvpwrvgnd_1", cell, cell, cell, HD + "tapvpwrvgnd_1"], 0.0, False, (2,))],
        "flip": [(base, 0.0, False, ()), (base, ROW_H, True, ()), (base, -ROW_H, True, ())],
    }
    files = {}
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in specs.items():
        top = ly.create_cell(f"abut_{name}_{cell}")
        for names, y, flip, mirror in rows:
            row(top, names, y, flip, mirror)
        opts = kdb.SaveLayoutOptions()
        opts.select_cell(top.cell_index())
        path = out / f"abut_{name}.gds"
        ly.write(str(path), opts)
        files[name] = (path, top.name)
    return files
