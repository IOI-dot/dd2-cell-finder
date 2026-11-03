"""Cell layout inside the fixed HD frame (Option 1 handout, sections 2 and 3.2).

Geometry is a list of rectangles per GDS layer, in um, built from:
  * the frame of given/plan_hd.json (boundary, areaid.sc, rails, n-well, implants, npc band), copied
    unchanged and stretched only in x to a whole number of sites;
  * the paired Euler ordering: one poly stripe per finger, contact columns where a net must leave
    the diffusion, diffusion breaks where the ordering needs them, W per transistor;
  * one poly pad per input; neighbouring stripes of one input share it over a poly bridge;
  * li1 only for wiring; met1 only in the rails. Each contact starts as one licon at the rail end
    of the diffusion, cellgen.router joins the nets, then every contact stack grows as far as the
    wires allow (HD's cells give up contacts the same way where a wire passes).
Every spacing comes from cellgen.rules.
"""
import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from dd2 import paths

from . import router
from .rules import (CROSS_GAP, DIFF_SP, LI_EDGE, LI_ENC2, LI_HIGH, LI_LOW, LI_SP, LI_W, LICON, LICON_DIFF_ENC,
                    LICON_DIFF_ENC2, LICON_GATE_SP, LICON_POLY_ENC, LICON_POLY_ENC2, LICON_SP, MCON, MET1_END,
                    MET1_HIGH, MET1_LOW, MET1_SP, MET1_W, MIN_DEVICE_W, NPC_ENC, PAD_ON, PAD_OUT, POLY_SP, POLY_W,
                    SEED_N, SEED_N_Y, SEED_P, SEED_P_Y, SITE, snap)

LAYERS = {
    "diff": (65, 20), "poly": (66, 20), "licon": (66, 44), "li1": (67, 20), "mcon": (67, 44),
    "met1": (68, 20), "nwell": (64, 20), "nsdm": (93, 44), "psdm": (94, 20), "hvtp": (78, 44),
    "npc": (95, 20), "areaid": (81, 4), "boundary": (236, 0),
    "li1.label": (67, 5), "li1.pin": (67, 16), "met1.label": (68, 5), "met1.pin": (68, 16),
    "nwell.label": (64, 5), "nwell.pin": (64, 16), "pwell.label": (64, 59), "pwell.pin": (122, 16),
}
RAILS = ("VGND", "VPWR")
DIFF_Y = {"n": 0.235, "p": 2.485}     # the row's fixed edge: W grows from here (plan_hd.json reference)
STRIPE_Y = (0.105, 2.615)             # poly_y of plan_hd.json reference
MIN_W = MIN_DEVICE_W.value


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


@dataclass
class Node:
    """A place in one diffusion row where a net meets the diffusion."""
    row: str
    col: int                  # column j: between gates j-1 and j
    part: str                 # "" whole column, "left"/"right" at a diffusion break
    net: str
    w: float                  # narrowest diffusion beside this column
    end: bool                 # first or last node of a diffusion segment


def _units(gates) -> list:
    """Neighbouring stripes of one input: they share one pad over a poly bridge."""
    out = []
    for i, g in enumerate(gates):
        if out and out[-1][0] == g:
            out[-1][2] = i
        else:
            out.append([g, i, i])
    return out


def _nodes(order, wdef) -> tuple:
    """Per row the nodes along the diffusion, and the columns with a diffusion break."""
    nodes, breaks = [], set()
    for row, slots in order.slots.items():
        devs = [(i, s) for i, s in enumerate(slots) if s is not None]
        wid = lambda s: s.w or wdef[row]                                         # noqa: E731
        if not devs:
            continue
        nodes.append(Node(row, devs[0][0], "", devs[0][1].left, wid(devs[0][1]), True))
        for (i, a), (j, b) in zip(devs, devs[1:]):
            if a.right == b.left:
                nodes.append(Node(row, j, "", a.right, min(wid(a), wid(b)), False))
            elif j == i + 1:
                breaks.add(j)
                nodes.append(Node(row, j, "left", a.right, wid(a), True))
                nodes.append(Node(row, j, "right", b.left, wid(b), True))
            else:
                breaks.add(j)
                nodes.append(Node(row, i + 1, "", a.right, wid(a), True))
                nodes.append(Node(row, j, "right", b.left, wid(b), True))
        nodes.append(Node(row, devs[-1][0] + 1, "", devs[-1][1].right, wid(devs[-1][1]), True))
    return nodes, breaks


