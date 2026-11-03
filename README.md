# Project 1, Option 3: DD2 Cell Finder

Group **GB4**, cell prefix `dd2_g4__` · Option 3 (Options 1 and 2, connected).
Omar Abdel Motalb, 900232118; Noor Elshahidi; Mohamed Azouz; the other members' names and IDs still need to be listed.

**For the TA:**
- Option 2, Milestone 2: open [TA_M2/README.md](TA_M2/README.md), with its figures, tables and the Table 4 question.
- Option 1, Milestone 2: section 6 below, and [results/option1/m2/](results/option1/m2/).
- The studio and the agent: [web/README.md](web/README.md) and [docs/roadmap.md](docs/roadmap.md).

AI is used as a development aid, and in Option 1 as a bounded agent that picks generator settings.
Option 2's flow runs no model and needs no API key.

## 1. Status

- **Option 2, Milestone 2:** the saved WSL experiment passes mapping, equivalence, timing and
  tutorial-simulation checks ([readiness.json](results/m2/readiness.json)). Readiness stays false while
  Table 4 gives six verified one-stage classes against the handout's five. No TA acceptance is assumed.
  Measured savings can be zero or negative, and are shown as they are.
- **Option 1, Milestone 2:** reference cells, multi-stage cells, characterizer and test cells, in
  section 6.
- **Option 3:** connected through the Appendix A format in `docs/interface/`. `make o3` has Option 1 build,
  check and characterize every cell Option 2 requests (`src/cellgen/deliver.py`), and only cells that pass,
  with their Liberty, replace the estimated ones when Option 2 remaps (`src/dd2m2/option3.py`,
  `results/option3/`). The M2 evidence in `results/m2/` is left as it is.

## 2. Setup

The team works on macOS and on Ubuntu/WSL. Use Python >= 3.11.

- **Option 2:** recent OpenSTA, Yosys >= 0.34 and Icarus >= 13. `tools/install_course_tools.py` installs the
  SHA256-pinned OSS CAD Suite. Keep Ubuntu's Yosys 0.33 and its ABC separately for the Milestone 1 reference
  table, or use the `dd2-flow` image (`make docker-flow`, then `make m1-docker`).
- **Option 1:** Docker (Colima on macOS) with the course image `dd2-layout-tools` (`make o1-image`) and
  OpenSTA in `dd2-sta` (`make o1-sta`).

Course inputs stay outside Git, and `make setup` links them:

- `GIVEN`: the student pack's `given/`.
- `PDK_ROOT`: the directory holding `sky130A`.
- `TUTORIALS`: `spm/` and `multiplier/`, the original Tutorial 4 and Tutorial 2 sources and testbenches.
  Keep their licence notices.

```sh
make setup
.venv/bin/python tools/install_course_tools.py   # Option 2 tools
make group                                        # once: the DD2 group number
make check
make test
make all
```

## 3. What the tool does
Option 2 finds the small Boolean functions a synthesized design computes again and again and
checks which of them SKY130 HD lacks; Option 1 builds Boolean functions as HD-compatible cells.
Option 1 (`src/cellgen`, at Milestone 2): read an Appendix A request and check expression against
truth table; build one static CMOS stage when Y allows it, or the fewest-transistor chain of stages
found otherwise (pull-down from a series-parallel formula, pull-up as its dual, at most 3 in series)
and check it at switch level; size it (hd, or stack with folded fingers); order the gates by a paired
Euler path; draw the cell with GDSfactory inside the frame of `plan_hd.json` (li1 wiring, met1 for
the rails, and in a multi-stage cell only where li1 fails); then check it with Magic DRC (alone and
in rows of HD cells: side by side, mirrored, next to itself, flipped onto a shared rail), Netgen LVS
and RC-LVS (against its schematic and, for reference cells, the installed HD cell), the layer check,
ngspice on the RC-extracted netlist with SA and SB and Icarus on the Verilog model; and compare it
with the installed cell. The characterizer writes Liberty tables from ngspice; on the installed cells it
is checked against the shipped Liberty (Table 5). Option 2 at Milestone 1 (`src/dd2`) runs in this order: (1) map every required design onto the usable and the
reduced HD library with ABC scripts A and B (Table 1); (2) write each design as an AIG, once as
synthesized and once restructured by ABC; (3) enumerate every cut of up to 4 inputs with its
truth table, and check each one by simulating its cone for every input combination; (4) build the
class table of HD; (5) classify functions as Exists / Exists with an inverter / Contained / New
against the full HD library, and self-test that checker against Table 4 of the handout. Option 2 at Milestone 2 (`src/dd2m2`) costs each
candidate, fits an area model on the HD x1 cells and reports its held-out error, ranks candidates by
mapped-cone savings, writes cell requests and an extended Liberty, maps every benchmark with and without
the new cells using the same A/B scripts, proves each mapping with ABC cec, compares timing with OpenSTA,
and runs the original tutorial testbenches on the mapped netlists.

