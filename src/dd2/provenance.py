"""Provenance records: every result file carries the command, inputs, versions and verdict."""
import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import paths


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_inputs(files) -> dict:
    return {paths.rel(Path(f)): sha256(Path(f)) for f in files}


@dataclass
class RunRecord:
    argv: list
    inputs: dict = field(default_factory=dict)
    tools: dict = field(default_factory=dict)
    started: str = field(default_factory=now)
    finished: str = ""
    exit_code: int | None = None
    status: str = "error"
    logs: list = field(default_factory=list)
    host: str = field(default_factory=lambda: f"{platform.system()} {platform.machine()}")

    def finish(self, exit_code: int, logs=(), status: str | None = None):
        self.exit_code = exit_code
        self.finished = now()
        self.logs = [paths.rel(Path(p)) for p in logs]
        self.status = status or ("pass" if exit_code == 0 else "fail")
        return self

    def asdict(self) -> dict:
        return asdict(self)


def write_json(path: Path, data) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path
