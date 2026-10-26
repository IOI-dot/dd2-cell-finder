"""Layer check (Option 1 handout, section 3.2): psdm and hvtp over every PMOS diffusion, nsdm over
every NMOS diffusion, and npc over every poly contact. Magic does not check these as drawn.

PMOS diffusion = diff inside the n-well; NMOS diffusion = diff outside it; a poly contact =
licon on poly and not on diff. Uses KLayout's region boolean operations on the GDS itself.
"""
from pathlib import Path

import klayout.db as kdb

L = {"diff": (65, 20), "poly": (66, 20), "licon": (66, 44), "nwell": (64, 20), "nsdm": (93, 44),
     "psdm": (94, 20), "hvtp": (78, 44), "npc": (95, 20)}


def check(gds: Path, cell: str) -> list:
    ly = kdb.Layout()
    ly.read(str(gds))
    top = ly.cell(cell)
    if top is None:
        return [f"cell {cell} not in {gds}"]

    def region(name):
        li = ly.find_layer(*L[name])
        r = kdb.Region() if li is None else kdb.Region(top.begin_shapes_rec(li))
        return r.merged()

    diff, nwell, poly, licon = region("diff"), region("nwell"), region("poly"), region("licon")
    pdiff, ndiff = diff & nwell, diff - nwell
    poly_contacts = (licon & poly) - diff
    errs = []
    for what, shapes, cover in (("psdm", pdiff, "psdm"), ("hvtp", pdiff, "hvtp"),
                                ("nsdm", ndiff, "nsdm"), ("npc", poly_contacts, "npc")):
        left = shapes - region(cover)
        if not left.is_empty():
            boxes = [b.to_dtype(ly.dbu) for b in left.each()]
            errs.append(f"{what} does not cover {len(boxes)} shape(s), e.g. {boxes[0]}")
    if pdiff.is_empty() and ndiff.is_empty():
        errs.append("no diffusion found")
    return errs
