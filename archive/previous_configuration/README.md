# Project 1, Option 3: DD2 Cell Finder

## 1. Group
<names and student IDs, to be filled in by the group; commit authors so far: Omar Abdel Motalb,
Mohamed Azouz, Noor Elshahidi> · Option 3 (Options 1 and 2, connected) · AI used as an agentic system
(LangGraph planned; at cp1 the wrapped tools, read-only checks and run logs exist, see section 8)

## 2. Quick start
Tools used for the evidence: the `dd2-flow` image (`docker/flow.Dockerfile`, Ubuntu 24.04):
Yosys 0.33 (git 2584903a060) with its yosys-abc, Python 3.12. Icarus Verilog 13.0 on the host.
SKY130A via ciel (`dd7771c…`). The course image `dd2-layout-tools`: Magic 8.3.684, Netgen (reports
1.5.132), ngspice 47 with the BSIM4 fix (stress test passes; `make check` records its SHA256).
GDSfactory 9.51.0 and KLayout 0.30.12 (Python, for Option 1). Host Yosys 0.70 also runs everything, but
only Linux Yosys 0.33 reproduces the handout's Table 1 exactly (research D-2).

    make setup        # links pdk/ and given/, creates .venv with pytest
    make docker-flow  # once: builds dd2-flow (Yosys 0.33)
    make check        # tools, PDK, supplied inputs
    make m1-docker    # the M1 flow inside dd2-flow: writes results/m1 (about 1 minute)
    make test         # host test suite; make test-docker runs it inside dd2-flow

`make all` runs the Option 2 flow inside `dd2-flow` when that image exists (otherwise on the host
Yosys, and Table 1 is then labelled NOT REPRODUCED), then `o1-rules` and `o1-m1`, which need Docker
with the course image. On the verification run of a clean clone (2026-10-27): setup 40 s (new venv
with GDSfactory), check about 1 s, test about 93 s (177 tests), all 134 s, agent-check 42 s.

Any
Python >= 3.11 works; uv picks the newest one installed, and `results/m1/environment.json` records
which one was used.

`make setup` expects `PDK_ROOT` (default `~/.ciel`, containing `sky130A`) and
`GIVEN` (default `../DD2_Project1_student_pack/given`). Nothing is copied.

## 3. What the tool does
Option 2 finds the small Boolean functions a synthesized design computes again and again and
checks which of them SKY130 HD lacks; Option 1 builds Boolean functions as HD-compatible cells.
Option 1 (`src/cellgen`, at Milestone 1): read an Appendix A request and check expression against
truth table; build a single static CMOS stage (pull-down from a series-parallel formula, pull-up as
its dual, at most 3 in series) and check it at switch level; order the gates by a paired Euler path;
draw the cell with GDSfactory inside the frame of `plan_hd.json` (li1 wiring, met1 rails only);
then check it with Magic DRC (alone and in rows of HD cells: side by side, mirrored, next to itself,
flipped onto a shared rail), Netgen LVS (against its schematic and the installed HD cell), the
layer check, ngspice on the RC-extracted netlist and Icarus on the Verilog model; and compare it
with the installed cell. Option 2 (`src/dd2`) at Milestone 1 runs in this order: (1) map every required design onto the usable and the
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
| `make o1-image` | the student pack's `container/` | the course image `dd2-layout-tools` (Magic, Netgen, fixed ngspice) |
| `make o1-rules` | `src/cellgen/rules.py` | `results/option1/rules.csv`: every layout number with its design rule |
| `make o1-m1` | installed HD cells, `plan_hd.json` | `cells/dd2_ref__{inv_1,nand2_1}/` (GDS, schematic, extracted and RC netlists, Verilog, report, comparison SVG) and `results/option1/m1/` |
| `make agent-check` | cpu8 | `ai/runs/<run>.jsonl`, `ai/runs/<run>.checks.json`; tool outputs in `runs/<run>/` |
| `make demo IN=<design.v> [TOP=<top>] [SV=1]` | any Verilog design | `build/demo/<name>/` (never touches `results/`) |
| `make demo IN=<request.json>` | an Appendix A request | `build/demo/cells/<name>/`, including `response.json` |
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
- `src/cellgen/`: Option 1, the cell generator (request reader, networks, Euler ordering, layout,
  router, DRC/LVS/abutment/layer checks, simulation, comparison)
