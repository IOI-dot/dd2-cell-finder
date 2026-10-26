"""AIG extraction (Option 2 handout section 4, step 1) and an AIGER reader (aig and aag).

synth:        read_verilog; synth -flatten -top; async2sync; dffunmap; aigmap; write_aiger
restructured: ABC on the synth AIG: strash; dch -f; strash  (the last strash removes the choice
              nodes that dch leaves, research D-4)
Plain write_aiger is used: its latch count equals the flip-flop count after synth, while -zinit
adds an input and logic per flip-flop. The -zinit header is still recorded for comparison.
"""
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import designs, paths, provenance, tools


@dataclass
class Aig:
    M: int
    I: int
    L: int
    O: int
    A: int
    inputs: list = field(default_factory=list)
    latches: list = field(default_factory=list)   # (lit, next, init)
    outputs: list = field(default_factory=list)
    ands: list = field(default_factory=list)       # (lhs, rhs0, rhs1), lhs even
    B: int = 0
    bad: list = field(default_factory=list)        # bad-state literals; ABC writes POs here

    def all_outputs(self) -> list:
        """Primary outputs, including those an AIGER writer stored as bad-state properties."""
        return self.outputs + self.bad

    def fanins(self) -> dict:
        """AND variable -> (rhs0 literal, rhs1 literal)."""
        return {lhs >> 1: (r0, r1) for lhs, r0, r1 in self.ands}

    def levels(self) -> int:
        lev = {}
        for lhs, r0, r1 in self.ands:
            lev[lhs >> 1] = 1 + max(lev.get(r0 >> 1, 0), lev.get(r1 >> 1, 0))
        return max(lev.values(), default=0)


def _decode(data: bytes, pos: int):
    x, shift = 0, 0
    while True:
        if pos >= len(data):
            raise ValueError("truncated binary AND section")
        b = data[pos]
        pos += 1
        x |= (b & 0x7F) << shift
        if not b & 0x80:
            return x, pos
        shift += 7


def read_aiger(path: Path) -> Aig:
    data = Path(path).read_bytes()
    nl = data.find(b"\n")
    head = data[:nl].decode("ascii", "replace").split()
    if len(head) < 6 or head[0] not in ("aig", "aag") or not all(t.isdigit() for t in head[1:]):
        raise ValueError(f"{path}: malformed AIGER header {' '.join(head)!r}")
    fmt = head[0]
    M, I, L, O, A = map(int, head[1:6])
    extra = list(map(int, head[6:])) + [0, 0, 0, 0]
    B, C, J, F = extra[:4]
    if J or F:
        raise ValueError(f"{path}: justice/fairness properties are not supported")
    if M < I + L + A:
        raise ValueError(f"{path}: M={M} < I+L+A={I + L + A}")
    g = Aig(M, I, L, O, A, B=B)
    pos = nl + 1

    def line():
        nonlocal pos
        end = data.find(b"\n", pos)
        if end < 0:
            raise ValueError(f"{path}: unexpected end of file")
        s = data[pos:end].decode("ascii")
        pos = end + 1
        return list(map(int, s.split()))

    if fmt == "aag":
        g.inputs = [line()[0] for _ in range(I)]
    else:
        g.inputs = [2 * (i + 1) for i in range(I)]
    for i in range(L):
        t = line()
        if fmt == "aig":
            t = [2 * (I + i + 1)] + t
        g.latches.append((t[0], t[1], t[2] if len(t) > 2 else 0))
    g.outputs = [line()[0] for _ in range(O)]
    g.bad = [line()[0] for _ in range(B)]
    for _ in range(C):
        line()
    if fmt == "aag":
        g.ands = [tuple(line()) for _ in range(A)]
    else:
        for i in range(A):
            lhs = 2 * (I + L + i + 1)
            d0, pos = _decode(data, pos)
            d1, pos = _decode(data, pos)
            r0 = lhs - d0
            g.ands.append((lhs, r0, r0 - d1))
    defined = set(range(I + L + 1))                  # constant, inputs and latches
    for lhs, r0, r1 in g.ands:
        if lhs & 1 or r0 < 0 or r1 < 0 or lhs >> 1 > M or r0 >> 1 > M or r1 >> 1 > M:
            raise ValueError(f"{path}: bad AND {lhs} {r0} {r1}")
        if r0 >> 1 not in defined or r1 >> 1 not in defined:
            raise ValueError(f"{path}: AND {lhs} uses a node defined later; "
                             "AND gates must be in topological order")
        defined.add(lhs >> 1)
    return g


