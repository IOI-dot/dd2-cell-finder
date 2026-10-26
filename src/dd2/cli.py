"""dd2 command line. Exit codes: 0 pass, 1 check failed, 2 usage or missing input."""
import argparse
import sys
from pathlib import Path

from . import paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dd2")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="tool versions, PDK and supplied inputs")
    c.add_argument("--given", type=Path, default=paths.given())
    c.add_argument("--pdk", type=Path, default=paths.pdk())
    c.add_argument("--out", type=Path, default=paths.build("environment.json"))

    b = sub.add_parser("baseline", help="map designs (handout section 2) and write Table 1")
    b.add_argument("--designs", nargs="*", default=None)
    b.add_argument("--out", type=Path, default=paths.results("m1"))
    b.add_argument("--given", type=Path, default=paths.given())

    a = sub.add_parser("aig", help="write synth and restructured AIGs")
    a.add_argument("--designs", nargs="*", default=None)
    a.add_argument("--out", type=Path, default=paths.results("m1", "aigs"))
    a.add_argument("--given", type=Path, default=paths.given())
    a.add_argument("--scratch", type=Path, default=paths.build("aigs"))

    k = sub.add_parser("cuts", help="enumerate and check 4-input cuts of the M1 AIGs")
    k.add_argument("--aigs", type=Path, default=paths.results("m1", "aigs"))
    k.add_argument("--out", type=Path, default=paths.results("m1", "cuts"))
    k.add_argument("--full", type=Path, default=paths.build("cuts"))
    k.add_argument("--designs", nargs="*", default=None)

    ck = sub.add_parser("cutcheck", help="independently check a cut file against its AIG")
    ck.add_argument("--aig", type=Path, required=True)
    ck.add_argument("--cuts", type=Path, required=True)

    h = sub.add_parser("hdclasses", help="class table of HD")
    h.add_argument("--pdk", type=Path, default=paths.pdk())
    h.add_argument("--given", type=Path, default=paths.given())
    h.add_argument("--out", type=Path, default=paths.results("m1"))

    cl = sub.add_parser("classify", help="redundancy class of one function")
    cl.add_argument("--tt", required=True)
    cl.add_argument("--arity", type=int, required=True)
    cl.add_argument("--pdk", type=Path, default=paths.pdk())

    s = sub.add_parser("selftest", help="redundancy checker self-test (Table 4)")
    s.add_argument("--pdk", type=Path, default=paths.pdk())
    s.add_argument("--out", type=Path, default=paths.results("m1", "redundancy"))

    d = sub.add_parser("demo", help="run the M1 front end on one design into build/demo")
    d.add_argument("design", type=Path)
    d.add_argument("--top", default=None)
    d.add_argument("--sv", action="store_true")
    d.add_argument("--given", type=Path, default=paths.given())
    d.add_argument("--pdk", type=Path, default=paths.pdk())

    sm = sub.add_parser("summary", help="generate results/m1/summary.md from the records")
    sm.add_argument("--out", type=Path, default=paths.results("m1"))

    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0

    if args.cmd == "check":
        from .envcheck import check
        return check(args.given, args.pdk, args.out)
    if args.cmd == "baseline":
        from .mapping import run_all
        return run_all(args.given, args.out, args.designs)
    if args.cmd == "aig":
        from .aig import run_all
        return run_all(args.given, args.out, args.designs, args.scratch)
    if args.cmd == "cuts":
        from .cutflow import run_all
        return run_all(args.aigs, args.out, args.full, args.designs)
    if args.cmd == "cutcheck":
        from .cutflow import check_file
        return check_file(args.aig, args.cuts)
    if args.cmd == "hdclasses":
        from .hdclasses import run
        return run(args.pdk, args.given, args.out)
    if args.cmd == "classify":
        from .redundancy import cli_classify
        return cli_classify(args.tt, args.arity, args.pdk)
    if args.cmd == "selftest":
        from .redundancy import run_selftest
        return run_selftest(args.pdk, args.out)
    if args.cmd == "demo":
        from .demo import run
        return run(args.design, args.top, args.sv, args.given, args.pdk)
    if args.cmd == "summary":
        from .summary import run
        return run(args.out)
    return 2


if __name__ == "__main__":
    sys.exit(main())