- `cells/`: one folder per generated cell (cp1: the regenerated `dd2_ref__inv_1`, `dd2_ref__nand2_1`)
- `libs/`: Option 2 Liberty files (from M2)
- `ai/`: AI use and mistakes logs; `ai/runs/` agent run logs; `runs/` the outputs those logs point to
- `specs/001-agentic-cell-finder/`: specification, plan, research, contracts and tasks (Spec Kit)
- `report/`: reports (at submission)

## 6. Results
<!-- m1-summary:start -->
| cp1 requirement | Evidence | Status |
|---|---|---|
| Environment (make check) | `results/m1/environment.json` | pass |
| Table 1: 24 mappings measured (research D-2) | `results/m1/table1.csv` | pass |
| AIGs of every required design, synth and restructured: 12 artifacts | `results/m1/aigs/manifest.json` | pass |
| Cut enumerator passing its check: 423381 cuts, 0 failures | `results/m1/cuts/summary.csv` | pass |
| Class table of HD: 323 cells, 40 PN classes, 19 NPN classes | `results/m1/hd_classes.csv` | pass |
| Redundancy self-test: 323/323 HD cells Exists; Table 4 below | `results/m1/redundancy/self_test.json` | pass on rows 1-5 and 7; row 6 open (Q-1) |
| Agentic rows: tools wrapped, checks read-only, runs logged | `ai/runs/A-1027-02.checks.json` | pass |
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

