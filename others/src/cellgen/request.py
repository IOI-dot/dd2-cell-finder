"""Read an Appendix A cell request; refuse it unless expression and truth table agree."""
import json
from dataclasses import dataclass, field
from pathlib import Path

from dd2 import boolfn as bf
from dd2 import interface


@dataclass
class Request:
    status: str                      # ok | fail | unsupported
    reason: str | None
    inputs: list = field(default_factory=list)
    output: str = "Y"
    tt: int = 0
    data: dict = field(default_factory=dict)


def parse(data: dict) -> Request:
    inputs = data.get("inputs") or []
    if isinstance(data.get("output"), list) and len(data["output"]) != 1:
        return Request("unsupported", f"{len(data['output'])} outputs: the generator builds cells with "
                       "one output", inputs, data=data)
    if len(inputs) > 4:
        return Request("unsupported", f"{len(inputs)} inputs: the generator takes at most 4 inputs",
                       inputs, data=data)
    errs = interface.validate_request(data)
    if errs:
        return Request("fail", "; ".join(errs), inputs, data=data)
    tt = bf.eval_expr(data["expression"], inputs)
    return Request("ok", None, list(inputs), data["output"], tt, data)


def read(path: Path) -> Request:
    return parse(json.loads(Path(path).read_text()))