def header(path: Path) -> dict:
    with open(path, "rb") as f:
        t = f.readline().decode("ascii").split()
    vals = list(map(int, t[1:])) + [0, 0]
    return dict(zip("MILOABC", vals[:7]))


def outputs(h: dict) -> int:
    return h.get("O", 0) + h.get("B", 0)


def cec(a: Path, b: Path, log: Path) -> bool:
    """ABC combinational equivalence of two AIGs (latches matched by order; initial values are
    not compared, which is harmless while every latch is uninitialised)."""
    code, _ = tools.run(tools.abc_cmd() + ["-c", f"cec {paths.rel(a)} {paths.rel(b)}"], log,
                        timeout=1800, cwd=paths.ROOT)
    return code == 0 and "Networks are equivalent" in Path(log).read_text()


FF_TYPES = re.compile(r"FF|DLATCH|_SR_")


def _ffs(stat_json: Path) -> int:
    mod = next(iter(json.loads(stat_json.read_text())["modules"].values()))
    return sum(v for k, v in mod.get("num_cells_by_type", {}).items() if FF_TYPES.search(k))


def extract_design(design, given: Path, out: Path, src: Path | None = None,
                   scratch: Path | None = None) -> dict:
    d = Path(out) / design.name
    d.mkdir(parents=True, exist_ok=True)
    scratch = Path(scratch or paths.build("aigs")) / design.name
    scratch.mkdir(parents=True, exist_ok=True)
    src = Path(src) if src else Path(given) / "designs" / f"{design.name}.v"
    synth_aig, restr_aig = d / "synth.aig", d / "restructured.aig"
    arts = {}
    R = paths.rel                                    # records carry repository-relative paths

    cmds = [f"read_verilog {'-sv ' if design.sv else ''}{R(src)}", f"synth -flatten -top {design.top}",
            f"tee -q -o {R(scratch / 'ffstat.json')} stat -json", "async2sync", "dffunmap", "aigmap",
            f"write_aiger {R(synth_aig)}", f"write_aiger -zinit {R(scratch / 'synth_zinit.aig')}"]
    argv = tools.yosys_cmd() + ["-q", "-p", "; ".join(cmds)]
    rec = provenance.RunRecord(argv=[str(a) for a in argv], inputs=provenance.hash_inputs([src]),
                               tools={"yosys": tools.version(tools.yosys_cmd() + ["-V"])})
    code, _ = tools.run(argv, d / "synth.log", cwd=paths.ROOT)
    art = {"design": design.name, "variant": "synth", "aig_path": paths.rel(synth_aig), "commands": cmds}
    if code == 0 and synth_aig.exists():
        art.update(aig_sha256=provenance.sha256(synth_aig), header=header(synth_aig),
                   outputs=outputs(header(synth_aig)),
                   levels=read_aiger(synth_aig).levels(), ffs_after_synth=_ffs(scratch / "ffstat.json"),
                   zinit_header=header(scratch / "synth_zinit.aig"),
                   handout_ffs=design.handout_ffs, handout_ands=design.handout_ands)
    rec.finish(code, logs=[d / "synth.log"])
    if code == 0 and art.get("header", {}).get("L") != art.get("ffs_after_synth"):
        rec.status = "fail"
        art["error"] = "latch count differs from flip-flop count"
    art["run"] = rec.asdict()
    provenance.write_json(d / "synth.json", art)
    arts["synth"] = art

    cmds = [f"read {R(synth_aig)}", "strash", "print_stats", "dch -f", "strash", "print_stats",
            f"write_aiger {R(restr_aig)}"]
    argv = tools.abc_cmd() + ["-c", "; ".join(cmds)]
    rec = provenance.RunRecord(argv=[str(a) for a in argv],
                               inputs=provenance.hash_inputs([synth_aig]) if synth_aig.exists() else {},
                               tools={"abc": "yosys-abc bundled with " + str(rec.tools["yosys"])})
    code, _ = tools.run(argv, d / "restructured.log", cwd=paths.ROOT) if synth_aig.exists() else (1, 0)
    art = {"design": design.name, "variant": "restructured", "aig_path": paths.rel(restr_aig), "commands": cmds}
    if code == 0 and restr_aig.exists():
        log = (d / "restructured.log").read_text()
        stats = [int(x) for x in re.findall(r"and =\s*(\d+)", log)]
        art.update(aig_sha256=provenance.sha256(restr_aig), header=header(restr_aig),
                   outputs=outputs(header(restr_aig)), levels=read_aiger(restr_aig).levels(),
                   strash_only_ands=stats[0] if stats else None,
                   has_choices=bool(re.search(r"and =\s*\d+\s*\(choice", log)),
                   equivalent_to_synth=cec(synth_aig, restr_aig, d / "cec.log"))
        problems = []
        if art["has_choices"]:
            problems.append("restructured AIG has choice nodes")
        if art["outputs"] != arts["synth"].get("outputs"):
            problems.append(f"outputs {art['outputs']} != synth {arts['synth'].get('outputs')}")
        if not art["equivalent_to_synth"]:
            problems.append("ABC cec: restructured is not equivalent to synth")
        if problems:
            code = 1
            art["error"] = "; ".join(problems)
    rec.finish(code, logs=[d / "restructured.log", d / "cec.log"])
    art["run"] = rec.asdict()
    provenance.write_json(d / "restructured.json", art)
    arts["restructured"] = art
    return arts