Table 1 (um^2, Yosys 0.33; the handout's Yosys 0.33 values for comparison):

| Design | Script | Usable | Reduced | Reduced vs usable | Handout reduced | Ours vs handout |
|---|---|---:|---:|---:|---:|---:|
| cpu8 | A | 4186.5 | 4186.5 | +0.00% | 4186.5 | +0.00% |
| cpu8 | B | 4367.9 | 4359.2 | -0.20% | 4359.2 | -0.00% |
| dsp8 | A | 5928.2 | 5928.2 | +0.00% | 5928.2 | -0.00% |
| dsp8 | B | 6217.2 | 6214.7 | -0.04% | 6214.7 | +0.00% |
| arlet6502 | A | 9654.3 | 9701.8 | +0.49% | 9701.8 | +0.00% |
| arlet6502 | B | 9954.5 | 9995.8 | +0.41% | 9995.8 | +0.00% |
| uart_apb | A | 12948.7 | 12948.7 | +0.00% | 12948.7 | -0.00% |
| uart_apb | B | 13180.1 | 13180.1 | +0.00% | 13180.1 | +0.00% |
| risc8 | A | 28265.9 | 28263.4 | -0.01% | 28263.4 | -0.00% |
| risc8 | B | 27501.4 | 27511.4 | +0.04% | 27511.4 | -0.00% |
| fir10 | A | 25968.7 | 25968.7 | +0.00% | 25968.7 | -0.00% |
| fir10 | B | 29055.4 | 29055.4 | +0.00% | 29055.4 | -0.00% |

Cuts per AIG:

| Design | Variant | ANDs | Cuts | Failures | PN classes | NPN classes |
|---|---|---:|---:|---:|---:|---:|
| cpu8 | synth | 1265 | 10725 | 0 | 195 | 63 |
| cpu8 | restructured | 1112 | 9048 | 0 | 197 | 60 |
| dsp8 | synth | 1973 | 16445 | 0 | 200 | 54 |
| dsp8 | restructured | 1533 | 13047 | 0 | 194 | 50 |
| arlet6502 | synth | 3221 | 27091 | 0 | 205 | 51 |
| arlet6502 | restructured | 2738 | 20766 | 0 | 208 | 61 |
| uart_apb | synth | 4673 | 39290 | 0 | 203 | 45 |
| uart_apb | restructured | 2971 | 17935 | 0 | 135 | 38 |
| risc8 | synth | 7750 | 57178 | 0 | 173 | 45 |
| risc8 | restructured | 6598 | 44225 | 0 | 174 | 47 |
| fir10 | synth | 8795 | 92196 | 0 | 176 | 43 |
| fir10 | restructured | 6937 | 75435 | 0 | 170 | 43 |
<!-- m1-summary:end -->

Option 1 Milestone 1 (generated by `make o1-m1` from `results/option1/m1/`):

<!-- o1-summary:start -->
| cp1 requirement | Evidence | Status |
|---|---|---|
| HD frame checked against installed inv_1 and nand2_1 | `results/option1/m1/frame_check.json` | pass |
| inv_1 regenerated at 2.72 um (3 sites): DRC 0 in a tap row, LVS match (vs installed: match), abutment 0 errors in 4 fixtures, layers pass, SPICE pass, model pass | `results/option1/m1/inv_1.json`, `cells/dd2_ref__inv_1/` | pass |
| nand2_1 regenerated at 2.72 um (3 sites): DRC 0 in a tap row, LVS match (vs installed: match), abutment 0 errors in 4 fixtures, layers pass, SPICE pass, model pass | `results/option1/m1/nand2_1.json`, `cells/dd2_ref__nand2_1/` | pass |
| Request reader (accept example; refuse mismatch, 5 inputs, bad operator) | `results/option1/m1/request_reader.json` | pass |
| Network check on the 11 single-stage test functions | `results/option1/m1/network_check.csv` | pass |
<!-- o1-summary:end -->

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
| Option 1 network check | a deleted pull-up (floating Y) and a VPWR-VGND short (`tests/unit/test_cellgen_network.py`) |
| Option 1 layer check | hvtp removed, npc removed (`tests/unit/test_cellgen_layers.py`) |
| Option 1 DRC | gate A moved 0.08 um towards B: poly.2 must fire (`tests/integration/test_cellgen_broken.py`) |
| Option 1 LVS | wrong NMOS width; inputs swapped on every gate; series order swapped (all must mismatch) |
| Option 1 abutment | the row without its tap must fail nwell.4 |
| Option 1 transistor-level simulation | one pull-up deleted from the extracted netlist (handout 4.2) |
| Option 1 model-level simulation | a Verilog model with one wrong truth-table row (handout 4.2) |
| Request reader | a truth table that disagrees with the expression; 5 inputs; an unknown operator |

`tests/broken/SHA256SUMS` makes any edit to a broken case fail the suite.

## 8. AI use
AGENTS.md · ai/use_log.md · ai/mistakes_log.md · ai/runs/ · report/ai_report.pdf (at submission)

## 9. Limitations
- Table 1 and the handout's AIG AND counts reproduce exactly only with Linux Yosys 0.33
  (`make m1-docker`). Host Yosys 0.70 differs by up to 4.5%, and the macOS/WebAssembly builds of 0.33
  also differ on script A, because ABC's results depend on the platform (research D-2).
- Table 4, row "New, one stage, at most 3 in series and 12 transistors": we measure 6, the
  handout says 5. The six functions are listed in `results/m1/redundancy/self_test.json`; the
  question is open with the TA (research Q-1).
- No candidate costing, area model, Liberty writer, extended-library mapping, mapping-vs-RTL
  cec or OpenSTA yet (M2). (ABC cec is already used to check each restructured AIG against its
  synth AIG.)
- The agent layer has no model yet: tools, policy and logs are exercised by a scripted run.
- Option 1 at cp1 builds single-stage cells only, with one finger per row (HD sizing). Multi-stage
  cells, stack sizing, RC-LVS, the characterizer, Liberty and the round trip are cp2/cp3 work.
- The li1 router handles inv_1 and nand2_1; wide single stages with repeated inputs (such as the
  Appendix A example maj4n) do not route yet, so `make demo IN=docs/interface/request_example.json`
  returns a `fail` response that names the failed checks (cp2 work).
- The PDK's HD library had lost its gds, spice, cdl, lef, mag and maglef views. They were restored
  from the identical ciel release (all 894 files byte-identical to it); `make check` now requires
  them. A group member should confirm this with ciel.
- The installed nor2_1 and a21oi_1 put a different input next to Y in their series stacks than
  the generator's convention; reference regeneration at cp2 must follow the installed order.
- The course image reports Netgen 1.5.132 although the student-pack recipe checks out tag 1.5.133.
- Two broken cases in `tests/broken_proposed/` are exercised by the tests but not yet moved into
  `tests/broken/` (that move and the checksum update are left to a group member).

## 10. Third-party files
- `given/` (linked, not copied): the course student pack, including the designs, each under
  its own licence notice (BSD, GPL-2, LGPL-2.1 or the author's own).
- `docs/interface/*_example.json`: from the course `repo_template`.
- `tests/broken/wrong_truth_table.aig`: generated by Yosys from the course design `cpu8.v`.
- SKY130 PDK (Apache-2.0), used through the `pdk` link, never copied.
