"""Our expression semantics must equal Yosys's reading of the same Liberty function."""
import re
import subprocess

import pytest

from dd2 import boolfn as bf


@pytest.mark.parametrize("expr", ["A&B^C", "A|B^C&!A", "!A^B|C&B"])
def test_matches_yosys_eval(tmp_path, expr):
    lib = tmp_path / "p.lib"
    lib.write_text('library (p) { cell (pc) { area : 1; pin (A) { direction : input; } '
                   'pin (B) { direction : input; } pin (C) { direction : input; } '
                   f'pin (Y) {{ direction : output; function : "{expr}"; }} }} }}\n')
    evals = "; ".join(f"eval -set A {i & 1} -set B {(i >> 1) & 1} -set C {(i >> 2) & 1} -show Y pc"
                      for i in range(8))
    out = subprocess.run(["yosys", "-p", f"read_liberty {lib}; {evals}"], capture_output=True,
                         text=True).stdout
    bits = [int(b) for b in re.findall(r"Eval result: \\Y = 1'(\d)", out)]
    assert len(bits) == 8, out[-500:]
    assert sum(b << i for i, b in enumerate(bits)) == bf.eval_expr(expr, "ABC")
