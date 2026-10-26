# Quickstart: validating Option 2 Milestone 1 (cp1)

This is the script for the 10-minute TA meeting and for a clean-checkout check. Expected outcomes refer
to [contracts/cli.md](contracts/cli.md) and [contracts/results-schema.md](contracts/results-schema.md).

## Prerequisites
- At least 2 GB free on disk for M1 (≥ 15 GB later for Docker, the PDK views and the course container). Check with `df -h ~`.
- `uv`, Yosys (pinned version, research D-2), Icarus 13+, and the SKY130 PDK under `PDK_ROOT` (default `~/.ciel`).
- The student pack **outside** the repository: `../DD2_Project1_student_pack/`.

## 1. Setup and environment
```bash
git clone <repo> dd2 && cd dd2 && git checkout cp1
make setup                         # creates pdk/ and given/ symlinks, runs uv sync
make check                         # exit 0; results/m1/environment.json lists versions
```
Expected: `check: pass`. `results/m1/environment.json` records `liberty_import` = 189 (reduced)
and 307 (usable) and the full HD library's 428 cells. OpenSTA and the layout container are printed
as `NOTE … required from M2 / Option 1`, not as passing.

## 2. Tests, including the broken cases
```bash
make test
```
Expected: all tests pass, and the report shows these negative tests rejecting their broken inputs:
- `tests/broken/wrong_truth_table.json` is rejected by the cut check
- `tests/broken/hd_cell_as_candidate.json` (an HD cell) is classified `Exists`, not `New`
- `tests/broken/invalid_function.lib` is rejected by the Liberty reader
- `tests/broken/missing_given/` makes `dd2 check --given tests/broken/missing_given` fail and name the missing files

## 3. The M1 flow
```bash
make m1            # or: make all
make agent-check   # cp1 agentic rows: wrapped tools, refused bad calls, Appendix B log
```
Expected (each item points to a file the TA can open):
| cp1 requirement | File | Pass condition |
|---|---|---|
| AIGs of every required design | `results/m1/aigs/manifest.json` | 12 entries, every `run.status = pass`, restructured ≠ synth |
| Cut enumerator passing its check | `results/m1/cuts/summary.csv` | `failures = 0` and `checked = total` on all 12 rows |
| Table 1 reproduced | `results/m1/table1.csv` | 24 measured cells; the Yosys version is recorded and deltas are shown |
| Class table of HD | `results/m1/hd_classes.csv` | 323 single-output combinational cells; PN and NPN class counts |
| Redundancy checker self-test | `results/m1/redundancy/self_test.json` | all HD cells `Exists`; Table 4 rows 1–5 and 7 match; row 6 shown as `definition-open` (research Q-1) |

## 4. The demo path (the interview runs this on an unseen design)
```bash
make demo IN=given/designs/dsp8.v TOP=dsp8
```
Expected: `build/demo/dsp8/` contains baseline areas, both AIGs, a cut summary with 0 failures, and the
redundancy class of every 4-input PN class found. `results/m1` is unchanged (`git status` is clean).

## 5. Hygiene checks before tagging `cp1`
```bash
git ls-files | grep -E 'DD2_Project1_student_pack|^given/|^pdk/|\.pdf$|^references/' && echo "FIX FIRST"
git ls-files -z | xargs -0 du -k | awk '$1 > 51200' | grep . && echo "FILE OVER 50 MB"
git log -1 --format=%B | grep -q 'AI-assisted:' && echo "trailer ok"
```
Then `git tag cp1 && git push origin cp1`, **once** and before the meeting. Never move it afterwards.
