"""Comparison with the installed HD cells (Option 1 handout, section 4.1, Table 4) and the frame
check against plan_hd.json. Everything is measured from the two GDS files with KLayout."""
from pathlib import Path

import klayout.db as kdb

L = {"boundary": (236, 0), "nwell": (64, 20), "nsdm": (93, 44), "psdm": (94, 20), "hvtp": (78, 44),
     "npc": (95, 20), "met1": (68, 20), "li1": (67, 20), "diff": (65, 20), "poly": (66, 20),
     "li1.pin": (67, 16), "li1.label": (67, 5), "met1.pin": (68, 16), "met1.label": (68, 5),
     "areaid": (81, 4), "nwell.label": (64, 5), "nwell.pin": (64, 16), "pwell.label": (64, 59),
     "pwell.pin": (122, 16)}
FRAME_LAYERS = ("boundary", "nwell", "nsdm", "psdm", "hvtp", "areaid")


class Gds:
    def __init__(self, path: Path, cell: str):
        self.ly = kdb.Layout()
        self.ly.read(str(path))
        self.cell = self.ly.cell(cell)
        if self.cell is None:
            raise ValueError(f"{cell} not in {path}")

    def region(self, name):
        li = self.ly.find_layer(*L[name])
        return kdb.Region() if li is None else kdb.Region(self.cell.begin_shapes_rec(li)).merged()

    def boxes(self, name):
        return [b.to_dtype(self.ly.dbu) for b in self.region(name).each()]

    def yext(self, name):
        bs = [p.bbox() for p in self.boxes(name)]
        return (round(min(b.bottom for b in bs), 3), round(max(b.top for b in bs), 3)) if bs else None

    def width(self):
        b = self.region("boundary").bbox().to_dtype(self.ly.dbu)
        return round(b.width(), 3)

    def labels(self, name="li1.label"):
        li = self.ly.find_layer(*L[name])
        out = []
        if li is not None:
            for s in self.cell.shapes(li).each():
                if s.is_text():
                    out.append((s.text_string, round(s.text_dpos.x, 3), round(s.text_dpos.y, 3)))
        return out


def _xext(gds, name):
    bs = [p.bbox() for p in gds.boxes(name)]
    return (round(min(b.left for b in bs), 3), round(max(b.right for b in bs), 3)) if bs else None


def frame_check(gds: Gds, frame: dict) -> list:
    """The frame layers of a cell against plan_hd.json: y extents, x extents (relative to the cell
    width) and the rails (met1 and the li1 strip)."""
    from .layout import _x
    w = gds.width()
    rows = []

    def row(layer, want, got):
        rows.append({"layer": layer, "plan_hd": list(want), "measured": list(got) if got else None,
                     "match": got is not None and all(abs(p - q) < 1e-6 for p, q in zip(got, want))})

    for key, layer in (("boundary", "boundary"), ("nwell", "nwell"), ("nsdm", "nsdm"),
                       ("psdm", "psdm"), ("hvtp", "hvtp"), ("npc_band", "npc"), ("areaid_sc", "areaid")):
        row(layer, tuple(frame[key]["y"]), gds.yext(layer))
        row(f"{layer} x", tuple(_x(v, w) for v in frame[key]["x"]), _xext(gds, layer))
    for rail in ("VGND", "VPWR"):
        for lay in ("met1", "li1"):
            want = tuple(frame["rails"][rail][lay]["y"])
            mid = sum(want) / 2
            got = [b.bbox() for b in gds.boxes(lay) if b.bbox().bottom <= mid <= b.bbox().top]
            got = (round(got[0].bottom, 3), round(got[0].top, 3)) if got else None
            if lay == "li1" and got:            # the strip may merge with contacts reaching it
                got = (max(got[0], want[0]), min(got[1], want[1])) if got[0] <= want[0] and got[1] >= want[1] else got
            row(f"{lay} {rail} rail", want, got)
    return rows


