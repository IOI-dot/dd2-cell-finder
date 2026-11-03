"""How long each stage took in past runs, so that the studio can say what to expect.

An estimate is only ever the median of recorded runs: with no history there is no estimate. Runs are
grouped because a multi-stage cell's search takes far longer than a single-stage cell's.
"""
import json
import statistics
from pathlib import Path

KEEP = 20                                # the most recent runs that count
MERGE = {"rc_lvs": "rc", "interpreter": "model", "diagnostician": "model", "explainer": "report"}
PER_CALL = {"model", "report"}           # these happen several times a run, so each call is timed alone


class Spans:
    """First and last sighting of each stage in the first build, or of each model call."""

    def __init__(self):
        self.times = {}

    def seen(self, stage: str, revision: str, step: str, t: float) -> None:
        name = MERGE.get(stage, stage)
        if not name or revision not in ("", "r0"):
            return
        key = (name, step if name in PER_CALL else "")
        a, b = self.times.get(key, (t, t))
        self.times[key] = (min(a, t), max(b, t))

    def seconds(self) -> dict:
        out = {}
        for (name, _), (a, b) in self.times.items():
            out[name] = max(out.get(name, 0), round(b - a, 2))
        return out


def record(path: Path, group: str, seconds: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"group": group, "seconds": seconds}) + "\n")


def estimates(path: Path) -> dict:
    """{group: {stage: {seconds, runs}}}, the median of the last KEEP runs of each."""
    if not Path(path).is_file():
        return {}
    seen = {}
    for line in Path(path).read_text().splitlines():
        row = json.loads(line)
        for stage, s in row["seconds"].items():
            seen.setdefault(row["group"], {}).setdefault(stage, []).append(s)
    return {g: {k: {"seconds": round(statistics.median(v[-KEEP:]), 2), "runs": len(v[-KEEP:])} for k, v in stages.items()} for g, stages in seen.items()}
