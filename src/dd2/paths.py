"""Repository paths. Inputs are reached through the pdk/ and given/ links made by make setup."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FULL_HD_LIB = "libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"


def given(base: Path | None = None) -> Path:
    return Path(base) if base else ROOT / "given"


def pdk(base: Path | None = None) -> Path:
    return Path(base) if base else ROOT / "pdk"


def full_hd_lib(pdk_dir: Path | None = None) -> Path:
    return pdk(pdk_dir) / FULL_HD_LIB


def results(*parts: str) -> Path:
    return ROOT.joinpath("results", *parts)


def build(*parts: str) -> Path:
    return ROOT.joinpath("build", *parts)


def rel(p: Path) -> str:
    """Repository-relative path for records; absolute if outside the repository."""
    p = Path(p).absolute()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