def _pad_geometry(d: str, style: str, pad_gap=(0.03, 0.03)) -> dict:
    """Pad offsets from a stripe's left edge. The contact sits pad_gap outside the stripe (L, R; a
    negative gap overlaps it, as HD's nand3_1 B pad does) or on it (C); poly encloses it by 0.05
    beside it (licon.8) and 0.08 above and below (licon.8a), and always reaches the stripe. li1
    overhangs by 0.08 on two opposite sides (li.5): "x" left and right, "y" above and below."""
    lic = {"L": -pad_gap[0] - LICON.value, "R": POLY_W.value + pad_gap[1],
           "C": POLY_W.value / 2 - LICON.value / 2}[d]
    poly = (min(0.0, lic - LICON_POLY_ENC.value), max(POLY_W.value, lic + LICON.value + LICON_POLY_ENC.value))
    over = LI_ENC2.value if style == "x" else 0.0
    return {"lic": lic, "poly": poly, "li": (lic - over, lic + LICON.value + over)}


def build(net, order, name: str, wn: float = 0.65, wp: float = 1.0, frame: dict | None = None,
          pad_gap: tuple = (0.03, 0.03), dirs: list | None = None, style: str = "x",
          cross: tuple = (), route: bool = True, seeds: str = "far", met1: bool = False,
          priority: str | None = None) -> Cell:
    """dirs: one of L, R, C per pad unit; style: li1 pad shape; cross: unit boundaries kept open
    for a vertical li1 wire; seeds: where the first contact of a non-rail net goes: "far" at the
    rail end of the diffusion, "near" at the channel end, "cross" near only for nets that leave
    their row, which leaves the rail-side track free for the nets that stay. met1: nets that li1
    cannot join may jump on met1 (multi-stage cells only, handout Table 3)."""
    frame = (frame or load_frame())["frame"]
    wdef = {"n": wn, "p": wp}
    sizes = [s.w or wdef[r] for r, sl in order.slots.items() for s in sl if s]
    limit = {"n": 0.65, "p": 1.0}
    for r, sl in order.slots.items():
        for s in sl:
            w = (s.w if s else 0) or wdef[r]
            if w > limit[r] + 1e-9 or w < MIN_W - 1e-9:
                raise ValueError(f"W = {w} um does not fit one finger in the HD frame: fold it "
                                 f"(stack sizing) or use {MIN_W} <= W <= 0.65/1.0")
    k = len(order.gates)
    units = _units(order.gates)
    if dirs is None:
        dirs = ["L"] * ((len(units) + 1) // 2) + ["R"] * (len(units) // 2)
    pads = [_pad_geometry(d, style, pad_gap) for d in dirs]
    pad_at = {}                               # stripe -> pad index, for the stripe that carries the pad
    for u, (g, first, last) in enumerate(units):
        pad_at[last if dirs[u] == "R" else first] = u
    unit_of = {i: u for u, (g, f, l) in enumerate(units) for i in range(f, l + 1)}

    nodes, break_cols = _nodes(order, wdef)
    occ = {}
    for nd in nodes:
        occ[nd.net] = occ.get(nd.net, 0) + 1
    gate_nets = set(order.gates)
    needs = lambda n_: n_ in RAILS or n_ == net.output or n_ in gate_nets or occ[n_] > 1      # noqa: E731
    contact_cols = {nd.col for nd in nodes if needs(nd.net)}

    # ---- gate positions (relative; shifted to centre the cell later) ----
    gap_contact = 2 * LICON_GATE_SP.value + LICON.value                      # 0.27
    gap_break = 2 * (LICON_GATE_SP.value + LICON.value + LICON_DIFF_ENC.value) + DIFF_SP.value
    gx = [0.0]
    last_pad = None                           # (poly right, li right) of the pad to the left
    if 0 in pad_at:
        p = pads[pad_at[0]]
        last_pad = (gx[0] + p["poly"][1], gx[0] + p["li"][1])
    for j in range(1, k):
        base = gap_break if j in break_cols else (gap_contact if j in contact_cols else POLY_SP.value)
        x = gx[-1] + POLY_W.value + base
        if unit_of[j] != unit_of[j - 1] and last_pad:
            x = max(x, last_pad[0] + POLY_SP.value)                          # stripe clears the pad on its left
        if j in pad_at:
            p = pads[pad_at[j]]
            if unit_of[j] != unit_of[j - 1]:
                # this pad clears the stripe and the pad on its left
                x = max(x, gx[-1] + POLY_W.value + POLY_SP.value - p["poly"][0])
            if last_pad:
                x = max(x, last_pad[0] + POLY_SP.value - p["poly"][0],
                        last_pad[1] + LI_SP.value - p["li"][0])
                if unit_of[j] in cross:
                    x = max(x, last_pad[1] + CROSS_GAP.value - p["li"][0])
            last_pad = (x + p["poly"][1], x + p["li"][1])
        gx.append(snap(x))

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

    def col_mid(j):
        return (gx[j - 1] + POLY_W.value + gx[j]) / 2

    # ---- diffusion rectangles: one per device, stepped where W changes ----
    diff_rects = []
    for row, slots in order.slots.items():
        devs = [(i, s) for i, s in enumerate(slots) if s is not None]
        for t, (i, s) in enumerate(devs):
            prev = devs[t - 1] if t else None
            nxt = devs[t + 1] if t + 1 < len(devs) else None
            if prev and prev[1].right == s.left:
                x0 = col_mid(i)
            else:
                part = "right" if prev and i in break_cols and prev[0] == i - 1 else ("right" if i in break_cols and prev else "")
                x0 = contact_x(i, part)[0] - LICON_DIFF_ENC.value
            if nxt and nxt[1].left == s.right:
                x1 = col_mid(nxt[0])
            else:
                part = "left" if nxt and nxt[0] == i + 1 else ""
                x1 = contact_x(i + 1, part)[1] + LICON_DIFF_ENC.value
            diff_rects.append((row, x0, x1, s.w or wdef[row]))

    # ---- extents and width ----
    poly_ext = [(gx[i] + (pads[pad_at[i]]["poly"][0] if i in pad_at else 0.0),
                 gx[i] + (pads[pad_at[i]]["poly"][1] if i in pad_at else POLY_W.value)) for i in range(k)]
    li_ext = [(gx[i] + pads[pad_at[i]]["li"][0], gx[i] + pads[pad_at[i]]["li"][1]) for i in pad_at]
    contact_ext = [contact_x(nd.col, nd.part) for nd in nodes if needs(nd.net)]
    lo = min(min(d[1] for d in diff_rects) - DIFF_SP.value / 2, min(p[0] for p in poly_ext) - POLY_SP.value / 2,
             min(p[0] for p in li_ext) - LI_SP.value / 2)
    hi = max(max(d[2] for d in diff_rects) + DIFF_SP.value / 2, max(p[1] for p in poly_ext) + POLY_SP.value / 2,
             max(p[1] for p in li_ext) + LI_SP.value / 2)
    sites = math.ceil(round((hi - lo) / SITE.value, 6))
    width = snap(sites * SITE.value)
    shift = snap(-lo + (width - (hi - lo)) / 2)
    X = lambda v: snap(v + shift)                                            # noqa: E731
    cell = Cell(name, width)
    if not route:                                        # the search only needs the width
        cell.report["width_sites"] = sites
        return cell

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

    band = frame["npc_band"]["y"]
    lic_y = (snap(band[0] + NPC_ENC.value), snap(band[0] + NPC_ENC.value + LICON.value))
    pad_y = (snap(lic_y[0] - LICON_POLY_ENC2.value), snap(lic_y[1] + LICON_POLY_ENC2.value))

    # ---- poly: gate stripes, bridges between same-input stripes, input pads ----
    terminals, pad_boxes = {}, {}
    has = {r: [s is not None for s in sl] for r, sl in order.slots.items()}
    for i, g in enumerate(order.gates):
        x0 = X(gx[i])
        y0 = STRIPE_Y[0] if has["n"][i] else pad_y[0]
        y1 = STRIPE_Y[1] if has["p"][i] else pad_y[1]
        cell.add("poly", (x0, y0, x0 + POLY_W.value, y1), g)
    for g, first, last in units:
        if last > first:
            cell.add("poly", (X(gx[first]), pad_y[0], X(gx[last]) + POLY_W.value, pad_y[1]), g)
    for i, u in pad_at.items():
        g = units[u][0]
        p = pads[u]
        x0 = X(gx[i])
        lx = x0 + p["lic"]
        cell.add("licon", (lx, lic_y[0], lx + LICON.value, lic_y[1]), g)
        cell.add("poly", (x0 + p["poly"][0], pad_y[0], x0 + p["poly"][1], pad_y[1]), g)
        box = (x0 + p["li"][0], lic_y[0], x0 + p["li"][1], lic_y[1]) if style == "x" else \
              (x0 + p["li"][0], pad_y[0], x0 + p["li"][1], pad_y[1])
        box = tuple(snap(v) for v in box)
        cell.add("li1", box, g)
        terminals.setdefault(g, []).append([box])
        pad_boxes.setdefault(g, []).append(box)

    # ---- diffusion ----
    y_of = {"n": lambda w: (DIFF_Y["n"], DIFF_Y["n"] + w), "p": lambda w: (DIFF_Y["p"] - w, DIFF_Y["p"])}
    for row, x0, x1, w in diff_rects:
        ya, yb = y_of[row](w)
        cell.add("diff", (X(x0), ya, X(x1), yb))

    # ---- one seed contact per node: the first licon away from the channel, grown after routing ----
    contacts = []
    for nd in nodes:
        if not needs(nd.net):
            continue
        cx0 = X(contact_x(nd.col, nd.part)[0])
        cx1 = snap(cx0 + LICON.value)        # snapped once, or a mid-column contact loses a grid step
        c = {"nd": nd, "x": (cx0, cx1), "rail": nd.net in RAILS, "licons": []}
        contacts.append(c)
    by_row = {}
    for c in contacts:
        by_row.setdefault(c["nd"].row, []).append(c)
    for row, cs in by_row.items():
        cs.sort(key=lambda c: c["x"][0])
        wide = []                                      # a wide pad needs LI_SP to its neighbours' pads
        for c in cs:
            ok = not c["rail"] and all(
                (o["x"][0] - c["x"][1] if o["x"][0] > c["x"][0] else c["x"][0] - o["x"][1])
                - LI_ENC2.value * (1 + (o in wide)) >= LI_SP.value - 1e-9 for o in cs if o is not c)
            c["style"] = "rail" if c["rail"] else ("x" if ok or c["nd"].w < 0.31 else "y")
            if c["style"] == "x":
                wide.append(c)
    rows_of = {}
    for c in contacts:
        rows_of.setdefault(c["nd"].net, set()).add(c["nd"].row)
    for c in contacts:
        nd, (cx0, cx1) = c["nd"], c["x"]
        leaves = len(rows_of[nd.net]) > 1 or nd.net in gate_nets
        c["near"] = not c["rail"] and (seeds == "near" or (seeds == "cross" and leaves))
        lo_y, hi_y = _seed(nd.row, c["style"], nd.w, c["near"])
        cell.add("licon", (cx0, lo_y, cx1, hi_y), nd.net)
        c["licons"].append((lo_y, hi_y))
        c["box"] = _li_box(nd.row, c["style"], cx0, cx1, lo_y, hi_y)
        cell.add("li1", c["box"], nd.net)
        if not c["rail"]:
            terminals.setdefault(nd.net, []).append([c["box"]])

    # ---- route nets that join several shapes ----
    half = LI_W.value / 2                        # the window holds wire centres
    window = (LI_EDGE.value, LI_LOW.value + half, width - LI_EDGE.value, LI_HIGH.value - half)
    route_nets = [n_ for n_ in terminals if len(terminals[n_]) > 1]
    fixed = [r for r in cell.rects if r.layer == "li1"]
    routed, failed = _route(route_nets, terminals, fixed, window, priority)
    for n_, wires in routed.items():
        for wbox in wires:
            cell.add("li1", wbox, n_)
    jumped = _jump(cell, failed, terminals, window) if met1 and failed else []
    failed = [n_ for n_ in failed if n_ not in jumped]
    if failed:
        cell.report["route_failures"] = failed
    cell.report["met1_nets"] = jumped

    # ---- grow every contact stack as far as the wires allow ----
    for c in contacts:
        _grow(cell, c)

    _fill_notches(cell)
    _fill_notches(cell, "met1", MET1_SP.value)
    clashes = _li_clashes(cell)
    if clashes:
        cell.report.setdefault("route_failures", []).extend(clashes)

    # ---- pins and labels (HD conventions, plan_hd.json "pins") ----
    for g in net.inputs:
        for box in pad_boxes.get(g, []):
            _pin(cell, "li1", g, (box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    ypads = [c["box"] for c in contacts if c["nd"].net == net.output]
    for pad in ypads[:2]:
        _pin(cell, "li1", net.output, (pad[0] + pad[2]) / 2, (pad[1] + pad[3]) / 2)
    for rail, y in (("VGND", 0.0), ("VPWR", 2.72)):
        cell.labels.append(("met1.label", rail, 0.23, y))
        cell.add("met1.pin", (0.145, y - 0.085, 0.315, y + 0.085), rail)
    cell.labels.append(("nwell.label", "VPB", 0.23, 2.72))
    cell.add("nwell.pin", (0.145, 2.635, 0.315, 2.805), "VPB")
    cell.labels.append(("pwell.label", "VNB", 0.23, 0.0))
    cell.add("pwell.pin", (0.145, -0.085, 0.315, 0.085), "VNB")

    # ---- report: what section 4.1 compares; SA and SB are known here (handout section 5) ----
    tr = []
    for row, slots in order.slots.items():
        segs = _diff_segments([d for d in diff_rects if d[0] == row])
        for i, s in enumerate(slots):
            if s is None:
                continue
            x = gx[i]
            seg = next(a for a in segs if a[0] <= x <= a[1])
            tr.append({"kind": row, "gate": order.gates[i], "w": s.w or wdef[row], "l": POLY_W.value, "x": X(x),
                       "sa": snap(x - seg[0]), "sb": snap(seg[1] - (x + POLY_W.value))})
    cell.report.update({
        "pad_gap_um": list(pad_gap), "pad_dirs": dirs, "pad_style": style, "width_um": width, "width_sites": sites,
        "gate_order": order.gates, "gate_pitch_um": [snap(gx[i + 1] - gx[i]) for i in range(k - 1)],
        "diffusion_breaks": order.breaks, "row_breaks": order.row_breaks, "rows": order.rows, "transistors": tr,
        "routed_nets": {n_: len(w) for n_, w in routed.items()},
        "contacts": {f"{c['nd'].row}{c['nd'].col}{c['nd'].part} {c['nd'].net}": len(c["licons"]) for c in contacts},
    })
    return cell


def _diff_segments(rects) -> list:
    segs = []
    for _, a, b, _ in sorted(rects, key=lambda d: d[1]):
        if segs and a <= segs[-1][1] + 1e-9:
            segs[-1][1] = max(segs[-1][1], b)
        else:
            segs.append([a, b])
    return segs


def _seed(row: str, style: str, w: float, near: bool = False) -> tuple:
    """The contact that stays whatever is routed. Far: at the rail end of the diffusion, where a y
    pad's li1 overhang must still clear the rail strip by LI_SP. Near: at the channel end, inside
    the diffusion by licon.5c."""
    enc = LICON_DIFF_ENC2.value
    if near:
        lo = snap(DIFF_Y["n"] + w - enc - LICON.value) if row == "n" else snap(DIFF_Y["p"] - w + enc + 0.03)
        if row == "n" and lo < SEED_N.value:
            lo = SEED_N.value
        if row == "p" and lo > SEED_P.value:
            lo = SEED_P.value
        return lo, snap(lo + LICON.value)
    if row == "n":
        lo = {"rail": SEED_N.value, "x": SEED_N.value, "y": SEED_N_Y.value}[style]
    else:
        lo = {"rail": SEED_P.value, "x": SEED_P.value, "y": SEED_P_Y.value}[style]
    return lo, snap(lo + LICON.value)


def _li_box(row, style, x0, x1, lo, hi) -> tuple:
    if style == "x":
        return tuple(snap(v) for v in (x0 - LI_ENC2.value, lo, x1 + LI_ENC2.value, hi))
    if style == "rail":
        return (x0, -0.085, x1, snap(hi + LI_ENC2.value)) if row == "n" else (x0, snap(lo - LI_ENC2.value), x1, 2.805)
    return tuple(snap(v) for v in (x0, lo - LI_ENC2.value, x1, hi + LI_ENC2.value))


def _spaced(a, b, sp=LI_SP.value) -> bool:
    dx = max(b[0] - a[2], a[0] - b[2])
    dy = max(b[1] - a[3], a[1] - b[3])
    if dx <= 0 or dy <= 0:
        return max(dx, dy) >= sp - 1e-9
    return dx * dx + dy * dy >= sp * sp - 1e-9


def _grow(cell, c):
    """Add contacts toward the channel while the diffusion and the other nets' li1 allow it."""
    nd = c["nd"]
    x0, x1 = c["x"]
    pitch = LICON.value + LICON_SP.value
    enc = LICON_DIFF_ENC2.value if nd.end else LICON_DIFF_ENC.value
    others = [r.box for r in cell.rects if r.layer == "li1" and r.net != nd.net]
    up = (nd.row == "n") != c.get("near", False)     # toward the channel, or from it toward the rail
    while True:
        lo, hi = c["licons"][-1]
        a, b = (snap(lo + pitch), snap(hi + pitch)) if up else (snap(lo - pitch), snap(hi - pitch))
        low, high = (DIFF_Y["n"], DIFF_Y["n"] + nd.w) if nd.row == "n" else (DIFF_Y["p"] - nd.w, DIFF_Y["p"])
        if b > high - enc + 1e-9 or a < low + enc - 1e-9:
            return
        over = LI_ENC2.value
        if c["style"] == "x":
            box = (x0 - over, min(a, lo), x1 + over, max(b, hi))
        elif up:
            box = (x0, lo, x1, snap(b + over))
        else:
            box = (x0, snap(a - over), x1, hi)
        if nd.net not in RAILS and (box[1] < LI_LOW.value - 1e-9 or box[3] > LI_HIGH.value + 1e-9):
            return
        if not all(_spaced(box, o) for o in others):
            return
        cell.add("licon", (x0, a, x1, b), nd.net)
        cell.add("li1", box, nd.net)
        c["licons"].append((a, b))


def _fill_notches(cell, layer="li1", space=LI_SP.value):
    """Spacing rules do not know nets: two shapes of one net closer than the rule become one shape."""
    for _ in range(4):
        shapes = [r for r in cell.rects if r.layer == layer and r.net not in RAILS or r.layer == layer and layer == "li1"]
        added = False
        for i, a in enumerate(shapes):
            for b in shapes[i + 1:]:
                if a.net != b.net:
                    continue
                p, q = a.box, b.box
                dx, dy = max(q[0] - p[2], p[0] - q[2]), max(q[1] - p[3], p[1] - q[3])
                if 0 < dx < space - 1e-9 and dy < 0:
                    x0, x1 = (p[2], q[0]) if p[2] <= q[0] else (q[2], p[0])
                    cell.add(layer, (x0, max(p[1], q[1]), x1, min(p[3], q[3])), a.net)
                    added = True
                elif 0 < dy < space - 1e-9 and dx < 0:
                    y0, y1 = (p[3], q[1]) if p[3] <= q[1] else (q[3], p[1])
                    cell.add(layer, (max(p[0], q[0]), y0, min(p[2], q[2]), y1), a.net)
                    added = True
        if not added:
            return


def _jump(cell, failed, terminals, window) -> list:
    """Nets li1 could not finish: keep what li1 joins, then met1 between the pieces."""
    done = []
    m1_window = (window[0], MET1_LOW.value, window[2], MET1_HIGH.value)
    half = MET1_W.value / 2
    for n_ in failed:
        others = [r.box for r in cell.rects if r.layer == "li1" and r.net != n_]
        wires, parts = router.connect_parts(terminals[n_], window, others)
        if len(parts) == 1:
            continue
        m1 = [r.box for r in cell.rects if r.layer == "met1" and r.net not in RAILS]
        hops = router.jump([[b for b in p if b[3] - b[1] >= LI_W.value - 1e-9 and b[2] - b[0] >= LI_W.value - 1e-9]
                            for p in parts], m1_window, m1, half, MET1_SP.value)
        if hops is None:
            continue
        for wbox in wires:
            cell.add("li1", wbox, n_)
        for rects, vias in hops:
            for b in rects:
                cell.add("met1", b, n_)
            # the pad runs along the wire it ends, so that it adds no notch beside that wire
            for (x, y), wire in zip(vias, (rects[0], rects[-1]) if rects else (None, None)):
                s = MCON.value / 2
                cell.add("mcon", (x - s, y - s, x + s, y + s), n_)
                along_x = wire is None or wire[2] - wire[0] > wire[3] - wire[1]
                dx, dy = (s + MET1_END.value, half) if along_x else (half, s + MET1_END.value)
                cell.add("met1", (x - dx, y - dy, x + dx, y + dy), n_)
        done.append(n_)
    return done


def _li_clashes(cell) -> list:
    """What this generator can get wrong and can see by itself; such a layout goes no further than
    this check: different nets closer than their spacing rule, and a contact that is not square."""
    out = set()
    for layer, space in (("li1", LI_SP.value), ("met1", MET1_SP.value)):
        shapes = [r for r in cell.rects if r.layer == layer]
        out |= {f"{a.net}/{b.net}" for i, a in enumerate(shapes) for b in shapes[i + 1:]
                if a.net != b.net and not _spaced(a.box, b.box, space)}
    out |= {f"contact {r.box}" for r in cell.rects if r.layer in ("licon", "mcon")
            and (abs(r.box[2] - r.box[0] - LICON.value) > 1e-9 or abs(r.box[3] - r.box[1] - LICON.value) > 1e-9)}
    return sorted(out)


def _route(route_nets, terminals, fixed, window, priority=None, tries=8) -> tuple:
    """Rip up and retry: every failed net moves to the front of the order."""
    order = sorted(route_nets, key=lambda n_: (n_ != priority, -len(terminals[n_]), n_))
    best = ({}, list(order))
    for _ in range(tries):
        routed, failed, wires_so_far = {}, [], []
        for n_ in order:
            others = [r.box for r in fixed if r.net != n_] + [b for m, w in routed.items() if m != n_ for b in w]
            wires = router.connect(terminals[n_], window, others)
            if wires is None:
                failed.append(n_)
            else:
                routed[n_] = wires
        if not failed:
            return routed, []
        if len(failed) < len(best[1]):
            best = (routed, failed)
        order = failed + [n_ for n_ in order if n_ not in failed]
    return best


_OUT, _ON = PAD_OUT.value, PAD_ON.value
PAD_GAPS = ((_OUT, _ON), (_ON, _OUT), (_OUT, _OUT), (_ON, _ON))     # left and right pads, as HD splays them first
MAX_ATTEMPTS, MAX_PER_WIDTH = 3600, 2000      # per pass: li1 only, then with met1
WIDE_CELL, WIDE_ATTEMPTS = 7, 1000            # stripes; one attempt costs more in a wide cell


def _patterns(units, net) -> list:
    """Pad directions to try. A wire crosses the pad row at a unit boundary where the left pad goes
    left and the right pad goes right (as HD's nand3_1 and a21oi_1 do)."""
    m = len(units)
    if m == 1:
        return [["L"], ["R"], ["C"]]
    if m <= 6:
        return [list(p) for p in itertools.product("LR", repeat=m)]
    out = []
    for s in range(m + 1):
        out.append(["L"] * s + ["R"] * (m - s))
    out.append(["L", "R"] * (m // 2) + ["L"] * (m % 2))
    out.append(["R", "L"] * (m // 2) + ["R"] * (m % 2))
    return out


def generate(net, order, name: str, orders=None, order_index=None, priority=None, allow_met1=True, progress=None, **kw) -> Cell:
    """Every ordering and pad pattern, narrowest first; the first that routes wins. At most
    MAX_ATTEMPTS full layouts. If none routes, the narrowest failed layout comes back with its
    route_failures, so the check fails and says which nets. The three choices a caller may make:
    order_index keeps one ordering only, priority routes that net first, allow_met1=False keeps
    a multi-stage cell on li1."""
    orders = orders or [order]
    if order_index is not None:
        orders = [orders[order_index % len(orders)]]
    if priority:
        kw["priority"] = priority
    plans = []
    for oi, o in enumerate(orders):
        units = _units(o.gates)
        for dirs in _patterns(units, net):
            for style in ("x", "y"):
                splays = [u for u in range(1, len(units)) if dirs[u - 1] == "L" and dirs[u] == "R"]
                for cross in ((), tuple(splays)) if splays else ((),):
                    for gap in PAD_GAPS:
                        w = build(net, o, name, dirs=dirs, style=style, cross=cross, route=False,
                                  pad_gap=gap, **kw).report["width_sites"]
                        plans.append((w, oi, o.breaks, style != "x", len(cross), gap, dirs, style, cross, o))
    plans.sort(key=lambda p: p[:6] + (p[6],))
    best, tried = None, 0
    wide = len(orders[0].gates) >= WIDE_CELL
    budget, per_width = (WIDE_ATTEMPTS, WIDE_ATTEMPTS // 2) if wide else (MAX_ATTEMPTS, MAX_PER_WIDTH)
    # li1 first; met1 only when li1 has failed, and only in a multi-stage cell (handout Table 3).
    # A bounded number of tries per width, so that a hard width cannot use up the whole search.
    for met1 in (False, True) if len(net.stages) > 1 and allow_met1 else (False,):
        start, used = tried, {}
        limit = per_width // 3 if met1 else per_width       # met1 moves on to wider cells sooner
        for w, _, _, _, _, gap, dirs, style, cross, o in plans:
            if used.get(w, 0) >= limit or tried - start >= budget:
                continue
            # a via needs li1 clear of the rails, so met1 runs seed their contacts near the channel
            for seeds in ("near", "cross") if met1 else ("far", "cross", "near"):
                tried += 1
                used[w] = used.get(w, 0) + 1
                c = build(net, o, name, dirs=dirs, style=style, cross=cross, pad_gap=gap, seeds=seeds, met1=met1, **kw)
                if progress:
                    progress({"n": tried, "sites": w, "order": " ".join(o.gates), "pads": "".join(dirs), "style": style, "gap": gap, "seeds": seeds,
                              "met1": met1, "failed": list(c.report.get("route_failures") or [])}, c)
                if not c.report.get("route_failures"):
                    c.report["layout_attempts"] = tried
                    return c
                if best is None or len(c.report["route_failures"]) < len(best.report["route_failures"]):
                    best = c
    best.report["layout_attempts"] = tried
    return best


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
    ports = list(net.inputs) + ["VGND", "VNB", "VPB", "VPWR", net.output]
    lines = [f".subckt {cell_name} {' '.join(ports)}"]
    for i, t in enumerate(net.transistors):
        body, model, w = ("VNB", "sky130_fd_pr__nfet_01v8", wn) if t.kind == "n" else \
                         ("VPB", "sky130_fd_pr__pfet_01v8_hvt", wp)
        lines.append(f"X{i} {t.drain} {t.gate} {t.source} {body} {model} "
                     f"w={round((t.w or w) * 1e6)}u l={round(POLY_W.value * 1e6)}u")
    lines.append(".ends")
    return "\n".join(lines) + "\n"
