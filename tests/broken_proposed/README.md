# Proposed broken cases (waiting for a human)

AGENTS.md says only a human adds a broken case. An assistant wrote these after the 2026-10-26
verification (findings 8 and 13). Review each one; if you accept it, move it into `tests/broken/`,
regenerate `tests/broken/SHA256SUMS` yourself, and point the test at the new path.

| File | Check it must fail | Why it is needed |
|---|---|---|
| `yosys_rejects.lib` | Yosys `read_liberty -lib` exits non-zero (unbalanced braces) | Option 2 handout 9.1: "a Liberty file Yosys must reject". `tests/broken/invalid_function.lib` is rejected by our reader but Yosys accepts it. |
| `nonequivalent_restructured.aig` | ABC `cec` against `tests/broken/wrong_truth_table.aig` (cpu8 synth) reports NOT EQUIVALENT | The restructured-AIG check (`dd2.aig.cec`) needs a case that it must fail. Made by flipping one fanin polarity of the last AND gate. |

Table 1 completeness already has a negative test: `test_table1_rejects_incomplete_matrix`.
