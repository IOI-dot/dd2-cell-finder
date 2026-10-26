"""External tool runner with logs and timeouts, and version probes."""
import os
import subprocess
import time
from pathlib import Path

TIMEOUT_EXIT = 124


def run(argv, log: Path, timeout: float | None = 3600, cwd: Path | None = None, env=None):
    """Run argv, write stdout+stderr to log, return (exit_code, seconds). 124 means timeout."""
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with open(log, "w") as out:
        out.write("$ " + " ".join(map(str, argv)) + "\n")
        out.flush()
        try:
            p = subprocess.run(list(map(str, argv)), stdout=out, stderr=subprocess.STDOUT,
                               cwd=cwd, timeout=timeout, env=env)
            code = p.returncode
        except subprocess.TimeoutExpired:
            out.write(f"\n[dd2] timeout after {timeout} s\n")
            code = TIMEOUT_EXIT
        except FileNotFoundError as e:
            out.write(f"\n[dd2] tool not found: {e}\n")
            code = 127
    return code, round(time.monotonic() - t0, 3)


def version(argv) -> str | None:
    """First non-empty output line of a version command, or None if the tool is missing."""
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    text = (p.stdout or "") + (p.stderr or "")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return lines[0] if lines else None


def yosys_cmd() -> list:
    """The Yosys used by the flow: $DD2_YOSYS (space-separated) or yosys on PATH."""
    return os.environ.get("DD2_YOSYS", "yosys").split()


def abc_cmd() -> list:
    return os.environ.get("DD2_ABC", "yosys-abc").split()


def versions() -> dict:
    import sys
    return {
        "python": sys.version.split()[0],
        "yosys": version(yosys_cmd() + ["-V"]),
        "yosys-abc": version(abc_cmd() + ["-h"]) and "present (bundled with yosys)",
        "iverilog": version(["iverilog", "-V"]),
        "sta": version(["sta", "-version"]),
    }
