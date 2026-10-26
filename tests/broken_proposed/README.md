# Proposed broken cases (waiting for a human)

AGENTS.md says only a human adds a broken case. An assistant wrote these four. The tests already show
that each one is rejected (`tests/integration/test_proposed_broken.py`). A group member should review
them, move them into `tests/broken/`, and regenerate `tests/broken/SHA256SUMS`.

| File | Check it must fail | Why it is needed |
|---|---|---|
| `yosys_rejects.lib` | Yosys `read_liberty` and `read_liberty -lib` exit non-zero (a missing `;` after an attribute) | Option 2 handout 9.1: "a Liberty file Yosys must reject". `tests/broken/invalid_function.lib` is rejected by our reader, but Yosys accepts it. |
| `nonequivalent_restructured.aig` | ABC `cec` against `tests/broken/wrong_truth_table.aig` (cpu8 synth) reports NOT EQUIVALENT | The restructured-AIG check (`dd2.aig.cec`) needs a case it must fail. It was made by flipping one fanin polarity of the last AND gate. |
| `nand2_pullup_deleted.spice` | ngspice transistor-level simulation fails (DC row A=1, B=0 floats) | Option 1 handout 4.2: "a netlist with one pull-up transistor deleted must fail the transistor-level simulation". |
| `nand2_model_wrong_row.v` | the Icarus model-level check fails on row 1 | Option 1 handout 4.2: "a Verilog model with one wrong truth-table row must fail the model-level check". |

## Review (2026-10-26 and 2026-10-27)
Each case was checked and fails its check. The two Yosys/ABC cases fail on both Yosys 0.33 (dd2-flow)
and 0.70 (host). An earlier unbalanced-brace Liberty case was replaced, because Yosys 0.33 accepts it.
The assistant's attempt to move the cases into `tests/broken/` was blocked by the Claude Code
permission classifier as a change to protected checks, so a group member must run:

    git mv tests/broken_proposed/*.lib tests/broken_proposed/*.aig tests/broken_proposed/*.spice tests/broken_proposed/*.v tests/broken/
    (cd tests/broken && find . -type f ! -name SHA256SUMS | sort | xargs shasum -a 256 > SHA256SUMS)
    sed -i '' 's|"broken_proposed"|"broken"|' tests/integration/test_proposed_broken.py
    make test

Commit that move yourself (it is a human decision, not an AI-assisted change).
