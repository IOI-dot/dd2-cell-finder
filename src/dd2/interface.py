"""Appendix A request/response validation (standard library only).

Implements the subset of JSON Schema used by docs/interface/*.schema.json, plus the rules a
schema cannot state: the expression and the truth table must agree, and only a response with
status "pass" may be used in a mapping.
"""
import json
import re

from . import boolfn as bf
from .paths import ROOT

SCHEMAS = ROOT / "docs" / "interface"


def _schema(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text())


def _check(value, schema, where, errs):
    t = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
             "null": type(None)}
    if t:
        allowed = t if isinstance(t, list) else [t]
        if not any(isinstance(value, types[a]) and not (a in ("integer", "number") and isinstance(value, bool))
                   for a in allowed):
            errs.append(f"{where}: expected {t}")
            return
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{where}: {value!r} not in {schema['enum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append(f"{where}: {value!r} does not match {schema['pattern']}")
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1 << 30):
            errs.append(f"{where}: length out of range")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{where}: below minimum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errs.append(f"{where}: must be > {schema['exclusiveMinimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errs.append(f"{where}: fewer than minItems {schema['minItems']}")
        if len(value) > schema.get("maxItems", 1 << 30):
            errs.append(f"{where}: more than maxItems {schema['maxItems']}")
        if schema.get("uniqueItems") and len(set(map(json.dumps, value))) != len(value):
            errs.append(f"{where}: items not unique")
        for i, v in enumerate(value):
            _check(v, schema.get("items", {}), f"{where}[{i}]", errs)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{where}.{k}: missing")
        for k, v in value.items():
            if k in props:
                _check(v, props[k], f"{where}.{k}", errs)
            elif schema.get("additionalProperties") is False:
                errs.append(f"{where}.{k}: unexpected field")


def check_schema(value, schema: dict, where: str = "args") -> list:
    """Errors of value against a JSON-Schema subset (type, enum, pattern, ranges, items,
    required, additionalProperties). Empty list means valid."""
    errs = []
    _check(value, schema, where, errs)
    return errs


def validate_request(req: dict) -> list:
    errs = []
    _check(req, _schema("request"), "request", errs)
    if errs:
        return errs
    try:
        tt = bf.eval_expr(req["expression"], req["inputs"])
    except ValueError as e:
        return [f"request.expression: {e}"]
    want = bf.to_hex(tt, len(req["inputs"]))
    if req["truth_table"] != want:
        errs.append(f"request.truth_table {req['truth_table']} does not match expression ({want})")
    return errs


def validate_response(resp: dict) -> list:
    errs = []
    _check(resp, _schema("response"), "response", errs)
    if not errs and resp["status"] != "pass" and not resp["reason"]:
        errs.append("response.reason: required when status is not pass")
    return errs


def usable(resp: dict) -> bool:
    """A cell may enter a mapping library only if its response is valid and passed every check."""
    return not validate_response(resp) and resp["status"] == "pass"
