"""Option 1's answer to an Option 2 request (Appendix A): pass only with every check and a Liberty file."""
from cellgen import flow
from dd2 import interface

REQ = {"request_id": "M2-001", "name": "dd2_g4__n3_2b_1", "inputs": ["A", "B", "C"], "output": "Y",
       "expression": "!((!A&B)|(C&(!A|B)))", "truth_table": "0x2B", "sizing": "hd", "estimated_area_um2": 6.3}


def report(status="pass", failed=(), stages=2):
    return {"cell": REQ["name"], "status": status, "failed_checks": list(failed),
            "layout": {"width_sites": 7, "width_um": 3.22},
            "checks": {"network": {"transistors": 10, "stages": stages}, "drc": {"errors": 0}, "lvs": {"result": "match"},
                       "rc_lvs": {"result": "match"}, "spice": {"status": "pass"}, "model": {"status": "pass"},
                       "abutment": {"errors": 0}, "layers": {"status": "pass"}}}


def test_a_passing_cell_with_its_liberty_is_a_pass():
    r = flow.response(REQ, report(), liberty=True)
    assert r["status"] == "pass" and r["reason"] is None
    assert r["stages"] == 2 and r["checks"]["rc_lvs"] == "match"
    assert r["area_um2"] == round(3.22 * 2.72, 4)
    assert interface.validate_response(r) == []


def test_without_a_liberty_a_passing_cell_is_still_a_fail():
    r = flow.response(REQ, report(), liberty=False)
    assert r["status"] == "fail" and "Liberty" in r["reason"]


def test_a_failed_check_is_a_fail_that_names_it():
    r = flow.response(REQ, report("fail", ["lvs", "spice"]), liberty=True)
    assert r["status"] == "fail" and "lvs" in r["reason"] and "spice" in r["reason"]
    assert interface.validate_response(r) == []
