# Independent verification of Milestone 1 (2026-10-26, commit 71656fb)

An adversarial subagent reviewed the work read-only, with its own code. Its scratch scripts are in
the session scratchpad `verify/`.

## Confirmed independently
- **Table 4.** Rows 1–5 and 7 come out the same from an independent classifier that does not
  import dd2, and its class agrees with ours on all 3,904 classes.
- **HD filter.** The 323-cell filter is right: 428 = 323 combinational + 69 sequential + 13
  tri-state + 10 two-output + 12 with no output + 1 with no input. All 323 classify as Exists.
- **HD class table.** It matches exactly: P/PN/NPN = 77/40/19.
- **Cuts.**
  - All 315,522 stored cuts are correct: truth tables, cut property, and leaf 0 = LSB.
  - A brute-force completeness check (hundreds of roots) found 0 missing and 0 extra cuts.
  - Cutcheck has no shared code and caught 185 of 200 mutations; the other 15 were semantically identical.
- **AIGs.** Latches = flip-flops = the handout's Table 2 on all six designs. ABC `cec` says synth ≡ restructured on all six.
- **Table 1 mechanics.** The commands are byte-equal to `map.sh`, and two values were reproduced by running `map.sh` directly.
- **Repository.** A clean clone runs `make setup/check/test/all` (81 tests, 13 s; `all` 36 s). Hygiene, the README section order, the Appendix B log shape and the Appendix A examples are all right.

