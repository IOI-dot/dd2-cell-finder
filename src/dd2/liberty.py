"""Minimal Liberty reader: single-output combinational cells and their output function.

Only the pin-level `function` attribute is read; `power_down_function` is ignored. A cell is kept
when it has exactly one output pin with a function, at least one input, and no ff, latch,
statetable or three_state. A function that does not parse raises ValueError naming the cell.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from . import boolfn as bf

# Attributes may follow a newline, "{" or ";" (one-line groups are legal Liberty).
_B = r'(?:^|(?<=[\s{;]))'
_CELL = re.compile(_B + r'cell\s*\(\s*"?([\w$]+)"?\s*\)\s*\{', re.M)
_PIN = re.compile(_B + r'pin\s*\(\s*"?([\w\[\]]+)"?\s*\)\s*\{', re.M)
_FUNC = re.compile(_B + r'function\s*:\s*"([^"]*)"', re.M)
_AREA = re.compile(_B + r'area\s*:\s*"?([0-9.eE+-]+)"?', re.M)
_DIR = re.compile(r'direction\s*:\s*"?(\w+)')
_SEQ = re.compile(_B + r'(ff|latch|ff_bank|latch_bank|statetable)\s*\(', re.M)


@dataclass
class LibCell:
    name: str
    inputs: list
    output: str
    function: str
    tt: int
    area: float


def _groups(text: str, pattern):
    for m in pattern.finditer(text):
        depth, i = 1, m.end()
        while depth:
            ch = text[i]
            depth += (ch == "{") - (ch == "}")
            i += 1
        yield m.group(1), text[m.end():i - 1]


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def read_cells(path: Path) -> list:
    text = _strip_comments(Path(path).read_text())
    cells = []
    for name, body in _groups(text, _CELL):
        if _SEQ.search(body):
            continue
        pins = list(_groups(body, _PIN))
        ins = [p for p, b in pins if (_DIR.search(b) or [None, ""])[1] == "input"]
        outs = [(p, b) for p, b in pins if (_DIR.search(b) or [None, ""])[1] == "output"]
        if len(outs) != 1 or not ins or "three_state" in outs[0][1]:
            continue
        fm = _FUNC.search(outs[0][1])
        if not fm:
            continue
        try:
            tt = bf.eval_expr(fm.group(1), ins)
        except ValueError as e:
            raise ValueError(f"{path}: cell {name}: {e}") from None
        am = _AREA.search(body[:body.find("pin")] if "pin" in body else body)
        cells.append(LibCell(name, ins, outs[0][0], fm.group(1), tt, float(am.group(1)) if am else 0.0))
    return cells


def cell_names(path: Path) -> set:
    return {m.group(1) for m in _CELL.finditer(Path(path).read_text())}
