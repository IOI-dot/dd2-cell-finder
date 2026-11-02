"""Typed tools: each wraps one dd2 CLI step and writes only under runs/<run_id>/."""
import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
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
    argv: Callable          # (args, run_dir) -> CLI arguments of `python -m <module>`
    output: Callable        # (args, run_dir) -> the path the tool writes (its result)
    module: str = "dd2"     # dd2 (Option 2 core) or cellgen (Option 1)


def _obj(props: dict, required=()):
    return {"type": "object", "properties": props, "required": list(required),
            "additionalProperties": False}


EXPR = r"^[A-Za-z0-9_!&|^() ]{1,80}$"
NAME = r"^[A-Za-z][A-Za-z0-9_]{0,40}$"
NET = r"^[A-Za-z_][A-Za-z0-9_]{0,20}$"
DESIGN = {"design": {"type": "string", "enum": DESIGNS}}

TOOLS = {t.name: t for t in [
    Tool("run_baseline", "Map one required design with both ABC scripts on the reduced and usable "
         "libraries (handout section 2).", _obj(DESIGN, ["design"]),
         lambda a, d: ["baseline", "--designs", a["design"], "--out", d],
         lambda a, d: d / "table1.csv"),
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
    Tool("build_reference_cell", "Regenerate an installed HD cell (Option 1) and run every cp1 check "
         "and the comparison with the installed cell.",
         _obj({"cell": {"type": "string", "enum": ["inv_1", "nand2_1", "nor2_1", "nand3_1", "a21oi_1", "o21ai_1",
                                                   "a21o_1", "mux2_1"]}}, ["cell"]),
         lambda a, d: ["ref", "--cell", a["cell"], "--out", d / "cells", "--work", d / "work"],
         lambda a, d: d / "cells" / f"dd2_ref__{a['cell']}" / "report.json", module="cellgen"),
    Tool("build_cell", "Generate one cell from its function and run every check (handout steps 2 to 7). "
         "The arguments are the generator's choices; the result is the check report.",
         _obj({"expr": {"type": "string", "pattern": EXPR}, "name": {"type": "string", "pattern": NAME},
               "sizing": {"type": "string", "enum": ["hd", "stack"]},
               "order_index": {"type": "integer"}, "priority": {"type": "string", "pattern": NET},
               "no_met1": {"type": "boolean"}}, ["expr", "name", "sizing"]),
         lambda a, d: ["build", "--expr", a["expr"], "--name", a["name"], "--sizing", a["sizing"],
                       *(["--order-index", str(a["order_index"])] if "order_index" in a else []),
                       *(["--priority", a["priority"]] if a.get("priority") else []),
                       *(["--no-met1"] if a.get("no_met1") else []),
                       "--out", d / "cells", "--work", d / "work"],
         lambda a, d: d / "cells" / a["name"] / "report.json", module="cellgen"),
    Tool("redundancy_selftest", "Run the redundancy checker's Table 4 self-test.", _obj({}),
         lambda a, d: ["selftest", "--out", d / "redundancy"],
         lambda a, d: d / "redundancy" / "self_test.json"),
]}


def stop_containers(run_id: str) -> None:
    """Killing `docker run` leaves its container running: find a run's containers by label."""
    ids = subprocess.run(["docker", "ps", "-q", "--filter", f"label=dd2.run={run_id}"], capture_output=True, text=True).stdout.split()
    if ids:
        subprocess.run(["docker", "kill", *ids], capture_output=True)


def execute(tool: Tool, args: dict, run_dir: Path, timeout: float = 1800, on_trace=None, cancel=None) -> tuple:
    """Run a validated, authorised tool call: (exit code, result path). Exit 130 means it was
    cancelled and 124 that it timed out. on_trace gets each progress line of the tool as it happens."""
    out = tool.output(args, run_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"PYTHONPATH": str(paths.ROOT / "src"), "DD2_TRACE": "1", "DD2_RUN": run_dir.name}
    argv = [paths.rel(a) if isinstance(a, Path) else str(a) for a in tool.argv(args, run_dir)]
    log = Path(str(out) + ".log")
    p = subprocess.Popen([sys.executable, "-m", tool.module, *argv], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         cwd=paths.ROOT, env=env, start_new_session=True)
    lines, fresh = [], deque()

    def read():
        for line in p.stdout:
            (fresh if line.startswith("@@ ") else lines).append(line)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline, code = time.time() + timeout, None
    while code is None:
        reader.join(0.2)
        while fresh and on_trace:
            on_trace(json.loads(fresh.popleft()[3:]))
        if not reader.is_alive():
            code = p.wait()
        elif (cancel and cancel.is_set()) or time.time() > deadline:
            code = 130 if cancel and cancel.is_set() else 124
            with contextlib.suppress(ProcessLookupError):
                os.killpg(p.pid, signal.SIGKILL)
            stop_containers(run_dir.name)
    log.write_text("".join(lines) + ({130: "\ncancelled\n", 124: f"\ntimeout after {timeout} s\n"}.get(code, "")))
    if tool.name == "classify" and code == 0:
        out.write_text("".join(lines))
    return code, out


def call(name: str, args: dict, run_id: str, log, agent: str = "fixed", timeout: float = 1800, on_trace=None, cancel=None) -> tuple:
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
    targets = [tool.output(args, d)] + [a for a in tool.argv(args, d) if isinstance(a, Path)]
    if not all(policy.may_write(t, run_id) for t in targets):
        log.policy(agent, name, args, "refused: write outside runs/<run_id>/")
        return None, None
    before = policy.protected_digest()
    code, out = execute(tool, args, d, timeout, on_trace, cancel)
    if policy.protected_digest() != before:
        log.policy(agent, name, args, "violation: protected files changed during the call")
        return 1, out
    log.tool(agent, name, args, out, exit_code=code)
    return code, out
