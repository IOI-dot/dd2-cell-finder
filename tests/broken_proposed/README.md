# Proposed broken cases (waiting for a human)

AGENTS.md says only a human adds a broken case. An assistant wrote these after the 2026-10-26
verification (findings 8 and 13). Review each one; if you accept it, move it into `tests/broken/`,
regenerate `tests/broken/SHA256SUMS` yourself, and point the test at the new path.

| File | Check it must fail | Why it is needed |
|---|---|---|
| `yosys_rejects.lib` | Yosys `read_liberty` and `read_liberty -lib` exit non-zero (a missing `;` after an attribute) | Option 2 handout 9.1: "a Liberty file Yosys must reject". `tests/broken/invalid_function.lib` is rejected by our reader but Yosys accepts it. |
| `nonequivalent_restructured.aig` | ABC `cec` against `tests/broken/wrong_truth_table.aig` (cpu8 synth) reports NOT EQUIVALENT | The restructured-AIG check (`dd2.aig.cec`) needs a case that it must fail. Made by flipping one fanin polarity of the last AND gate. |

Table 1 completeness already has a negative test: `test_table1_rejects_incomplete_matrix`.

## Review (2026-10-26)
Both cases were reviewed and fail their check on Yosys 0.33 (dd2-flow) and 0.70 (host); see
`tests/integration/test_proposed_broken.py`. An unbalanced-brace version was replaced, because
Yosys 0.33 accepts it. The user asked for both to be promoted. The assistant's attempt to move them
into `tests/broken/` and regenerate `SHA256SUMS` was blocked by the Claude Code permission
classifier, as a change to protected checks. So a group member must promote them:

    git mv tests/broken_proposed/yosys_rejects.lib tests/broken_proposed/nonequivalent_restructured.aig tests/broken/
    (cd tests/broken && find . -type f ! -name SHA256SUMS | sort | xargs shasum -a 256 > SHA256SUMS)
    sed -i '' 's|"broken_proposed"|"broken"|' tests/integration/test_proposed_broken.py
    make test