## 4. Commands

| Command | Purpose |
|---|---|
| `make setup`, `make group` | Links `pdk/`, `given/`, `tutorials/`; the Python env; the group number |
| `make check`, `make check-versions` | Both options' tools and inputs; strict minimum versions for Option 2 |
| `make test` | Every test, and the frozen broken-case hashes |
| `make all` | Option 2 M1 and M2, then Option 1 M1 and M2 |
| `make m1` / `make m1-docker` | Option 2 M1 with the reference Yosys 0.33 (Table 1, AIGs, cuts, HD classes, redundancy) |
| `make m2` | Option 2 M2: six benchmarks plus tutorials, estimated cells, CEC, timing, GLS and plots |
| `make ta` | Refresh `TA_M2/` from saved results, without rerunning anything |
| `make readiness` | Print Option 2's recorded blockers; nonzero while any remain |
| `make o1-m1`, `make o1-m2` | Option 1 M1 and M2 into `cells/` and `results/option1/` |
| `make o3`, `make o3-cells`, `make o3-map` | Option 3: Option 1 builds Option 2's requests, then Option 2 remaps with the cells that passed, into `results/option3/` |
| `make agent FUNC='<expression>'`, `make fixed FUNC=...`, `make agent-compare` | The Option 1 agent, its fixed-choice version, and the comparison |
| `make agent-server`, `make web` | The studio's back end and front end |
| `make demo IN=<design.v> [TOP=<top>]` | Option 2 on any design, into `build/demo/` |
| `make demo IN=<request.json>` | Option 1 on an Appendix A request, with its `response.json` |

Every Option 2 step also has its own target (`m2-fit`, `m2-candidates`, `m2-map` and so on). On another
installation, set `REFERENCE_YOSYS` and `REFERENCE_ABC` when the reference binaries are elsewhere.

## 5. Layout

| Folder | Purpose |
|---|---|
| [TA_M2/](TA_M2/) | Option 2 M2 for the TA meeting: figures, key tables, Table 4 evidence |
| [src/dd2/](src/dd2/), [src/dd2m2/](src/dd2m2/) | Option 2: M1 functions and checks; M2 costing, ranking, requests, Liberty, mapping, proofs, timing |
| [src/cellgen/](src/cellgen/) | Option 1: the cell generator and its checks |
| [agent/dd2_agent/](agent/dd2_agent/), [web/](web/), [prompts/](prompts/) | The agent, the studio, and the versioned prompts |
| [tests/](tests/) | Unit, contract and integration tests, `tests/m2/` for Option 2 M2, frozen broken cases |
| [results/](results/) | `m1/`, `m2/` for Option 2; `option1/` for Option 1 |
| [cells/](cells/), [libs/](libs/) | Generated cells; generated Liberty files |
| [docs/](docs/) | `interface/` (Appendix A), `roadmap.md`, `option2-m2-plan.md`, `architecture.md` |
| [specs/](specs/) | Spec Kit specification, plan, research and tasks |
| [config/](config/) | Group number, agent settings; host-specific tool selection is ignored by Git |
| [tools/](tools/) | Pinned Option 2 tool installer |
| [ai/](ai/) | AI use and mistakes logs, `ai/runs/` agent run logs; `runs/` their outputs |

