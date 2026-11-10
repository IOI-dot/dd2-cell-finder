"""Course tutorial inputs and fresh, zero-delay gate simulations.

The original source/testbench bytes live outside git behind tutorials/.
Cell models are generated from the exact mapping Liberty, including its
sequential functions. These are functional GLS, not SDF/timing simulations.
"""

from pathlib import Path
import re

from dd2 import aig, cutflow, designs, mapping, paths, provenance, tools
from . import evaluate

SPECS = {
    "spm": {
        "top": "SPM",
        "sources": ["SPM.v", "CSADD.v", "TCMP.v"],
        "testbench": "SPM_tb.v",
        "tb_top": "SPM_tb",
        "pass_marker": "PASS: SPM behaves as a signed 32x32 multiplier",
    },
    "multiplier": {
        "top": "mul",
        "sources": ["mul.v"],
        "testbench": "mul_exhaustive_tb.v",
        "tb_top": "mul_exhaustive_tb",
        "pass_marker": "PASS: all 65536 signed input pairs correct",
    },
}


def input_files(name):
    s = SPECS[name]
    return [paths.ROOT / "tutorials" / name / n for n in s["sources"] + [s["testbench"]]]


def supplied(name):
    return all(p.is_file() for p in input_files(name))


def resolve(name):
    if name not in SPECS:
        return designs.get(name), paths.given() / "designs" / f"{name}.v"
    if not supplied(name):
        raise ValueError(f"{name}: missing original tutorial RTL/testbench; run the GB4 input installer")
    s = SPECS[name]
    # Concatenate the unmodified sources for APIs that accept a single file.
    # Preserve every copyright notice and document the source hashes.
    dest = paths.build("tutorials", name, "combined.v")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\n".join(p.read_bytes() for p in input_files(name)[:-1]) + b"\n")
    provenance.write_json(dest.with_suffix(".inputs.json"), provenance.hash_inputs(input_files(name)))
    return designs.Design(name, s["top"], False), dest


def simulation_passed(code, text, marker):
    return (
        code == 0
        and marker in text
        and not re.search(r"(?im)^\s*(?:ERROR|FAIL|FATAL|MISMATCH)(?:\b|:)", text)
    )


def simulate(name, sources, out, lib=None):
    out = Path(out).absolute()
    out.mkdir(parents=True, exist_ok=True)
    spec = SPECS[name]
    tb = paths.ROOT / "tutorials" / name / spec["testbench"]
    source_files = [Path(p).absolute() for p in sources]
    if lib is not None:
        models = out / "liberty_models.v"
        evaluate.command(
            f"read_liberty -ignore_miss_func {evaluate.quote(lib)}\n"
            f"write_verilog -noattr {evaluate.quote(models)}",
            out / "models.log",
        )
        source_files.append(models)
    program = out / "simulation.vvp"
    argv = [
        "iverilog",
        "-g2012",
        "-s",
        spec["tb_top"],
        "-o",
        str(program),
        str(tb.resolve()),
        *map(str, source_files),
    ]
    code, _ = tools.run(argv, out / "compile.log", cwd=out, timeout=120)
    compile_code = code
    if code == 0:
        code, _ = tools.run(["vvp", str(program)], out / "simulation.log", cwd=out, timeout=300)
    log = out / "simulation.log"
    # Never accept an old success log after a new compilation failure.
    text = log.read_text() if compile_code == 0 and log.is_file() else ""
    result = {
        "status": "pass" if simulation_passed(code, text, spec["pass_marker"]) else "fail",
        "compile_exit_code": compile_code,
        "simulation_exit_code": code if compile_code == 0 else None,
        "pass_marker": spec["pass_marker"],
        "inputs": provenance.hash_inputs([tb, *sources] + ([lib] if lib else [])),
        "scope": "zero-delay functional GLS from exact Liberty" if lib else "original tutorial RTL testbench",
        "iverilog": tools.version(["iverilog", "-V"]),
    }
    provenance.write_json(out / "simulation.json", result)
    return result


def discover_design(d, src, dest, full):
    """Write equivalent AIG variants and check each design's cut truth tables."""
    name = d.name
    rows = []
    dest.mkdir(parents=True, exist_ok=True)
    synth = dest / "synth.aig"
    restr = dest / "restructured.aig"
    evaluate.command(
        f"read_verilog {'-sv ' if d.sv else ''}{evaluate.quote(src)}\nsynth -flatten -top {d.top}\n"
        f"async2sync\ndffunmap\naigmap\nwrite_aiger -zinit {evaluate.quote(synth)}",
        dest / "synth.log",
    )
    code, _ = tools.run(
        tools.abc_cmd() + ["-c", f"read {synth}; strash; dch -f; strash; write_aiger {restr}"],
        dest / "restructured.log",
        cwd=paths.ROOT,
    )
    if code or not restr.is_file() or not aig.cec(synth, restr, dest / "cec.log"):
        raise RuntimeError(f"{name}: AIG restructuring or equivalence check failed")
    for variant in ["synth", "restructured"]:
        s = cutflow.process(
            dest / f"{variant}.aig",
            dest / "cuts",
            full / (variant + ".jsonl.gz"),
            variant,
        )
        if s["run"]["status"] != "pass":
            raise RuntimeError(f"{name}: cut check failed")
        rows.append(
            {
                "design": name,
                "variant": variant,
                "ands": s["header"]["A"],
                "cuts": s["cuts_total"],
                "checked": s["cuts_checked"],
                "failures": len(s["failures"]),
                "pn_classes": s["pn_classes"],
                "npn_classes": s["npn_classes"],
            }
        )
    return rows


def discovery(names, out):
    rows = []
    for name in names:
        if name in SPECS:
            design, source = resolve(name)
            rows.extend(
                discover_design(
                    design, source, out / "tutorial_discovery" / name, paths.build("tutorial_cuts", name)
                )
            )
            print("Tutorial AIGs/cuts:", name, "pass", flush=True)
    return rows


def verify(names, out, extended_lib):
    results = {}
    for name in SPECS:
        if name not in names:
            continue
        d, src = resolve(name)
        rtl = simulate(name, [src], out / "tutorial_simulations" / name / "rtl")
        gates = {}
        for kind, lib in [("baseline", paths.given() / "hd_reduced.lib"), ("extended", extended_lib)]:
            for script in mapping.SCRIPTS:
                mapped = out / "mapping" / name / kind / script / "mapped.v"
                gates[f"{kind}_{script}"] = simulate(
                    name, [mapped], out / "tutorial_simulations" / name / kind / script, lib
                )
        results[name] = {
            "rtl_supplied": True,
            "rtl_simulation": rtl,
            "gate_simulations": gates,
            "mapping_and_gate_simulation_verified": rtl["status"] == "pass"
            and all(r["status"] == "pass" for r in gates.values()),
        }
        print(
            "Tutorial RTL + four gate simulations:",
            name,
            "pass" if results[name]["mapping_and_gate_simulation_verified"] else "FAIL",
            flush=True,
        )
    provenance.write_json(out / "tutorial_simulations.json", results)
    return results
