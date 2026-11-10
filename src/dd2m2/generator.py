"""Consume Appendix A responses from the course generator."""

import json
import math
import re
from pathlib import Path

from dd2 import boolfn, interface, liberty, provenance

TEMPLATE = re.compile(r'\blu_table_template\s*\(\s*"?([\w$]+)"?\s*\)\s*\{')
TABLES = ("cell_rise", "cell_fall", "rise_transition", "fall_transition")
EXPECTED_CHECKS = {
    "drc": 0, "lvs": "match", "rc_lvs": "match", "truth_table": "pass", "abutment": 0, "layers": "pass",
}


def _response_files(directory):
    responses = {}
    for path in sorted(directory.rglob("*.json")):
        if path.name.startswith("."):
            continue
        data = json.loads(path.read_text())
        for entry in data if isinstance(data, list) else [data]:
            if not isinstance(entry, dict) or not {"request_id", "status", "cell"} <= entry.keys():
                continue
            key = entry["request_id"]
            if key in responses:
                raise ValueError(f"duplicate generator response for {key}")
            responses[key] = entry, path
    return responses


def _liberty_path(root, response_path, value):
    relative = Path(value)
    candidates = {p.resolve() for p in (root / relative, response_path.parent / relative) if p.is_file()}
    if len(candidates) != 1:
        raise ValueError(f"{response_path}: missing or ambiguous Liberty path {value}")
    path = candidates.pop()
    if not path.is_relative_to(root):
        raise ValueError(f"{response_path}: Liberty must be inside the response directory")
    return path


def merge_responses(base, out, requests, directory):
    """Validate and append the requested passing cell groups with their timing templates."""
    directory = Path(directory).resolve()
    if requests and not directory.is_dir():
        raise ValueError(f"course generator response directory is missing: {directory}")
    responses = _response_files(directory) if requests else {}
    source = base.read_text()
    base_clean = liberty._strip_comments(source)
    names = liberty.cell_names(base)
    templates = dict(liberty._groups(base_clean, TEMPLATE))
    groups, records = [], []
    for req in requests:
        errors = interface.validate_request(req)
        if errors:
            raise ValueError(f"invalid request: {errors}")
        name = req["name"]
        if name in names:
            raise ValueError(f"duplicate or baseline cell name: {name}")
        names.add(name)
        response = responses.get(req["request_id"])
        if response is None:
            raise ValueError(f"missing course generator response for {req['request_id']} ({name})")
        data, response_path = response
        errors = interface.validate_response(data)
        if errors:
            raise ValueError(f"{response_path}: {errors}")
        if data["cell"] != name or data["status"] != "pass" or data["checks"] != EXPECTED_CHECKS:
            raise ValueError(f"{name}: generator did not return a passing matching cell ({data['reason']})")
        lib = _liberty_path(directory, response_path, data["files"]["liberty"])
        text = liberty._strip_comments(lib.read_text())
        cells = liberty.read_cells(lib)
        if len(cells) != 1 or liberty.cell_names(lib) != {name}:
            raise ValueError(f"{lib}: expected exactly one Liberty cell named {name}")
        cell = cells[0]
        if (
            set(cell.inputs) != set(req["inputs"])
            or cell.output != req["output"]
            or boolfn.eval_expr(cell.function, req["inputs"]) != int(req["truth_table"], 16)
        ):
            raise ValueError(f"{lib}: requested pins or truth table do not match")
        if not math.isfinite(cell.area) or cell.area <= 0 or not math.isclose(
            cell.area, data["area_um2"], abs_tol=1e-6
        ):
            raise ValueError(f"{lib}: area disagrees with the generator response")
        body = next(liberty._groups(text, liberty._CELL))[1]
        for field in TABLES:
            if not re.search(rf'\b{field}\s*\(\s*"?(?!scalar\b)[\w$]+"?\s*\)', body):
                raise ValueError(f"{lib}: missing characterized {field} table")
        for template, definition in liberty._groups(text, TEMPLATE):
            if template not in templates:
                templates[template] = definition
                groups.append(f'lu_table_template ("{template}") {{{definition}}}')
            elif re.sub(r"\s+", "", templates[template]) != re.sub(r"\s+", "", definition):
                raise ValueError(f"{lib}: conflicting timing template {template}")
        groups.append(f'cell ("{name}") {{{body}}}')
        records.append(req | {
            "real_area_um2": cell.area, "response_sha256": provenance.sha256(response_path),
            "liberty_sha256": provenance.sha256(lib), "generator_version": data["tool_version"],
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    end = source.rindex("}")
    out.write_text(source[:end] + "\n".join(groups) + "\n" + source[end:] if groups else source)
    return records


def scale_cell_area(source, out, name):
    text = source.read_text()
    head = re.search(r'\bcell\s*\(\s*"?' + re.escape(name) + r'"?\s*\)\s*\{', text)
    if not head:
        raise ValueError(f"missing cell {name}")
    area = re.match(r'\s*area\s*:\s*([\d.eE+-]+)\s*;', text[head.end():])
    if not area:
        raise ValueError(f"{name}: missing area at start of cell")
    start, end = area.span(1)
    original = float(area.group(1))
    scaled = original * 0.7
    out.write_text(text[:head.end() + start] + f"{scaled:.9f}" + text[head.end() + end:])
    return original, scaled