## 6. Results

Option 2: Milestone 1 in [results/m1/summary.md](results/m1/summary.md), Milestone 2 in
[TA_M2/README.md](TA_M2/README.md) and [results/m2/](results/m2/). Both are generated from the saved records.

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

Option 1 Milestone 2 (generated by `make o1-m2` from `results/option1/m2/`):

<!-- o1-m2:start -->
| cp2 requirement | Evidence | Status |
|---|---|---|
| Six reference cells pass every Table 4 must-match row (6 of 6) | `results/option1/m2/table4.csv`, `results/option1/m2/references/` | pass |
| a21o_1 and mux2_1 built and compared: a21o_1 8 T vs 8 T, 7 vs 6 sites, LVS vs installed match (reported); mux2_1 12 T vs 12 T, 10 vs 9 sites, LVS vs installed mismatch (reported) | `results/option1/m2/references/` | pass |
| Characterizer against the shipped Liberty: 2744 entries of the six cells, median 2.368%, max 152.724% with the fixed ngspice; median 3.727%, max 71.68% with stock | `results/option1/m2/table5.json` | pass |
| Median per cell, fixed ngspice: a21oi_1 1.899%, inv_1 1.471%, nand2_1 2.55%, nand3_1 3.082%, nor2_1 2.347%, o21ai_1 2.642% | `results/option1/m2/table5.json` | pass |
| Input capacitance within 10%, Liberty loads in Yosys and OpenSTA, full-ramp broken case flagged | `results/option1/m2/table5.json` | pass |
| SPM with the six cells swapped in, worst delay change: script A 0.0129 ns (1.649%), script B 0.0043 ns (0.562%) | `results/option1/m2/table5.json` | pass |
| Test cells generated, verified and simulated (19 of 19, the extra one being the stack nor3) | `results/option1/m2/test_cells.csv`, `cells/` | pass |
| Agent (codex-cli:gpt-5.6-sol effort=high) and its fixed-choice version on the test cells: agent runs passing 2 of 2, fixed 3 of 3 | `results/option1/m2/agent_vs_fixed.csv`, `ai/runs/` | pass |
<!-- o1-m2:end -->

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
| Option 1 RC-LVS | one wrong connection in the RC netlist, and a net opened by removing its resistors, must mismatch (`tests/integration/test_cellgen_broken.py`) |
| Option 1 abutment | the row without its tap must fail nwell.4 |
| Option 1 comparison with HD | a moved frame, a met1 wire, a wrong pin layer (`tests/unit/test_cellgen_compare.py`) |
| Option 1 generator self-check | a contact that is not square stops the layout (`tests/unit/test_cellgen_stages.py`) |
| Option 1 SA and SB | a device with no geometry is an error (`tests/unit/test_cellgen_stress.py`) |
| Option 1 characterizer | tables indexed by the full ramp must be flagged (Table 5, `results/option1/m2/table5.json`) |
| Option 1 agent decisions | every forbidden action, malformed replies and repeated settings are refused; a failed cell cannot become a pass; the cost limit stops a run (`tests/unit/test_agent_graph.py`) |
| Option 1 transistor-level simulation | one pull-up deleted from the extracted netlist (handout 4.2) |
| Option 1 model-level simulation | a Verilog model with one wrong truth-table row (handout 4.2) |
| Request reader | a truth table that disagrees with the expression; 5 inputs; an unknown operator |

`tests/broken/SHA256SUMS` makes any edit to a broken case fail the suite.

## 8. Checks and limits of Option 2

Every cut is checked against exhaustive cut simulation. Redundancy compares against the full HD combinational
library. New candidate stages have at most three transistors in series; native HD calibration permits
four-stack cells. Cost features describe explicit realizations, not extracted HD transistor counts. The fitted
model covers HD x1 cells with up to four inputs and reports held-out error.