## Findings to act on (status column updated by whoever fixes them)
| # | Sev | Finding | Fix | Status |
|---|---|---|---|---|
| 1 | BLOCKER (scope) | The Option 1 cp1 rows (inv_1/nand2_1 at 2.72 µm, frame check, request reader, ngspice stress test in `make check`) are absent. This is an Option 3 group, so both options are graded. | The Option 1 sub-team must do it, or get the scope agreed with the TA in writing. | open (group decision) |
| 2 | BLOCKER (action) | There is no cp1 tag; 71656fb is not pushed. | Push, then the group tags cp1 once. | open (human) |
| 3 | MAJOR | The Table 1 status says "pass" although it was measured on 0.70 and differs by up to 4.49%. The reduced-vs-usable 0.5% claim fails on fir10/A (+3.00%), risc8/A and uart/A. `plan.md` says 0.33 is pinned (false). `baseline_yosys070/` was never made. | Do T004 (yowasp 0.33), or label it "measured on 0.70, not reproduced" with a tolerance check. Fix plan.md. Discuss the AND-count gap with the handout's Table 2. | fixed: summary says NOT REPRODUCED (0/12 rows match); `table1.csv` has `matches_handout`; plan.md corrected. T004 still open |
| 4 | MAJOR | Table 4 row 6 (6 vs 5), yet the self-test reads as a plain "pass". The six functions are three dual pairs (0x17↔0x17FF, 0x11F↔0x77F, 0x13F↔0x37F), so every symmetric definition gives an even count. 5 comes only from checking the first minimum-literal form an enumerator happens to find. | Report as "pass (rows 1–5, 7); row 6 open". Bring the dual-pair argument to the TA. | fixed: status 'pass on rows 1-5 and 7; row 6 open'; dual-pair argument in research D-7 |
| 5 | MAJOR | The agent guard: `run_id` is not validated (`../tests/broken` passes `may_write`); PDK, `tests/` and `agent/` are not protected; the digest only detects changes, it doesn't prevent them; `extract_aig` writes `build/aigs/*` outside the run. | Validate `run_id` with `^A-\d{4}-\d{2}$`; protect more paths; give each run its own scratch directory; chmod or `:ro` mounts. | fixed: run_id regex, tests/ + agent/ + PDK lib protected, run-local scratch; prevention by :ro mounts still to come (docker/) |
| 6 | MAJOR | The restructured AIGs record O=0: ABC wrote the outputs as B (bad-state) lines, and the reader skips B. | Treat B as outputs and record B in `header()`. Check that O+B equals the synth O. Add `cec` to `make m1-aigs`. | fixed: B lines read as outputs, O+B checked, ABC cec in make m1-aigs (all six equivalent) |
| 7 | MAJOR (M2) | `eval_expr` precedence is ! > & > ^ > |, but Yosys/Liberty have ^ above &. | Use ! > ^ > & > |, with a test against Yosys `eval`. | fixed: ! > ^ > & > |, tested against Yosys eval |
| 8 | MINOR | Yosys accepts `tests/broken/invalid_function.lib`; handout 9.1 wants a Liberty file that Yosys rejects. | T042 (M2). | proposed: tests/broken_proposed/yosys_rejects.lib (human to promote) |
| 9 | MAJOR | README §1 still has the placeholder names and IDs. | The group fills them in. | partly: commit authors listed; IDs and full names for the group |
| 10 | MINOR | The AI log has no commit hashes and no names in the "Who" column. AI authored the broken cases and SHA256SUMS, against AGENTS.md. The README timings are typed by hand. | A human reviews and re-hashes the broken cases. Fill the log columns. | fixed in logs (hashes, names); broken cases still need human review |
| 11 | MINOR | `classify` accepts a truth table larger than its arity (0x6 at arity 1 gives Exists). | Reject `tt > mask(n)`. | fixed |
| 12 | MINOR | The Liberty reader gives area 0 when `area` comes after the pins, and silently skips an output without a function. | Fix the area lookup; raise on an output with no function. | fixed: area outside pins; 105 exclusions recorded with reasons (428 accounted) |
| 13 | MINOR | Checks that pass vacuously: cutcheck on an empty file passes; `checked == total` is a tautology; "restructured ≠ synth" by sha256 can never fail. AIG and Table 1 checks have no broken cases. | Count checks separately; fail on empty input; add broken cases (a human adds them). | fixed: empty input fails; passed/failed counted vs enumeration; cec replaces sha test; AIG case proposed |
| 14 | MINOR | The demo classifies PN classes by the representative's polarity; 32 of 1,952 classes differ by polarity. | Key by P class or by the actual table. | fixed: demo keyed by P class |
| 15 | MINOR | The synth AIG is not strashed (uart 3551 → 2215 with strash alone), so `compare.csv` credits dch with the strash gain. | Add a strash-only column. | fixed: strash_only_ands column |
| 16 | MINOR | `make check` rewrites the tracked `environment.json` with absolute paths; the PDK ciel hash is not recorded; the run-log results point into the ignored `runs/`. | Write `environment.json` to build/ or with relative paths; record the ciel hash. | fixed: relative paths, ciel version recorded, `make check` writes build/, runs/ committed |
| 17 | MINOR | `.gitignore` `*.pdf` blocks `report/*.pdf`. Demo without `TOP=` fails on risc8. The AIGER reader accepts out-of-order literals. | `!report/*.pdf`; `hierarchy -auto-top`; validate literal order. | fixed: !report/*.pdf; demo auto-detects top; reader rejects bad/unordered literals |
| 18 | MINOR | Tasks marked [x] that deviate from their own text: T006 (no `uv run`), T012 (no `dd2 env`), T018 (no `baseline_yosys070`), T034 (README §1), T041 (`requests.py` became `interface.py`). | Correct `tasks.md` or finish them. | fixed: tasks.md annotated (T006, T012, T018, T041); T034 reopened |
| 19 | NOTE | The student pack is still in history (e55f766, pushed). SPM and the Tutorial 2 multiplier are needed from M2. | Group decision (Q-4); M2. | open (group decision / M2) |

## Re-verification of a9e925a (same reviewer, fresh clone)

**Result:** the fixes for findings 3–7 and 11–17 hold up. On a fresh clone, 106 tests passed and
`make all` and `make agent-check` both passed. The committed tables were regenerated
byte-identically.

Mutation tests confirmed that `cec` compares the B outputs and the latch inputs. Seven more
expressions matched Yosys `eval` exactly. The precedence fix changed no committed result.

Six minor leftovers, all addressed in the commit after a9e925a:

| # | Leftover | Fix |
|---|---|---|
| R1 | A symlinked `runs/<id>` or `scratch/` still escaped the write guard; `RUN_ID.match` accepted a trailing newline; only the declared output was checked. | `fullmatch`; refuse any symlink from `runs/<id>` down; require the run directory's parent to be `runs/`; check every path argument of a tool. |
| R2 | `checked == expected` was still computed from the same lists. | Recount the cuts in the written `jsonl.gz` (`cuts_in_full_list`). |
| R3 | A cell with no `area` came back as 0.0, silently. | Recorded as skipped (`no area`). |
| R4 | README timings, the `make check` output path and the cec note were stale; Python is not pinned. | README updated. Python stays unpinned on purpose (any version ≥ 3.11 keeps the TA's machine working) and is recorded in `environment.json`. |
| R5 | Commands and logs held absolute `/Users/...` paths. | Repository-relative paths, with tools run from the repository root. Runs A-1026-01/02 predate the fix and are kept as history. |
| R6 | `runs/<id>/baseline/baseline` was nested twice. | The tool passes `--out runs/<id>`. |

The two notes from the re-verification, also handled:
- **cec ignores latch initial values.** This is harmless while every latch is uninitialised, and the `aig.cec` docstring now says so.
- **Request expressions need explicit precedence.** T041 now requires fully parenthesised expressions.
