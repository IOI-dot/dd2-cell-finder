import json

import pytest

from dd2 import interface
from dd2.paths import ROOT

IF = ROOT / "docs" / "interface"


def load(name):
    return json.loads((IF / name).read_text())


def test_examples_are_the_template_bytes():
    tpl = ROOT.parent / "DD2_Project1_student_pack" / "repo_template" / "docs" / "interface"
    if tpl.exists():
        for f in ("request_example.json", "response_example.json"):
            assert (IF / f).read_bytes() == (tpl / f).read_bytes()


def test_examples_validate():
    assert interface.validate_request(load("request_example.json")) == []
    assert interface.validate_response(load("response_example.json")) == []


@pytest.mark.parametrize("change, fragment", [
    ({"truth_table": "0x077E"}, "does not match"),
    ({"inputs": ["A", "B", "C", "D", "E"]}, "maxItems"),
    ({"sizing": "big"}, "sizing"),
    ({"name": "sky130_fd_sc_hd__x"}, "name"),
    ({"extra": 1}, "unexpected"),
    ({"expression": "!(A & E)"}, "unknown name"),
])
def test_bad_requests_rejected(change, fragment):
    errs = interface.validate_request(load("request_example.json") | change)
    assert errs and any(fragment in e for e in errs), errs


def test_response_status_rules():
    r = load("response_example.json") | {"status": "maybe"}
    assert interface.validate_response(r)
    assert not interface.usable(load("response_example.json") | {"status": "fail", "reason": "drc"})
    assert interface.usable(load("response_example.json"))


def test_hex_case_and_padding_are_values_not_text():
    r = load("request_example.json")
    assert interface.validate_request(r | {"truth_table": "0x77f"}) == []
    assert interface.validate_request(r | {"truth_table": "0x077f"}) == []


def test_reserved_pin_names_refused():
    r = load("request_example.json") | {"inputs": ["A", "B", "C", "VPWR"],
                                         "expression": "!((C & VPWR) | (A & B & (C | VPWR)))"}
    assert any("reserved" in e for e in interface.validate_request(r))