ABC CEC checks RTL-derived gold against the mapped circuits with named state cutpoints; a separate bounded Yosys
induction attempt is diagnostic. Tutorial GLS runs the original testbenches with functional models from the exact
mapping Liberty: zero-delay functional simulation, without SDF or timing checks. M1 reference numbers and M2
newer-tool numbers are distinct experiments.

## 9. AI use
AGENTS.md · ai/use_log.md · ai/mistakes_log.md · ai/runs/ · report/ai_report.pdf (at submission)

## 10. Limitations
- Table 1 and the handout's AIG AND counts reproduce exactly only with Linux Yosys 0.33
  (`make m1-docker`). Host Yosys 0.70 differs by up to 4.5%, and the macOS/WebAssembly builds of 0.33
  also differ on script A, because ABC's results depend on the platform (research D-2).
- Table 4, row "New, one stage, at most 3 in series and 12 transistors": we measure 6, the
  handout says 5. The six functions, with their networks, are in `TA_M2/TABLE4_CLARIFICATION.md`; the
  question is open with the TA.
- Option 2's M2 areas use estimated cells, and the new cells' timing and capacitance are placeholders:
  OpenSTA gives pre-layout comparisons. Real Option 1 cells replace them in the Option 3 loop.
- The Option 1 agent reaches GPT-5.6 Sol through Codex CLI (`agent/dd2_agent/codex_cli.py`), with every
  tool off and any tool use refused, because the instructor has not named a provider (research Q-2). The
  overview allows an API key or a local model and forbids running inside an interactive coding
  assistant, so a group member should confirm this headless use with the TA.
- Option 1 has no Liberty for the generated cells yet, no response writer and no round trip (cp3); the
  characterizer exists and has passed Table 5, and `make o1-m2` uses it for Table 4's timing row.
- Several generated cells are wider than HD's. HD jogs its poly stripes and widens npc locally; the
  generator keeps straight stripes and the frame's npc band. `results/option1/m2/table4_notes.md` and
  `test_vs_hd.csv` list them.
- The RC netlists come from `extresist simplify off`, because Magic otherwise drops the resistors of every
  net that is small next to a transistor. `eda.count_caps_once` removes the substrate capacitance that
  extresist then writes twice. Input capacitance is measured between the Liberty's slew thresholds at
  the middle of the table; the shipped Liberty does not say how its values were measured.
- The characterizer picks an arc's slowest side input once, by delay at the middle of its table.
- met1 appears inside a multi-stage cell only after every li1 attempt failed, within a bounded search:
  a wider li1-only layout may exist beyond it. `results/option1/m2/test_cells.csv` names those nets.
- The layout search is exhaustive only within its budget, so a function given at the demo can fail to
  route. The cell then fails its check and the report names the nets.
- The PDK's HD library had lost its gds, spice, cdl, lef, mag and maglef views. They were restored
  from the identical ciel release (all 894 files byte-identical to it); `make check` now requires
  them. A group member should confirm this with ciel.
- The course image reports Netgen 1.5.132 although the student-pack recipe checks out tag 1.5.133.
- Two broken cases in `tests/broken_proposed/` are exercised by the tests but not yet moved into
  `tests/broken/` (that move and the checksum update are left to a group member).

## 11. Final milestone

Option 2: real generator cells from Option 1, greedy final selection, real-area reruns, the cell-by-cell curve, the
30% sensitivity experiment. Option 1: every test cell characterized with its Liberty cell, Verilog model and
response, the round trip, and a small design mapped, simulated and timed. Both: final technical and AI reports, and
the full unseen-input demo.

## 12. Third-party files
- `given/` (linked, not copied): the course student pack, including the designs, each under
  its own licence notice (BSD, GPL-2, LGPL-2.1 or the author's own).
- `docs/interface/*_example.json`: from the course `repo_template`.
- `tests/broken/wrong_truth_table.aig`: generated by Yosys from the course design `cpu8.v`.
- SKY130 PDK (Apache-2.0), used through the `pdk` link, never copied.
