import argparse
import json
from pathlib import Path
from dd2 import designs, paths
from . import flow, tutorials


def main():
    ap = argparse.ArgumentParser(description="Option 2 M2; no AI model runs in this tool")
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--out", type=Path, default=paths.build("environment.json"))
    c.add_argument("--strict", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--group", type=int, required=True)
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--designs", nargs="+", default=[d.name for d in designs.required()])
    r.add_argument("--out", type=Path, default=paths.results("m2"))
    sub.add_parser("readiness")
    sub.add_parser("m1-summary")
    sub.add_parser("showcase")
    est = sub.add_parser("m3-estimated", help="greedy remapping and course-generator requests")
    demo = sub.add_parser("demo", help="complete Option 2 workflow on an unseen design")
    for parser in (est, demo):
        parser.add_argument("--group", type=int, required=True)
        parser.add_argument("--limit", type=int, default=10)
    est.add_argument("--out", type=Path)
    est.add_argument("--best-of-all", action="store_true", help="remap every eligible candidate in each round")
    demo.add_argument("design", type=Path)
    demo.add_argument("--top")
    demo.add_argument("--sv", action="store_true")
    demo.add_argument("--real", type=Path)
    real = sub.add_parser("m3-real", help="map with passing responses from the course generator")
    real.add_argument("--responses", type=Path, required=True)
    real.add_argument("--estimated", type=Path, default=paths.results("m3", "estimated"))
    real.add_argument("--out", type=Path, default=paths.results("m3", "real"))
    steps = ["fit", "baseline", "candidates", "library", "map", "plots", "discovery", "tutorials"]
    for step in steps:
        s = sub.add_parser(step)
        s.add_argument("--out", type=Path, default=paths.results("m2"))
        s.add_argument("--designs", nargs="+", default=[d.name for d in designs.required()])
        if step == "library":
            s.add_argument("--group", type=int, required=True)
            s.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    try:
        if args.command == "check":
            return 0 if flow.check(args.out, args.strict) else 1
        if args.command == "m1-summary":
            return flow.m1_summary()
        if args.command == "showcase":
            flow.showcase(paths.results("m2"))
            return 0
        if args.command == "readiness":
            p = paths.results("m2", "readiness.json")
            if not p.is_file():
                print("M2 has not been run")
                return 1
            data = json.loads(p.read_text())
            print(json.dumps(data, indent=2))
            return 0 if data["checkpoint_ready"] else 1
        if args.command in {"m3-estimated", "m3-real", "demo"}:
            from . import final_flow

            if args.command == "m3-real":
                final_flow.real(args.estimated.absolute(), args.out.absolute(), args.responses)
            else:
                if args.group < 1 or not 1 <= args.limit <= 10:
                    raise ValueError("positive group and limit 1..10 required")
                if args.command == "demo":
                    final_flow.demo(args.design, args.top, args.sv, args.group, args.limit, args.real)
                else:
                    folder = "estimated-best" if args.best_of_all else "estimated"
                    out = args.out or paths.results("m3", folder)
                    final_flow.estimated(out.absolute(), args.group, args.limit, best_of_all=args.best_of_all)
            return 0
        if args.command in steps:
            out = args.out.absolute()
            out.mkdir(parents=True, exist_ok=True)
            args.designs = list(
                dict.fromkeys(args.designs + [n for n in tutorials.SPECS if tutorials.supplied(n)])
            )
            if args.command == "fit":
                flow.calibrate(out)
            elif args.command == "baseline":
                flow.baseline(args.designs, out)
            elif args.command == "candidates":
                from dd2 import liberty

                flow.candidates(
                    args.designs,
                    out,
                    liberty.read_cells(paths.full_hd_lib()),
                    json.loads((out / "area_model.json").read_text()),
                )
            elif args.command == "library":
                if args.group < 1 or not 1 <= args.limit <= 10:
                    raise ValueError("positive group; limit 1..10 required")
                from .library import write_library

                reqs = flow.requests(
                    out, args.group, args.limit, json.loads((out / "candidates.json").read_text())
                )
                write_library(paths.given() / "hd_reduced.lib", out / "hd_extended_estimated.lib", reqs)
            elif args.command == "map":
                flow.measure(
                    args.designs,
                    out,
                    out / "hd_extended_estimated.lib",
                    json.loads((out / "requests.json").read_text()),
                )
            elif args.command == "plots":
                flow.plots(out)
            elif args.command == "discovery":
                flow.write_csv(out / "tutorial_aig_cuts.csv", tutorials.discovery(args.designs, out))
            elif args.command == "tutorials":
                result = tutorials.verify(args.designs, out, out / "hd_extended_estimated.lib")
                return (
                    0
                    if len(result) == 2
                    and all(r["mapping_and_gate_simulation_verified"] for r in result.values())
                    else 1
                )
            return 0
        if args.group < 1:
            raise ValueError("group must be your actual positive DD2 group number")
        if not 1 <= args.limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        return flow.run(args.group, args.limit, args.designs, args.out)
    except (ValueError, RuntimeError, OSError, KeyError) as e:
        print("FAIL:", e)
        return 1


raise SystemExit(main())
