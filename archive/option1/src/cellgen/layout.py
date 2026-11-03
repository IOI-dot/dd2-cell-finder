"""Single-stage cell layout inside the fixed HD frame (Option 1 handout, sections 2 and 3.2).

Geometry is a list of rectangles per GDS layer, in um, built from:
  * the frame of given/plan_hd.json (boundary, areaid.sc, rails, n-well, implants, npc band), copied
    unchanged and stretched only in x to a whole number of sites;
  * the paired Euler ordering: one poly stripe per gate, contact columns where a net must leave
    the diffusion, diffusion breaks where the ordering needs them;
  * li1 only for wiring; met1 only in the rails. Nets that join several contacts are routed by
    cellgen.router.
Every spacing comes from cellgen.rules.
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from dd2 import paths

from . import router
from .rules import (DIFF_SP, LI_ENC2, LI_SP, LI_W, LICON, LICON_DIFF_ENC, LICON_DIFF_ENC2,
                    LICON_GATE_SP, LICON_POLY_ENC, LICON_POLY_ENC2, LICON_SP, NPC_ENC, POLY_SP,
                    POLY_W, SITE, snap)

LAYERS = {
    "diff": (65, 20), "poly": (66, 20), "licon": (66, 44), "li1": (67, 20), "mcon": (67, 44),
    "met1": (68, 20), "nwell": (64, 20), "nsdm": (93, 44), "psdm": (94, 20), "hvtp": (78, 44),
    "npc": (95, 20), "areaid": (81, 4), "boundary": (236, 0),
    "li1.label": (67, 5), "li1.pin": (67, 16), "met1.label": (68, 5), "met1.pin": (68, 16),
    "nwell.label": (64, 5), "nwell.pin": (64, 16), "pwell.label": (64, 59), "pwell.pin": (122, 16),
}
RAILS = ("VGND", "VPWR")


@dataclass
class Rect:
    layer: str
    box: tuple          # (x0, y0, x1, y1) um
    net: str | None = None


@dataclass
class Cell:
    name: str
    width: float
    rects: list = field(default_factory=list)
    labels: list = field(default_factory=list)     # (layer, text, x, y)
    report: dict = field(default_factory=dict)

    def add(self, layer, box, net=None):
        self.rects.append(Rect(layer, tuple(snap(v) for v in box), net))


def load_frame(path: Path | None = None) -> dict:
    return json.loads(Path(path or paths.given() / "plan_hd.json").read_text())


def _x(v, width):
    """Frame x values: a number, "width", or "width + c" / "width - c" (plan_hd.json's forms)."""
    if isinstance(v, (int, float)):
        return float(v)
    s = v.replace(" ", "")
    if s == "width":
        return width
    if s.startswith("width+") or s.startswith("width-"):
        return width + float(s[5:])
    raise ValueError(f"unsupported frame coordinate {v!r} in plan_hd.json")


def _licon_stack(y0: float, w: float):
    """Contact y ranges in a diffusion of height w starting at y0 (HD: 0.08 below, 0.06 above)."""
    pitch = LICON.value + LICON_SP.value
    n = max(1, math.floor((w - 2 * LICON_DIFF_ENC2.value + LICON_SP.value) / pitch))
    stack = n * LICON.value + (n - 1) * LICON_SP.value
    bottom = snap(y0 + w - stack - LICON_DIFF_ENC2.value)
    return [(snap(bottom + i * pitch), snap(bottom + i * pitch + LICON.value)) for i in range(n)]


def _columns(order):
    """Per row, per column j (0..k): list of nets ([net] or [left, right] at a break)."""
    k = len(order.gates)
    cols = {}
    for row, segs in order.rows.items():
        c = [[] for _ in range(k + 1)]
        j = 0
        for s, seg in enumerate(segs):
            if s:
                j -= 0       # a new segment starts in the same column as the break
            for i, net in enumerate(seg):
                c[j + i].append(net)
            j += len(seg) - 1
        cols[row] = [list(dict.fromkeys(x)) if len(set(x)) == 1 else x for x in c]
    return cols


def build(net, order, name: str, wn: float = 0.65, wp: float = 1.0, frame: dict | None = None,
          pad_gap: tuple = (0.03, 0.03)) -> Cell:
    frame = (frame or load_frame())["frame"]
    # one finger per row fits the HD bands: NMOS 0.235-0.885, PMOS 1.485-2.485 (plan_hd.json reference)
    if wn > 0.65 + 1e-9 or wp > 1.0 + 1e-9 or min(wn, wp) < 0.15:
        raise ValueError(f"W = {wn}/{wp} um does not fit one finger in the HD frame: fold it "
                         "(stack sizing) or use 0.15 <= W <= 0.65/1.0")
    k = len(order.gates)
    cols = _columns(order)
    occ = {}
    for row in cols.values():
        for c in row:
            for n_ in c:
                occ[n_] = occ.get(n_, 0) + 1
    needs = lambda n_: n_ in RAILS or n_ == "Y" or occ.get(n_, 0) > 1   # noqa: E731
    contact = {row: [[needs(n_) for n_ in c] for c in cols[row]] for row in cols}

    # ---- gate positions (relative; shifted to centre the cell later) ----
    gap_contact = 2 * LICON_GATE_SP.value + LICON.value                      # 0.27
    gap_break = 2 * (LICON_GATE_SP.value + LICON.value + LICON_DIFF_ENC.value) + DIFF_SP.value
    side = ["left"] if k == 1 else ["left"] + ["center"] * (k - 2) + ["right"]
    lic_off = {"left": -pad_gap[0] - LICON.value, "right": POLY_W.value + pad_gap[1],
               "center": POLY_W.value / 2 - LICON.value / 2}
    # poly pad: 0.05 beside the contact (licon.8), 0.08 above and below it (licon.8a);
    # the li1 pin overhangs the contact by 0.08 at both sides (li.5)
    # the pad always reaches its own gate stripe (else the input would be cut off)
    pad_off = {s: (min(0.0, o - LICON_POLY_ENC.value), max(POLY_W.value, o + LICON.value + LICON_POLY_ENC.value))
               for s, o in lic_off.items()}
    pin_off = {s: (o - LI_ENC2.value, o + LICON.value + LI_ENC2.value) for s, o in lic_off.items()}
    gaps = []
    for j in range(1, k):
        brk = any(len(cols[r][j]) > 1 for r in cols)
        con = any(any(contact[r][j]) for r in cols)
        base = gap_break if brk else (gap_contact if con else POLY_SP.value)
        right_ext = max(POLY_W.value, pad_off[side[j - 1]][1]) - POLY_W.value
        left_ext = -min(0.0, pad_off[side[j]][0])
        gaps.append(max(base, POLY_SP.value + right_ext + left_ext))
    gx = [0.0]
    for g in gaps:
        gx.append(gx[-1] + POLY_W.value + g)

    # ---- contact x ranges per column (relative) ----
    def contact_x(j, part):
        if j == 0:
            return (gx[0] - LICON_GATE_SP.value - LICON.value, gx[0] - LICON_GATE_SP.value)
        if j == k:
            a = gx[k - 1] + POLY_W.value + LICON_GATE_SP.value
            return (a, a + LICON.value)
        lo, hi = gx[j - 1] + POLY_W.value, gx[j]
        if part == "left":
            return (lo + LICON_GATE_SP.value, lo + LICON_GATE_SP.value + LICON.value)
        if part == "right":
            return (hi - LICON_GATE_SP.value - LICON.value, hi - LICON_GATE_SP.value)
        mid = (lo + hi) / 2
        return (mid - LICON.value / 2, mid + LICON.value / 2)

    # ---- extents and width ----
    xs = [contact_x(0, "")[0] - LICON_DIFF_ENC.value, contact_x(k, "")[1] + LICON_DIFF_ENC.value]
    pads = [(gx[i] + pad_off[side[i]][0], gx[i] + pad_off[side[i]][1]) for i in range(k)]
    pins = [(gx[i] + pin_off[side[i]][0], gx[i] + pin_off[side[i]][1]) for i in range(k)]
    lo = min(xs[0] - DIFF_SP.value / 2, min(p[0] for p in pads) - POLY_SP.value / 2,
             min(p[0] for p in pins) - LI_SP.value / 2)
    hi = max(xs[1] + DIFF_SP.value / 2, max(p[1] for p in pads) + POLY_SP.value / 2,
             max(p[1] for p in pins) + LI_SP.value / 2)
    sites = math.ceil(round((hi - lo) / SITE.value, 6))
    width = snap(sites * SITE.value)
    shift = snap(-lo + (width - (hi - lo)) / 2)
    X = lambda v: snap(v + shift)                                            # noqa: E731
    cell = Cell(name, width)

    # ---- frame (unchanged; stretched to the cell width in x) ----
    for key, layer in (("boundary", "boundary"), ("areaid_sc", "areaid"), ("nwell", "nwell"),
                       ("nsdm", "nsdm"), ("psdm", "psdm"), ("hvtp", "hvtp"), ("npc_band", "npc")):
        f = frame[key]
        cell.add(layer, (_x(f["x"][0], width), f["y"][0], _x(f["x"][1], width), f["y"][1]))
    for rail, f in frame["rails"].items():
        cell.add("met1", (0, f["met1"]["y"][0], width, f["met1"]["y"][1]), rail)
        cell.add("li1", (0, f["li1"]["y"][0], width, f["li1"]["y"][1]), rail)
        s = f["mcon"]["size"]
        for i in range(sites):
            cx = 0.23 + 0.46 * i
            cell.add("mcon", (cx - s / 2, f["mcon"]["y"][0], cx + s / 2, f["mcon"]["y"][1]), rail)

    rows = {"n": (0.235, wn), "p": (1.485, wp)}
    band = frame["npc_band"]["y"]
    lic_y = (snap(band[0] + NPC_ENC.value), snap(band[0] + NPC_ENC.value + LICON.value))

    # ---- poly: gate stripes and input pads ----
    for i, g in enumerate(order.gates):
        x0 = X(gx[i])
        cell.add("poly", (x0, 0.105, x0 + POLY_W.value, 2.615), g)
        lx = x0 + lic_off[side[i]]
        cell.add("licon", (lx, lic_y[0], lx + LICON.value, lic_y[1]), g)
        cell.add("poly", (x0 + pad_off[side[i]][0], lic_y[0] - LICON_POLY_ENC2.value,
                          x0 + pad_off[side[i]][1], lic_y[1] + LICON_POLY_ENC2.value), g)
        cell.add("li1", (lx - LI_ENC2.value, lic_y[0], lx + LICON.value + LI_ENC2.value, lic_y[1]), g)

    # ---- diffusion, contacts and li1 pads per row ----
    terminals = {}
    li_lo, li_hi = 0.255, 2.465            # non-rail li1 keeps LI_SP from the rail strips
    for row, (y0, w) in rows.items():
        ys = _licon_stack(y0, w)
        # diffusion segments
        seg_start = contact_x(0, "")[0] - LICON_DIFF_ENC.value
        for j in range(1, k + 1):
            if j == k or len(cols[row][j]) > 1:
                end = (contact_x(j, "left" if j < k else "")[1] + LICON_DIFF_ENC.value)
                cell.add("diff", (X(seg_start), y0, X(end), y0 + w))
                if j < k:
                    seg_start = contact_x(j, "right")[0] - LICON_DIFF_ENC.value
        # contacts
        for j in range(k + 1):
            parts = cols[row][j]
            for p_i, n_ in enumerate(parts):
                if not contact[row][j][p_i]:
                    continue
                part = "" if len(parts) == 1 else ("left" if p_i == 0 else "right")
                cx0, cx1 = (X(v) for v in contact_x(j, part))
                for a, b in ys:
                    cell.add("licon", (cx0, a, cx1, b), n_)
                if n_ in RAILS:
                    ybox = (-0.085, ys[-1][1] + LI_ENC2.value) if n_ == "VGND" else (ys[0][0] - LI_ENC2.value, 2.805)
                    pad = (cx0, ybox[0], cx1, ybox[1])
                else:
                    # the rail strips stop a vertical 0.08 overhang, so overhang 0.08 left and right (li.5)
                    ya = max(li_lo, ys[0][0] - LI_ENC2.value)
                    yb = min(li_hi, ys[-1][1] + LI_ENC2.value)
                    pad = (cx0 - LI_ENC2.value, ya, cx1 + LI_ENC2.value, yb)
                cell.add("li1", pad, n_)
                terminals.setdefault(n_, []).append([pad])

    # ---- route nets that join several contacts ----
    window = (0.17, 0.34, width - 0.17, 2.38)
    routed = {}
    for n_ in sorted((n_ for n_ in terminals if n_ not in RAILS), key=lambda n_: (-len(terminals[n_]), n_)):
        if len(terminals[n_]) < 2:
            continue
        others = [r.box for r in cell.rects if r.layer == "li1" and r.net != n_]
        wires = router.connect(terminals[n_], window, others)
        if wires is None:
            cell.report.setdefault("route_failures", []).append(n_)
            continue
        for wbox in wires:
            cell.add("li1", wbox, n_)
        routed[n_] = len(wires)

    # ---- pins and labels (HD conventions, plan_hd.json "pins") ----
    for r in cell.rects:
        if r.layer == "li1" and r.net in order.gates and (r.box[3] - r.box[1]) <= LICON.value + 1e-9:
            cx, cy = (r.box[0] + r.box[2]) / 2, (r.box[1] + r.box[3]) / 2
            _pin(cell, "li1", r.net, cx, cy)
    ypads = [t[0] for t in terminals.get("Y", [])]
    for pad in ypads[:2]:
        _pin(cell, "li1", "Y", (pad[0] + pad[2]) / 2, (pad[1] + pad[3]) / 2)
    for rail, y in (("VGND", 0.0), ("VPWR", 2.72)):
        cell.labels.append(("met1.label", rail, 0.23, y))
        cell.add("met1.pin", (0.145, y - 0.085, 0.315, y + 0.085), rail)
    cell.labels.append(("nwell.label", "VPB", 0.23, 2.72))
    cell.add("nwell.pin", (0.145, 2.635, 0.315, 2.805), "VPB")
    cell.labels.append(("pwell.label", "VNB", 0.23, 0.0))
    cell.add("pwell.pin", (0.145, -0.085, 0.315, 0.085), "VNB")

    # ---- report: what section 4.1 compares ----
    tr = []
    for row, (y0, w) in rows.items():
        for i, g in enumerate(order.gates):
            tr.append({"kind": row, "gate": g, "w": w, "l": POLY_W.value, "x": X(gx[i])})
    diffs = {row: sorted(r.box for r in cell.rects if r.layer == "diff" and r.box[1] == rows[row][0]) for row in rows}
    for t in tr:
        seg = next(d for d in diffs[t["kind"]] if d[0] <= t["x"] <= d[2])
        t["sa"], t["sb"] = snap(t["x"] - seg[0]), snap(seg[2] - (t["x"] + POLY_W.value))
    cell.report.update({
        "pad_gap_um": list(pad_gap), "width_um": width, "width_sites": sites, "gate_order": order.gates,
        "gate_pitch_um": [snap(gx[i + 1] - gx[i]) for i in range(k - 1)],
        "diffusion_breaks": order.breaks, "rows": order.rows, "transistors": tr, "routed_nets": routed,
    })
    return cell


PAD_GAPS = (0.03, 0.045, 0.06, 0.075, 0.09)   # bounded retry: input pads further from the gate


def generate(net, order, name: str, **kw) -> Cell:
    """Try every (left, right) pad offset; keep the narrowest cell whose nets all route, then
    the smallest total offset. At most len(PAD_GAPS)**2 attempts."""
    best, tried = None, 0
    for left in PAD_GAPS:
        for right in PAD_GAPS:
            tried += 1
            c = build(net, order, name, pad_gap=(left, right), **kw)
            ok = not c.report.get("route_failures")
            key = (not ok, c.report["width_sites"], left + right, left)
            if best is None or key < best[0]:
                best = (key, c)
    best[1].report["layout_attempts"] = tried
    return best[1]


def _pin(cell, layer, text, cx, cy):
    s = LI_W.value / 2
    cell.labels.append((f"{layer}.label", text, snap(cx), snap(cy)))
    cell.add(f"{layer}.pin", (cx - s, cy - s, cx + s, cy + s), text)


def write_gds(cell: Cell, path: Path) -> Path:
    import gdsfactory as gf
    if not getattr(write_gds, "_pdk", False):
        gf.gpdk.PDK.activate()             # gdsfactory needs an active PDK; layers are raw (layer, datatype)
        write_gds._pdk = True
    c = gf.Component(cell.name)
    for r in cell.rects:
        x0, y0, x1, y1 = r.box
        c.add_polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer=LAYERS[r.layer])
    for layer, text, x, y in cell.labels:
        c.add_label(text, position=(x, y), layer=LAYERS[layer])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    import klayout.db as kdb
    opts = kdb.SaveLayoutOptions()
    opts.write_context_info = False        # no $$$CONTEXT_INFO$$$ cell: Magic reads the file cleanly
    c.write_gds(str(path), save_options=opts, with_metadata=False)
    c.delete()                             # free the name in gdsfactory's process-wide registry
    return Path(path)


def schematic_spice(net, cell_name: str, wn: float = 0.65, wp: float = 1.0) -> str:
    """The generator's own schematic, in the installed HD netlist's conventions."""
    ports = list(net.inputs) + ["VGND", "VNB", "VPB", "VPWR", "Y"]
    lines = [f".subckt {cell_name} {' '.join(ports)}"]
    for i, t in enumerate(net.transistors):
        body, model, w = ("VNB", "sky130_fd_pr__nfet_01v8", wn) if t.kind == "n" else \
                         ("VPB", "sky130_fd_pr__pfet_01v8_hvt", wp)
        lines.append(f"X{i} {t.drain} {t.gate} {t.source} {body} {model} "
                     f"w={round(w * 1e6)}u l={round(POLY_W.value * 1e6)}u")
    lines.append(".ends")
    return "\n".join(lines) + "\n"