def gate_order(gds: Gds) -> dict:
    """Gates = poly over the NMOS diffusion, left to right; each named by the input label that
    lies on its poly shape (the pad is part of the shape); pitch between gate left edges."""
    ndiff = kdb.Region([d for d in gds.region("diff").each() if d.bbox().top < int(1.0 / gds.ly.dbu)])
    poly = gds.region("poly")
    gates = sorted((g.bbox() for g in (poly & ndiff).each()), key=lambda b: b.left)
    labels = [l for l in gds.labels() if l[0] != "Y"]
    names = []
    for g in gates:
        shape = next((q for q in poly.each() if q.inside(g.center())), None)
        hit = [n for n, x, y in labels if shape is not None and
               shape.inside(kdb.Point(int(round(x / gds.ly.dbu)), int(round(y / gds.ly.dbu))))]
        names.append(hit[0] if hit else "?")
    xs = [round(g.left * gds.ly.dbu, 3) for g in gates]
    nseg = len([d for d in gds.region("diff").each() if d.bbox().top < int(1.0 / gds.ly.dbu)])
    pseg = len([d for d in gds.region("diff").each() if d.bbox().bottom > int(1.3 / gds.ly.dbu)])
    return {"gates": names, "x_um": xs, "pitch_um": [round(b - a, 3) for a, b in zip(xs, xs[1:])],
            "diffusion_breaks": {"n": nseg - 1, "p": pseg - 1}}


def wiring_layers(gds: Gds) -> dict:
    """li1 inside the cell; met1 only in the two rails."""
    rails = kdb.Region(kdb.Box(-10**6, int(-0.24 / gds.ly.dbu), 10**6, int(0.24 / gds.ly.dbu)))
    rails += kdb.Region(kdb.Box(-10**6, int(2.48 / gds.ly.dbu), 10**6, int(2.96 / gds.ly.dbu)))
    met1_outside = gds.region("met1") - rails
    return {"met1_outside_rails_um2": round(met1_outside.area() * gds.ly.dbu ** 2, 4),
            "li1_present": not gds.region("li1").is_empty(),
            "ok": met1_outside.is_empty() and not gds.region("li1").is_empty()}


def frame_xor(a: Gds, b: Gds) -> dict:
    """XOR of the frame layers, the met1 rails and the li1 rail strips, when the widths are equal
    (an empty XOR means an identical frame)."""
    if a.width() != b.width():
        return {"compared": False, "identical": False, "reason": f"widths differ: {a.width()} vs {b.width()}"}
    out = {"compared": True}
    for layer in FRAME_LAYERS + ("met1",):
        out[layer] = round((a.region(layer) ^ b.region(layer)).area() * a.ly.dbu ** 2, 6)
    u = lambda v: int(round(v / a.ly.dbu))                                # noqa: E731
    bands = kdb.Region(kdb.Box(u(-1), u(-0.085), u(10), u(0.085))) + kdb.Region(kdb.Box(u(-1), u(2.635), u(10), u(2.805)))
    out["li1_rails"] = round(((a.region("li1") & bands) ^ (b.region("li1") & bands)).area() * a.ly.dbu ** 2, 6)
    out["identical"] = all(v == 0 for k, v in out.items() if k not in ("compared",))
    return out


