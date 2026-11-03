"""Four-leaf cuts at mapped-cell boundaries and reclaimable actual cell area.

The M1 AIG enumerator remains the exhaustive discovery flow. These additional
cuts tie candidate savings to cells of the current mapping, rather than
multiplying a frequency by an invented NAND area. Internal cells with outside
fanout are retained. Overlap between different candidate classes remains a
ranking heuristic; the subsequent ABC remapping measures the actual saving.
"""

from collections import defaultdict
from dd2 import boolfn as bf, cuts


def mapped_cuts(netlist, top, libcells):
    mod = netlist["modules"].get(top) or netlist["modules"].get("\\" + top)
    if mod is None:
        raise ValueError(f"missing module {top}")
    lookup = {c.name: c for c in libcells}
    drivers = {}
    users = defaultdict(set)
    for name, cell in mod["cells"].items():
        typ = cell["type"].lstrip("\\")
        known = lookup.get(typ)
        for pin, bits in cell["connections"].items():
            direction = cell.get("port_directions", {}).get(pin)
            if direction == "input":
                for b in bits:
                    users[b].add(name)
        if known and len(cell["connections"].get(known.output, [])) == 1:
            args = []
            for p in known.inputs:
                if len(cell["connections"].get(p, [])) != 1:
                    break
                args.append(cell["connections"][p][0])
            else:
                bit = cell["connections"][known.output][0]
                drivers[bit] = (name, known, args)
    for name, p in mod["ports"].items():
        if p["direction"] == "output":
            for b in p["bits"]:
                users[b].add("@output:" + name)
    memo = {"0": [((), 0)], "1": [((), 1)]}
    active = set()
    areas = {}

    def enum(bit):
        if bit in memo:
            return memo[bit]
        if bit not in drivers:
            memo[bit] = [((bit,), 2)]
            return memo[bit]
        if bit in active:
            raise ValueError("combinational cycle in mapped design")
        active.add(bit)
        name, cell, args = drivers[bit]
        partial = {(): []}
        for arg in args:
            nextp = {}
            for union, tts in partial.items():
                for leaves, tt in enum(arg):
                    u = tuple(sorted(set(union) | set(leaves)))
                    if len(u) > 4:
                        continue
                    lifted = [cuts._lift(union, t, u, 0) for t in tts]
                    lifted.append(cuts._lift(leaves, tt, u, 0))
                    nextp.setdefault(u, lifted)
            partial = nextp
        found = {}
        for leaves, tts in partial.items():
            t = 0
            for row in range(1 << len(leaves)):
                idx = sum(((a >> row) & 1) << k for k, a in enumerate(tts))
                t |= ((cell.tt >> idx) & 1) << row
            found[leaves] = t
        kept = []
        for leaves in sorted(found, key=lambda x: (len(x), x)):
            if not any(set(w) < set(leaves) for w in kept):
                kept.append(leaves)
        out = [(l, found[l]) for l in sorted(kept)] + [((bit,), 2)]
        memo[bit] = out
        active.remove(bit)
        areas[name] = cell.area
        return out

    for bit in drivers:
        enum(bit)

    def cone(bit, leaves, seen):
        if bit in leaves or bit not in drivers:
            return
        name, _, args = drivers[bit]
        if name in seen:
            return
        seen[name] = bit
        for arg in args:
            cone(arg, leaves, seen)

    for root, (rootname, cell, args) in drivers.items():
        for leaves, tt in memo[root][:-1]:
            ess = bf.depends_on(tt, len(leaves))
            n = len(ess)
            if n < 2:
                continue
            t = bf.shrink(tt, len(leaves), ess)
            canonical = bf.canon_p(t, n)
            inside = {}
            cone(root, set(leaves), inside)
            remove = set(inside)
            while True:
                keep = {name for name in remove if name != rootname and users[inside[name]] - remove}
                if not keep:
                    break
                remove -= keep
            area = sum(areas[x] for x in remove)
            yield dict(
                arity=n,
                tt=canonical,
                root=root,
                leaves=list(leaves),
                replaced_area_um2=area,
                removed_cells=sorted(remove),
                shared_cells_retained=len(inside) - len(remove),
            )
