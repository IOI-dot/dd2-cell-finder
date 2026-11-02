"""cellgen command line: build a reference cell or a cell from an Appendix A request.
Exit code 0 when every check passes, 1 when a check fails, 2 for an unsupported or invalid input."""
import argparse
import json
import sys
from pathlib import Path

from dd2 import boolfn as bf

from . import flow, request


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cellgen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ref", help="regenerate an installed HD cell and compare with it")
    r.add_argument("--cell", required=True, choices=list(flow.SIX + flow.MULTI_STAGE))
    b = sub.add_parser("build", help="build a cell from an expression, with the generator's choices")
    b.add_argument("--expr", required=True)
    b.add_argument("--name", required=True)
    b.add_argument("--sizing", choices=["hd", "stack"], default="hd")
    b.add_argument("--order-index", type=int, default=None, help="keep this one ordering of the candidates")
    b.add_argument("--priority", default=None, help="route this net first")
    b.add_argument("--no-met1", action="store_true", help="stay on li1 even in a multi-stage cell")
    q = sub.add_parser("request", help="build the cell an Appendix A request asks for")
    q.add_argument("path", type=Path)
    for p in (r, q, b):
        p.add_argument("--out", type=Path, default=None, help="views folder root (default cells/)")
        p.add_argument("--work", type=Path, default=None, help="work folder root (default build/cells/)")
    a = ap.parse_args(argv)
    if a.cmd == "ref":
        rep = flow.build_reference(a.cell, out_root=a.out, work_root=a.work)
    elif a.cmd == "build":
        names = sorted({t for t in bf.tokenize(a.expr) if t[0].isalpha()})
        opts = {k: v for k, v in (("order_index", a.order_index), ("priority", a.priority)) if v is not None}
        if a.no_met1:
            opts["allow_met1"] = False
        rep = flow.build(a.name, names, bf.eval_expr(a.expr, names), sizing=a.sizing, layout_opts=opts,
                         out_root=a.out, work_root=a.work)
    else:
        req = request.read(a.path)
        if req.status != "ok":
            # Appendix A: a refused request still gets a response (fail or unsupported, with a reason)
            data = req.data
            name = data.get("name") or data.get("request_id") or "request"
            resp = {"request_id": data.get("request_id"), "status": req.status, "reason": req.reason,
                    "cell": data.get("name"), "stages": 0, "transistors": 0, "width_sites": 0, "area_um2": 0,
                    "files": {"gds": "", "liberty": "", "verilog": "", "report": ""},
                    "checks": {"drc": 0, "lvs": "not run", "rc_lvs": "not run", "truth_table": "not run",
                               "abutment": 0, "layers": "not run"}, "ngspice_sha256": "", "tool_version": "cellgen"}
            out = Path(a.out or flow.paths.ROOT / "cells") / name
            out.mkdir(parents=True, exist_ok=True)
            flow.provenance.write_json(out / "response.json", resp)
            print(json.dumps({"status": req.status, "reason": req.reason, "response": str(out / "response.json")}))
            return 2
        try:
            rep = flow.build(req.data["name"], req.inputs, req.tt, request=req.data,
                             out_root=a.out, work_root=a.work)
        except ValueError as e:                   # e.g. needs more than one stage (cp2)
            print(json.dumps({"status": "unsupported", "reason": str(e)}))
            return 2
    print(json.dumps({"cell": rep["cell"], "status": rep["status"], "failed": rep["failed_checks"]}))
    return 0 if rep["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
