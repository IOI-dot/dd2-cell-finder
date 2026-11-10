"""make o1-rules: the table of design rules behind every number in the layout (handout 8.2)."""
import csv
import sys

from dd2 import paths

from . import rules


def main() -> int:
    out = paths.results("option1", "rules.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "value_um", "rule", "meaning"])
        for name, r in sorted((n, v) for n, v in vars(rules).items() if isinstance(v, rules.Rule)):
            w.writerow([name, r.value, r.rule, r.meaning])
    print(f"wrote {paths.rel(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