def run_all(given: Path, out: Path, names=None, scratch: Path | None = None) -> int:
    names = names or [d.name for d in designs.required()]
    manifest, rows, ok = [], [], True
    for n in names:
        arts = extract_design(designs.get(n), given, out, scratch=scratch)
        for v, a in arts.items():
            ok &= a["run"]["status"] == "pass"
            manifest.append({k: a.get(k) for k in ("design", "variant", "aig_path", "aig_sha256",
                                                   "header", "outputs", "levels", "ffs_after_synth",
                                                   "equivalent_to_synth")}
                            | {"status": a["run"]["status"], "record": paths.rel(Path(out) / n / f"{v}.json")})
        s, r = arts["synth"], arts["restructured"]
        rows.append([n, s.get("ffs_after_synth"), s.get("handout_ffs"), s.get("header", {}).get("A"),
                     s.get("levels"), r.get("header", {}).get("A"), r.get("levels"),
                     s.get("zinit_header", {}).get("A"), s.get("handout_ands"),
                     r.get("strash_only_ands"), r.get("equivalent_to_synth")])
        print(f"{n:10s} synth ANDs {rows[-1][3]} lev {rows[-1][4]} | restructured ANDs {rows[-1][5]} "
              f"lev {rows[-1][6]} | {s['run']['status']}/{r['run']['status']}")
    expected = 2 * len(names)
    if len(manifest) != expected:
        ok = False
    provenance.write_json(Path(out) / "manifest.json",
                          {"expected_artifacts": expected, "artifacts": manifest,
                           "status": "pass" if ok else "fail", "written": provenance.now()})
    with open(Path(out) / "compare.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["design", "ffs_after_synth", "handout_ffs", "synth_ands", "synth_levels",
                    "restructured_ands", "restructured_levels", "zinit_ands", "handout_ands",
                    "strash_only_ands", "restructured_equivalent"])
        w.writerows(rows)
    return 0 if ok else 1
