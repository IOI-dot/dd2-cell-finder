"""Typed tools: each wraps one dd2 CLI step and writes only under runs/<run_id>/."""
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dd2 import designs, paths

from . import policy

DESIGNS = [d.name for d in designs.required()]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict
    argv: Callable          # (args, run_dir) -> dd2 CLI arguments
    output: Callable        # (args, run_dir) -> the path the tool writes (its result)


def _obj(props: dict, required=()):
    return {"type": "object", "properties": props, "required": list(required),
            "additionalProperties": False}


DESIGN = {"design": {"type": "string", "enum": DESIGNS}}

TOOLS = {t.name: t for t in [
    Tool("run_baseline", "Map one required design with both ABC scripts on the reduced and usable "
         "libraries (handout section 2).", _obj(DESIGN, ["design"]),
         lambda a, d: ["baseline", "--designs", a["design"], "--out", d / "baseline"],
         lambda a, d: d / "baseline" / "table1.csv"),
    Tool("extract_aig", "Write the synth and restructured AIGs of one required design.",
         _obj(DESIGN, ["design"]),
         lambda a, d: ["aig", "--designs", a["design"], "--out", d / "aigs", "--scratch", d / "scratch"],
         lambda a, d: d / "aigs" / "manifest.json"),
    Tool("enumerate_cuts", "Enumerate and exhaustively check the 4-input cuts of one design's AIGs "
         "(run extract_aig first).", _obj(DESIGN, ["design"]),
         lambda a, d: ["cuts", "--designs", a["design"], "--aigs", d / "aigs", "--out", d / "cuts",
                       "--full", d / "cuts_full"],
         lambda a, d: d / "cuts" / "summary.csv"),
    Tool("classify", "Redundancy class of one function against the full HD library.",
         _obj({"tt": {"type": "string", "pattern": "^0x[0-9A-Fa-f]{1,4}$"},
               "arity": {"type": "integer", "enum": [1, 2, 3, 4]}}, ["tt", "arity"]),
         lambda a, d: ["classify", "--tt", a["tt"], "--arity", str(a["arity"])],
         lambda a, d: d / f"classify_{a['tt']}_{a['arity']}.json"),
    Tool("redundancy_selftest", "Run the redundancy checker's Table 4 self-test.", _obj({}),
         lambda a, d: ["selftest", "--out", d / "redundancy"],
         lambda a, d: d / "redundancy" / "self_test.json"),
]}


def execute(tool: Tool, args: dict, run_dir: Path, timeout: float = 1800) -> tuple:
    """Run a validated, authorised tool call. Returns (exit_code, result_path)."""
    out = tool.output(args, run_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"PYTHONPATH": str(paths.ROOT / "src")}
    p = subprocess.run([sys.executable, "-m", "dd2", *map(str, tool.argv(args, run_dir))],
                       capture_output=True, text=True, cwd=paths.ROOT, env=env, timeout=timeout)
    log = Path(str(out) + ".log")
    log.write_text(p.stdout + p.stderr)
    if tool.name == "classify" and p.returncode == 0:
        out.write_text(p.stdout)
    return p.returncode, out


def call(name: str, args: dict, run_id: str, log, agent: str = "fixed") -> tuple:
    """The only entry point an agent gets: validate, authorise, run, verify, log."""
    tool = TOOLS.get(name)
    if tool is None:
        log.policy(agent, name, args, "refused: unknown tool")
        return None, None
    errs = policy.validate_args(tool.schema, args)
    if errs:
        log.policy(agent, name, args, "refused: invalid arguments: " + "; ".join(errs))
        return None, None
    d = policy.run_dir(run_id)
    if not policy.may_write(tool.output(args, d), run_id):
        log.policy(agent, name, args, "refused: write outside runs/<run_id>/")
        return None, None
    before = policy.protected_digest()
    code, out = execute(tool, args, d)
    if policy.protected_digest() != before:
        log.policy(agent, name, args, "violation: protected files changed during the call")
        return 1, out
    log.tool(agent, name, args, out, exit_code=code)
    return code, out
