"""Deterministic guard rails: argument validation, write authorisation and a digest of the
protected checks. The model never decides any of these (overview 4.3, rule 4)."""
import hashlib
import re
from pathlib import Path

from dd2 import interface, paths

ROOT = paths.ROOT
RUNS = ROOT / "runs"
# Check scripts, broken cases, the flow's own code and the supplied inputs. Hashed before and
# after every tool call; any change fails the run.
PROTECTED_TREES = [ROOT / "tests", ROOT / "src", ROOT / "agent", ROOT / "Makefile",
                   ROOT / "given" / "hd_reduced.lib", ROOT / "given" / "hd_usable.lib",
                   ROOT / "given" / "designs", ROOT / "given" / "scripts", ROOT / "given" / "plan_hd.json",
                   ROOT / "pdk" / paths.FULL_HD_LIB,
                   ROOT / "pdk" / "libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds",
                   ROOT / "pdk" / "libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice",
                   ROOT / "pdk" / "libs.tech/magic/sky130A.magicrc",
                   ROOT / "pdk" / "libs.tech/netgen/sky130A_setup.tcl",
                   ROOT / ".specify" / "memory" / "constitution.md"]
RUN_ID = re.compile(r"^A-\d{4}-\d{2,4}$")


def validate_args(schema: dict, args) -> list:
    return interface.check_schema(args, schema, "args")


def run_dir(run_id: str) -> Path:
    return RUNS / run_id


def may_write(path: Path, run_id: str) -> bool:
    """Only paths that resolve inside runs/<run_id>/ may be written, for a well-formed run_id.
    This is a guard before each call; the digest check after it detects anything that slipped
    through. Real prevention (read-only mounts) comes with docker/compose.yml."""
    if not RUN_ID.fullmatch(run_id or ""):
        return False
    d = run_dir(run_id)
    p = Path(path) if Path(path).is_absolute() else ROOT / path
    # No symlink anywhere from runs/ down to the target may redirect the write.
    if d.is_symlink() or RUNS.is_symlink():
        return False
    probe = p
    while probe != d and probe.is_relative_to(d):
        if probe.is_symlink():
            return False
        probe = probe.parent
    return p.resolve().is_relative_to(d.resolve()) and d.resolve().parent == RUNS.resolve()


def protected_digest() -> str:
    h = hashlib.sha256()
    for root in PROTECTED_TREES:
        files = sorted(p for p in Path(root).rglob("*") if p.is_file()) if Path(root).is_dir() \
            else [Path(root)] if Path(root).is_file() else []
        for f in files:
            if "__pycache__" in f.parts:
                continue
            h.update(str(f.relative_to(ROOT) if f.is_relative_to(ROOT) else f).encode())
            h.update(f.read_bytes())
    return h.hexdigest()
