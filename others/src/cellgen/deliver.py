"""Option 1's side of Option 3: build the cells Option 2 requests, and answer each one.

For every Appendix A request: build and check the cell, then characterize a passing cell from its
RC-extracted netlist and write its Liberty file, and write the response. A cell that fails any check
gets no Liberty, so Option 2 can never map onto it.

    python -m cellgen.deliver results/m2/requests.json [--only NAME ...]
"""
import argparse
import json
import sys
from pathlib import Path

from dd2 import interface, paths, provenance

from . import characterize as ch
from . import flow, request

SPEC_CELL = "nand2_1"            # HD x1 cells share the 7 x 7 table template; take its index values


def characterizer_validated() -> bool:
    """Handout 5.1: no generated cell is characterized before the characterizer meets Table 5."""
    p = paths.results("option1", "m2", "table5.json")
    return p.is_file() and all(v in (True, "pass") for v in json.loads(p.read_text()).get("requirements", {}).values())


def deliver(req: dict, out_root: Path | None = None, work_root: Path | None = None) -> dict:
    q = request.parse(req)
    out = Path(out_root or paths.ROOT / "cells") / req["name"]
    if q.status != "ok":
        resp = {"request_id": req.get("request_id"), "status": q.status, "reason": q.reason, "cell": req.get("name"), "stages": 0,
                "transistors": 0, "width_sites": 0, "area_um2": 0, "files": {"gds": "", "liberty": "", "verilog": "", "report": ""},
                "checks": {"drc": 0, "lvs": "not run", "rc_lvs": "not run", "truth_table": "not run", "abutment": 0, "layers": "not run"},
                "ngspice_sha256": "", "tool_version": "cellgen"}
    else:
        # no request here: the response is written once, below, when the Liberty question is settled
        rep = flow.build(req["name"], q.inputs, q.tt, out_root=out_root, work_root=work_root)
        lib = None
        if rep["status"] == "pass" and characterizer_validated():
            work = Path(work_root or paths.build("cells")) / req["name"]
            engine = ch.Engine("fixed")
            t = ch.read_cell(SPEC_CELL)["tables"][0]
            r = ch.characterize(req["name"], work / f"{req['name']}_rc_sasb.spice", q.inputs, req["output"], q.tt,
                                {"index_1": t["index_1"], "index_2": t["index_2"]}, engine, work / "char", jobs=4)
            lib = out / "cell.lib"
            lib.write_text(ch.liberty_text(req["name"], q.inputs, req["output"], q.tt, rep["layout"]["width_um"] * 2.72,
                                           r["capacitance"], r["tables"], ch.read_setup(), engine.identity(work / "char")))
        resp = flow.response(req, rep, liberty=lib is not None)
    errs = interface.validate_response(resp)
    if errs:
        raise ValueError(f"{req.get('name')}: response breaks Appendix A: {errs}")
    out.mkdir(parents=True, exist_ok=True)
    provenance.write_json(out / "response.json", resp)
    return resp


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cellgen.deliver", description=__doc__.split("\n\n")[0])
    ap.add_argument("requests", type=Path, help="a JSON list of Appendix A requests, such as results/m2/requests.json")
    ap.add_argument("--only", nargs="*", default=None, help="build only these cell names")
    a = ap.parse_args(argv)
    reqs = [r for r in json.loads(a.requests.read_text()) if not a.only or r["name"] in a.only]
    for r in reqs:
        resp = deliver(r)
        print(json.dumps({"request_id": resp["request_id"], "cell": resp["cell"], "status": resp["status"],
                          "area_um2": resp["area_um2"], "reason": resp["reason"]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
