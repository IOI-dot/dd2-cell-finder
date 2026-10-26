"""Comparison with the installed HD cells (Option 1 handout, section 4.1, Table 4) and the frame
check against plan_hd.json. Everything is measured from the two GDS files with KLayout."""
from pathlib import Path

import klayout.db as kdb

L = {"boundary": (236, 0), "nwell": (64, 20), "nsdm": (93, 44), "psdm": (94, 20), "hvtp": (78, 44),
     "npc": (95, 20), "met1": (68, 20), "li1": (67, 20), "diff": (65, 20), "poly": (66, 20),
     "li1.pin": (67, 16), "li1.label": (67, 5), "met1.pin": (68, 16), "areaid": (81, 4)}
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
            for s in self.cell.begin_shapes_rec(li).each() if False else self.cell.shapes(li).each():
                if s.is_text():
                    out.append((s.text_string, round(s.text_dpos.x, 3), round(s.text_dpos.y, 3)))
        return out


def frame_check(gds: Gds, frame: dict) -> list:
    """y extents of the frame layers in an installed cell against plan_hd.json."""
    rows = []
    for key, layer in (("boundary", "boundary"), ("nwell", "nwell"), ("nsdm", "nsdm"),
                       ("psdm", "psdm"), ("hvtp", "hvtp"), ("npc_band", "npc")):
        want = tuple(frame[key]["y"])
        got = gds.yext(layer)
        rows.append({"layer": layer, "plan_hd_y": list(want), "measured_y": list(got) if got else None,
                     "match": got is not None and all(abs(a - b) < 1e-6 for a, b in zip(got, want))})
    for rail in ("VGND", "VPWR"):
        want = tuple(frame["rails"][rail]["met1"]["y"])
        got = [b for b in gds.boxes("met1") if abs(b.bbox().center().y - sum(want) / 2) < 0.3]
        got = (round(got[0].bbox().bottom, 3), round(got[0].bbox().top, 3)) if got else None
        rows.append({"layer": f"met1 {rail} rail", "plan_hd_y": list(want), "measured_y": list(got) if got else None,
                     "match": got == want})
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


def pins(gds: Gds) -> list:
    out = []
    for name, x, y in gds.labels("li1.label"):
        band = "npc band" if 0.975 <= y <= 1.345 else ("nmos" if y < 0.975 else "pmos")
        out.append({"pin": name, "layer": "li1 67/20 (label 67/5)", "x": x, "y": y, "band": band})
    for name, x, y in gds.labels("met1.pin") + [(t, x, y) for t, x, y in gds.labels("met1.pin")]:
        pass
    li = gds.ly.find_layer(*L["met1.pin"])
    for name in ("VGND", "VPWR"):
        out.append({"pin": name, "layer": "met1 68/20 rail + li1 strip", "band": "rail"})
    return out


def wiring_layers(gds: Gds) -> dict:
    """li1 inside the cell; met1 only in the two rails."""
    rails = kdb.Region(kdb.Box(-10**6, int(-0.24 / gds.ly.dbu), 10**6, int(0.24 / gds.ly.dbu)))
    rails += kdb.Region(kdb.Box(-10**6, int(2.48 / gds.ly.dbu), 10**6, int(2.96 / gds.ly.dbu)))
    met1_outside = gds.region("met1") - rails
    return {"met1_outside_rails_um2": round(met1_outside.area() * gds.ly.dbu ** 2, 4),
            "li1_present": not gds.region("li1").is_empty(),
            "ok": met1_outside.is_empty() and not gds.region("li1").is_empty()}


def frame_xor(a: Gds, b: Gds) -> dict:
    """XOR of the frame layers when the widths are equal (empty XOR = identical frame)."""
    if a.width() != b.width():
        return {"compared": False, "reason": f"widths differ: {a.width()} vs {b.width()}"}
    out = {"compared": True}
    for layer in FRAME_LAYERS:
        x = a.region(layer) ^ b.region(layer)
        out[layer] = round(x.area() * a.ly.dbu ** 2, 6)
    out["identical"] = all(v == 0 for k, v in out.items() if k in FRAME_LAYERS)
    return out


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
