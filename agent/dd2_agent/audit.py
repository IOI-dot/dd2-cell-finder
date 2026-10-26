"""Run logs in the format of overview Appendix B: one JSON line per model, tool or policy event,
and a last line with the verdict and the check file it rests on."""
import json
import re
from datetime import date
from pathlib import Path

from dd2 import paths

LOG_DIR = paths.ROOT / "ai" / "runs"


def new_run_id(log_dir: Path = LOG_DIR) -> str:
    stem = f"A-{date.today():%m%d}"
    used = [int(m.group(1)) for p in Path(log_dir).glob(f"{stem}-*.jsonl")
            if (m := re.search(r"-(\d+)\.jsonl$", p.name))]
    return f"{stem}-{max(used, default=0) + 1:02d}"


class RunLog:
    def __init__(self, run_id: str, log_dir: Path = LOG_DIR):
        self.run, self.step = run_id, 0
        self.path = Path(log_dir) / f"{run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, entry: dict) -> dict:
        self.step += 1
        entry = {"run": self.run, "step": self.step} | entry
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, sort_keys=False) + "\n")
        return entry

    def tool(self, agent, tool, args, result, **extra):
        return self._write({"agent": agent, "kind": "tool", "tool": tool, "args": args,
                            "result": paths.rel(Path(result)) if result else None} | extra)

    def model(self, agent, model, prompt, tokens_in, tokens_out, decision):
        return self._write({"agent": agent, "kind": "model", "model": model, "prompt": prompt,
                            "tokens_in": tokens_in, "tokens_out": tokens_out, "decision": decision})

    def policy(self, agent, tool, args, reason):
        return self._write({"agent": agent, "kind": "policy", "tool": tool, "args": args,
                            "decision": reason})

    def result(self, status: str, checks: Path):
        return self._write({"kind": "result", "status": status, "checks": paths.rel(Path(checks))})


def verify(path: Path) -> list:
    """Problems with a run log; a pass without its check file counts as a failure."""
    lines = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    errs = []
    if not lines:
        return ["empty log"]
    if [l["step"] for l in lines] != list(range(1, len(lines) + 1)):
        errs.append("steps are not consecutive")
    last = lines[-1]
    if last.get("kind") != "result":
        errs.append("last line is not a result")
    elif last["status"] == "pass":
        chk = Path(last["checks"])
        if not (chk if chk.is_absolute() else paths.ROOT / chk).is_file():
            errs.append(f"pass without its check file {last['checks']}")
    return errs
