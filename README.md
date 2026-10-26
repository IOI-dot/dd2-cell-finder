# Project 1, Option 3: DD2 Cell Finder

## 1. Group
<names and student IDs, to be filled in by the group; commit authors so far: Omar Abdel Motalb,
Mohamed Azouz, Noor Elshahidi> · Option 3 (Options 1 and 2, connected) · AI used as an agentic system
(LangGraph planned; at cp1 the wrapped tools, read-only checks and run logs exist, see section 8)

## 2. Quick start
Tools used: Yosys 0.70+post (git 0c11ea0, the handout's Table 1 used 0.33), yosys-abc (bundled),
Icarus Verilog 13.0, Python 3.14.6 in `.venv` (any Python >= 3.11), SKY130A via ciel
(`dd7771c…`). Magic, Netgen and ngspice (Option 1) and OpenSTA (from M2) are not used by M1.

    make setup     # about 1 s (pytest cached by uv; a first install takes longer)
    make check     # under 1 s
    make test      # about 20 s
    make all       # about 40 s: the whole M1 flow into results/m1/

Timings were measured by the independent verification run on a fresh clone of a9e925a, on an
Apple-silicon laptop (2026-10-26): setup 0.8 s, check 0.4 s, test 18.2 s, all 39.4 s. Any
Python >= 3.11 works; uv picks the newest one installed, and `results/m1/environment.json` records
which one was used.

`make setup` expects `PDK_ROOT` (default `~/.ciel`, containing `sky130A`) and
`GIVEN` (default `../DD2_Project1_student_pack/given`). Nothing is copied.

## 3. What the tool does
Option 2 finds the small Boolean functions a synthesized design computes again and again and
checks which of them SKY130 HD lacks; Option 1 (later) builds the chosen ones as HD cells. At
Milestone 1 the tool runs in this order: (1) map every required design onto the usable and the
reduced HD library with ABC scripts A and B (Table 1); (2) write each design as an AIG, once as
synthesized and once restructured by ABC; (3) enumerate every cut of up to 4 inputs with its
truth table, and check each one by simulating its cone for every input combination; (4) build the
class table of HD; (5) classify functions as Exists / Exists with an inverter / Contained / New
against the full HD library, and self-test that checker against Table 4 of the handout.

## 4. Commands
| Command | Input | Output |
|---|---|---|
| `make setup` | `PDK_ROOT`, `GIVEN` | `pdk`, `given` links; `.venv` |
| `make check` | links, tools | `build/environment.json`; fails on a missing tool or input |
| `make test` | `tests/` | pytest; also verifies `tests/broken/SHA256SUMS` |
| `make all` / `make m1` | the six required designs | everything under `results/m1/` (starts with `m1-env`) |
| `make m1-env` | links, tools | `results/m1/environment.json` (plain `make check` writes `build/environment.json`) |
| `make m1-baseline` | designs, both libraries | `results/m1/baseline/**`, `results/m1/table1.csv` |
| `make m1-aigs` | designs | `results/m1/aigs/<design>/{synth,restructured}.{aig,json,log}`, `cec.log` (ABC equivalence), `manifest.json`, `compare.csv` |
| `make m1-cuts` | the 12 AIGs | `results/m1/cuts/**` (summaries, 1% samples); full lists in `build/cuts/` |
| `make m1-hdclasses` | full HD Liberty, reduced library | `results/m1/hd_classes.{json,csv}`, `hd_pn_classes.csv` |
| `make m1-redundancy` | full HD Liberty | `results/m1/redundancy/{self_test,four_input_counts}.json` |
| `make m1-summary` | the records above | `results/m1/summary.md` and section 6 of this file |
| `make agent-check` | cpu8 | `ai/runs/<run>.jsonl`, `ai/runs/<run>.checks.json`; tool outputs in `runs/<run>/` |
| `make demo IN=<design.v> [TOP=<top>] [SV=1]` | any Verilog design | `build/demo/<name>/` (never touches `results/`) |
| `make clean` | | removes `build/` |
| `.venv/bin/python -m dd2 cutcheck --aig A --cuts F` | an AIG and cut records | exit 1 if any stored truth table is wrong |
| `.venv/bin/python -m dd2 classify --tt 0x077F --arity 4` | a truth table | its redundancy class and HD witness |

(Run the `dd2` commands with `PYTHONPATH=src`.)

## 5. Layout
- `src/dd2/`: the deterministic tool (standard library only)
- `agent/dd2_agent/`: typed tool wrappers, policy guard, run logs (the agent layer)
- `backend/`, `web/`, `docker/`: planned platform parts (placeholders; see `docs/architecture.md`)
- `tests/`: unit, contract and integration tests; `tests/broken/` the immutable broken cases;
  `tests/broken_proposed/` broken cases waiting for human review; `tests/fixtures/` tiny AIGs
- `results/m1/`: every table and log the M1 evidence uses
- `docs/interface/`: the Appendix A request/response examples and their JSON Schemas
- `libs/`, `cells/`: Liberty files (M2) and Option 1 cells (later); empty at cp1
- `ai/`: AI use and mistakes logs; `ai/runs/` agent run logs; `runs/` the outputs those logs point to
- `specs/001-agentic-cell-finder/`: specification, plan, research, contracts and tasks (Spec Kit)
- `report/`: reports (at submission)

## 6. Results
<!-- m1-summary:start -->
| cp1 requirement | Evidence | Status |
|---|---|---|
| Environment (make check) | `results/m1/environment.json` | pass |
| Table 1: 24 mappings measured (research D-2) | `results/m1/table1.csv` | NOT REPRODUCED: 0/12 rows match the handout (Yosys 0.70+post vs the handout's 0.33; max deviation 4.49%) |
| AIGs of every required design, synth and restructured: 12 artifacts | `results/m1/aigs/manifest.json` | pass |
| Cut enumerator passing its check: 315522 cuts, 0 failures | `results/m1/cuts/summary.csv` | pass |
| Class table of HD: 323 cells, 40 PN classes, 19 NPN classes | `results/m1/hd_classes.csv` | pass |
| Redundancy self-test: 323/323 HD cells Exists; Table 4 below | `results/m1/redundancy/self_test.json` | pass on rows 1-5 and 7; row 6 open (Q-1) |
| Agentic rows: tools wrapped, checks read-only, runs logged | `ai/runs/A-1026-03.checks.json` | pass |
| Option 3: request/response format fixed (Appendix A) | `docs/interface/` | pass |

Table 4 self-test (4-input functions that depend on all inputs, up to input order):

| Row | Handout | Measured | Status |
|---|---:|---:|---|
| exists | 24 | 24 | match |
| exists_with_inverter | 20 | 20 | match |
| contained | 38 | 38 | match |
| new | 3822 | 3822 | match |
| new_one_stage | 9 | 9 | match |
| new_one_stage_small | 5 | 6 | definition-open |
| one_stage_read_once | 8 | 8 | match |

Table 1 (um^2, Yosys 0.70+post; the handout's Yosys 0.33 values for comparison):

| Design | Script | Usable | Reduced | Reduced vs usable | Handout reduced | Ours vs handout |
|---|---|---:|---:|---:|---:|---:|
| cpu8 | A | 4169.0 | 4195.3 | +0.63% | 4186.5 | +0.21% |
| cpu8 | B | 4316.6 | 4321.6 | +0.12% | 4359.2 | -0.86% |
| dsp8 | A | 5773.0 | 5794.3 | +0.37% | 5928.2 | -2.26% |
| dsp8 | B | 6099.6 | 6102.1 | +0.04% | 6214.7 | -1.81% |
| arlet6502 | A | 9285.2 | 9320.2 | +0.38% | 9701.8 | -3.93% |
| arlet6502 | B | 9557.9 | 9546.7 | -0.12% | 9995.8 | -4.49% |
| uart_apb | A | 12643.4 | 12817.3 | +1.38% | 12948.7 | -1.01% |
| uart_apb | B | 13028.7 | 13030.0 | +0.01% | 13180.1 | -1.14% |
| risc8 | A | 27764.1 | 28187.0 | +1.52% | 28263.4 | -0.27% |
| risc8 | B | 28112.0 | 28109.5 | -0.01% | 27511.4 | +2.17% |
| fir10 | A | 25557.0 | 26322.7 | +3.00% | 25968.7 | +1.36% |
| fir10 | B | 28935.3 | 28935.3 | +0.00% | 29055.4 | -0.41% |

Cuts per AIG:

| Design | Variant | ANDs | Cuts | Failures | PN classes | NPN classes |
|---|---|---:|---:|---:|---:|---:|
| cpu8 | synth | 932 | 6054 | 0 | 174 | 59 |
| cpu8 | restructured | 857 | 5417 | 0 | 174 | 56 |
| dsp8 | synth | 1677 | 11942 | 0 | 206 | 54 |
| dsp8 | restructured | 1305 | 9744 | 0 | 188 | 48 |
| arlet6502 | synth | 2511 | 19162 | 0 | 197 | 55 |
| arlet6502 | restructured | 2093 | 14599 | 0 | 193 | 50 |
| uart_apb | synth | 3551 | 29154 | 0 | 191 | 43 |
| uart_apb | restructured | 1748 | 9196 | 0 | 112 | 34 |
| risc8 | synth | 5480 | 39098 | 0 | 189 | 52 |
| risc8 | restructured | 4875 | 32017 | 0 | 175 | 46 |
| fir10 | synth | 8217 | 77025 | 0 | 203 | 54 |
| fir10 | restructured | 6383 | 62114 | 0 | 199 | 52 |
<!-- m1-summary:end -->

## 7. Tests
`make test` runs every test. Each check has a broken case it must reject:

| Check | Broken case |
|---|---|
| Cut truth-table check | `tests/broken/wrong_truth_table.json`: a real cpu8 cut with one flipped bit |
| Redundancy check | `tests/broken/hd_cell_as_candidate.json`: HD's a21oi, renamed and reordered, must be Exists |
| Liberty reader | `tests/broken/invalid_function.lib`: an unknown operator must be rejected |
| Environment check | `tests/broken/missing_given/`: `dd2 check` must fail and name the missing files |
| Appendix A validator | requests with a wrong truth table, 5 inputs, a bad name or sizing (`tests/contract/test_interface.py`) |
| Agent policy | writes into `tests/broken/`, `given/`, `src/`, `results/`, malformed run IDs, invalid arguments, unknown tools (`tests/unit/test_agent.py`) |
| Restructured AIG equivalence | proposed: `tests/broken_proposed/nonequivalent_restructured.aig` must fail ABC `cec` |
| Liberty rejected by Yosys | proposed: `tests/broken_proposed/yosys_rejects.lib` (handout 9.1) |
| Expression semantics | three mixed-operator functions are compared with Yosys `eval` (`tests/integration/test_precedence.py`) |

`tests/broken/SHA256SUMS` makes any edit to a broken case fail the suite.

## 8. AI use
AGENTS.md · ai/use_log.md · ai/mistakes_log.md · ai/runs/ · report/ai_report.pdf (at submission)

## 9. Limitations
- Table 1 is measured with Yosys 0.70, not the handout's 0.33. Areas differ by up to 4.5%, and on
  0.70 the reduced library costs up to 3.0% over the usable one (fir10, script A), not the
  handout's 0.5% or less. A pinned 0.33 (`yowasp-yosys==0.33.0.0.post574`) is planned and not yet
  verified (task T004).
- Table 4, row "New, one stage, at most 3 in series and 12 transistors": we measure 6, the
  handout says 5. The six functions are listed in `results/m1/redundancy/self_test.json`; the
  question is open with the TA (research Q-1).
- No candidate costing, area model, Liberty writer, extended-library mapping, mapping-vs-RTL
  cec or OpenSTA yet (M2). (ABC cec is already used to check each restructured AIG against its
  synth AIG.)
- The agent layer has no model yet: tools, policy and logs are exercised by a scripted run.
- Option 1 (cell generation) is not started in this repository. For an Option 3 group, cp1 also
  grades Option 1's inv_1 and nand2_1 at 2.72 um; that work, the course container and the ngspice
  stress test in `make check` are open.
- Two broken cases in `tests/broken_proposed/` wait for a human to review and promote them.

## 10. Third-party files
- `given/` (linked, not copied): the course student pack, including the designs, each under
  its own licence notice (BSD, GPL-2, LGPL-2.1 or the author's own).
- `docs/interface/*_example.json`: from the course `repo_template`.
- `tests/broken/wrong_truth_table.aig`: generated by Yosys from the course design `cpu8.v`.
- SKY130 PDK (Apache-2.0), used through the `pdk` link, never copied.