def pin_check(gds: Gds, inputs) -> list:
    """Option 1 handout, Table 2: inputs on li1 over the poly contact in the npc band, Y on li1,
    VGND/VPWR on the met1 rails, VPB on the n-well at the top edge, VNB at the bottom edge."""
    errs = []
    dbu = gds.ly.dbu

    def shapes_at(layer, x, y):
        p = kdb.Point(int(round(x / dbu)), int(round(y / dbu)))
        return any(b.inside(p) or b.bbox().contains(p) for b in gds.region(layer).each())

    li = {t: (x, y) for t, x, y in gds.labels("li1.label")}
    for name in list(inputs) + ["Y"]:
        if name not in li:
            errs.append(f"{name}: no li1 label (67/5)")
            continue
        x, y = li[name]
        if not shapes_at("li1", x, y):
            errs.append(f"{name}: label not on li1")
        if not shapes_at("li1.pin", x, y):
            errs.append(f"{name}: no li1 pin shape (67/16) under the label")
        if name != "Y" and not (0.975 <= y <= 1.345):
            errs.append(f"{name}: input pin at y={y} is outside the npc band 0.975-1.345")
        if name != "Y" and not shapes_at("poly", x, y):
            errs.append(f"{name}: input pin is not over its poly contact")
    m1 = {t: (x, y) for t, x, y in gds.labels("met1.label")}
    for name, ry in (("VGND", 0.0), ("VPWR", 2.72)):
        if name not in m1 or abs(m1[name][1] - ry) > 0.24:
            errs.append(f"{name}: no met1 label (68/5) on its rail")
        elif not shapes_at("met1.pin", *m1[name]):
            errs.append(f"{name}: no met1 pin shape (68/16) on the rail")
    for name, label, pin, ey in (("VPB", "nwell.label", "nwell.pin", 2.72), ("VNB", "pwell.label", "pwell.pin", 0.0)):
        hit = [(x, y) for t, x, y in gds.labels(label) if t == name]
        if not hit or abs(hit[0][1] - ey) > 1e-6:
            errs.append(f"{name}: no {label} label at the {'top' if ey else 'bottom'} edge")
        elif not shapes_at(pin, *hit[0]):
            errs.append(f"{name}: no {pin} shape at its label")
    return errs


SVG_STYLE = [("nwell", "none", "#7a5c00", 0.0), ("diff", "#3fa34d", "#3fa34d", 0.55),
             ("poly", "#d1342f", "#d1342f", 0.7), ("li1", "#9b59b6", "#9b59b6", 0.45),
             ("met1", "#4a90d9", "#4a90d9", 0.35), ("boundary", "none", "#222", 0.0)]
SVG_CONTACTS = [((66, 44), "#111"), ((67, 44), "#444")]


def svg(pairs, path: Path, scale=180):
    """Cells side by side in fixed layer colours (implants left out so the devices stay visible).
    pairs: [(title, gds_path, cell)]."""
    parts, x_off = [], 0.4
    for title, gds_path, cell in pairs:
        g = Gds(gds_path, cell)
        X = lambda v: (v + x_off) * scale                                 # noqa: E731
        Y = lambda v: (3.3 - v) * scale                                   # noqa: E731
        parts.append(f'<text x="{X(0)}" y="{Y(3.15)}" font-size="14" font-family="monospace">{title}</text>')

        def poly_svg(p, fill, stroke, op):
            pts = " ".join(f"{X(q.x * g.ly.dbu):.1f},{Y(q.y * g.ly.dbu):.1f}" for q in p.each_point_hull())
            return f'<polygon points="{pts}" fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="1"/>'
        for layer, fill, stroke, op in SVG_STYLE:
            for p in g.region(layer).each():
                parts.append(poly_svg(p, fill, stroke, op))
        for (l, d), colour in SVG_CONTACTS:
            li = g.ly.find_layer(l, d)
            if li is not None:
                for p in kdb.Region(g.cell.begin_shapes_rec(li)).each():
                    parts.append(poly_svg(p, colour, colour, 0.9))
        for name, x, y in g.labels():
            parts.append(f'<text x="{X(x)}" y="{Y(y)}" font-size="12" font-family="monospace" '
                         f'text-anchor="middle">{name}</text>')
        x_off += g.width() + 0.9
    w, h = (x_off + 0.6) * scale, 3.6 * scale
    legend = " · ".join(f'{l}' for l, *_ in SVG_STYLE[1:5])
    body = "\n".join(parts)
    Path(path).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
                          f'viewBox="0 0 {w:.0f} {h:.0f}"><rect width="100%" height="100%" fill="white"/>\n'
                          f'{body}\n<text x="10" y="{h - 10:.0f}" font-size="11" font-family="monospace">'
                          f'diff green, poly red, li1 purple, met1 blue, contacts black; implants not drawn</text></svg>\n')
    return Path(path)
