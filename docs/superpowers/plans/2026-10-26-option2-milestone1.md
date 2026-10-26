# Option 2 Milestone 1 Implementation Plan

> **Superseded (2026-10-26)** by `specs/001-agentic-cell-finder/` (plan.md, research.md, tasks.md). Research there found facts this plan lacks: Yosys 0.70 does not reproduce Table 1, `dch` leaves choice nodes, and the student pack is committed.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a reproducible Option 2 flow that meets every Checkpoint 1 / Milestone 1 requirement while preserving the interfaces and evidence needed to complete both Options 1 and 2 later.

**Architecture:** The repository will contain a Python-based Option 2 pipeline. It will synthesize a design into two AIG variants, enumerate and validate <=4-input cuts, classify Boolean functions, and compare candidate functions against the complete HD Liberty library. Commands write machine-readable evidence under `results/`; tests decide success. Option 1 is deliberately not implemented in this milestone, but its request/response contract is fixed now so that its later cell generator can consume Option 2 candidates without redesign.

**Tech Stack:** Python 3.11+, Yosys/ABC 0.34+, Icarus Verilog 13+, SKY130 PDK, supplied Liberty/design files, Make, and OpenSTA later for timing.

**Spec:** This document is the working synthesis of the three project handouts: `DD2 Project 1 - Overview and Rules.pdf`, `DD2 Project 1 - Option 1 - From a Boolean Function to an HD Cell.pdf`, and `DD2 Project 1 - Option 2 - Finding Cells Worth Adding.pdf`.

## Global Constraints

- The group is a five-student Option 3 group: it must eventually implement **both** Option 1 and Option 2, joined through the Appendix A request/response interface. The current implementation scope is **Option 2, Milestone 1 only**.
- Option 2 starts from `hd_reduced.lib` (189 cells), not the full 428-cell HD library. The full combinational HD Liberty library is still required for redundancy checks.
- Every required mapping uses `synth -flatten`, `dfflibmap`, `abc`, `opt_clean -purge`, and `stat`; only the library and ABC script may vary.
- Script A is `+strash;dch,-f;amap;topo`. Script B is `+strash;&get,-n;&dch,-f;&nf,-R,1000;&put`.
- A candidate function has at most four inputs and one output. A cut enumerator must independently simulate every input assignment to validate its truth table.
- AI never decides pass/fail, changes check scripts, broken cases, or the PDK. Numbers in reports must come from saved flow outputs.
- Keep `AGENTS.md`, `ai/use_log.md`, and `ai/mistakes_log.md` current. AI-assisted commits require an `AI-assisted: <tool>/<model>` trailer.
- Do not commit the PDK, copies of `given/`, build trees, or files over 50 MB. `make setup` links the PDK and supplied files; reports cite committed evidence in `results/`.
- Tags `cp1`, `cp2`, and `final` are immutable after their respective deadlines. Do not move them.
- Preserve each supplied design's license notice; read `pic1826.v` with SystemVerilog mode.

## Review Focus

- A cut whose fan-in cone includes complemented edges, repeated leaves, or fewer than four distinct leaves must still receive the correct canonical truth table; test this in Task 4.
- A deliberately corrupted truth table must make the cut-validation check fail; test this in Task 4.
- An ordinary combinational HD cell, including a non-x1 drive, must be classified `Exists`; test this in Task 5.
- A function matching HD only after output/input inversion or tying a candidate input to 0/1 must not be reported as `New`; test this in Task 5.
- A missing tool, PDK path, given-file link, or invalid Liberty input must make `make check` fail clearly rather than silently producing partial evidence; test this in Tasks 1 and 2.

---

## 1. Repository Status and Source of Truth

The repository currently contains the supplied student pack and a root `AGENTS.md`; it has not yet been populated from `repo_template/`. The supplied pack is the source of inputs and templates, and must remain external to the implementation's generated artifacts. Before implementation, copy/adapt the template's repository layout rather than committing duplicate PDK or `given/` content.

The root `AGENTS.md` makes these current rules enforceable:

- Option 2 finds repeated Boolean functions, identifies functions absent from SKY130 HD, and measures custom-cell savings using Python, Yosys/ABC, and OpenSTA.
- `make check` validates the environment; `make test` covers correctness and deliberately broken cases.
- Results evidence belongs in `results/`; AI-use evidence belongs in `ai/`.

### Required repository layout

| Path | Responsibility |
| --- | --- |
| `README.md` | Required user-facing project documentation in the prescribed ten-section order. |
| `AGENTS.md` | AI constraints and verification policy; already present, refine only when the project checks are concrete. |
| `Makefile` | `setup`, `check`, `test`, `all`, `demo`, and `clean`. |
| `src/` | Option 2 implementation. |
| `tests/` | Unit/integration checks; `tests/broken/` contains intentionally failing inputs. |
| `results/` | Committed tables, manifests, logs, AIG statistics, and other report evidence. |
| `libs/` | Liberty files generated by Option 2 (later milestones). |
| `cells/` | One folder per Option 1 generated cell (later milestones). |
| `docs/interface/` | Stable JSON request/response examples and interface notes. |
| `ai/` | Use and mistakes logs, and later agent-run logs if an agentic system is chosen. |
| `report/` | Technical/AI report PDFs and their sources at submission. |

## 2. Full Project Scope

### 2.1 The combined system (Option 3)

Option 2 discovers which missing functions are likely worth adding; Option 1 turns an accepted request into a physically verified HD-compatible cell. The closed loop is:

```text
RTL designs -> synthesize / AIG / cuts -> classify, cost, rank (Option 2)
         -> request JSON -> layout + verification + characterization (Option 1)
         -> response JSON + one Liberty cell -> extended library -> remap and measure (Option 2)
```

Until Checkpoint 2, Option 2 uses estimated cell areas and Option 1 works on test cells. In week 3, Option 1 builds Option 2's three to five best candidates; Option 2 replaces their estimated Liberty entries one-for-one with returned real cells and repeats the measurements.

### 2.2 Option 1: later work, but fixed requirements now

Option 1 accepts any one-output function of up to four inputs as an expression or truth table and produces an HD-compatible cell with GDS/layout, schematic/extracted netlist, Liberty, Verilog model, report, and response JSON.

Important constraints for the later generator:

- All cells are 2.72 um tall and an integral number of 0.46 um sites wide. The supplied `plan_hd.json` frame, rails, wells, implants, and fixed bands must not move.
- Build static-CMOS stages with no more than three transistors in series in either network. Use one stage when possible; otherwise decompose into stages/inverters.
- Use HD conventions: `nfet_01v8` (0.65 um) and `pfet_01v8_hvt` (1.00 um) for the HD sizing baseline; li1 internally, met1 rails; pins `A` through `D`, `Y`, `VGND`, `VNB`, `VPB`, `VPWR`; HD SPICE port order.
- Verify DRC=0, LVS, RC-LVS, layer coverage, abutment against tap/inverter/fill cells, switch/transistor/model-level function, and Liberty syntax. Test a deliberately removed pull-up and an incorrect Verilog truth-table row.
- Before novel cells, rebuild and compare `inv_1`, `nand2_1`, `nor2_1`, `nand3_1`, `a21oi_1`, and `o21ai_1`; generated novel cells wait until required comparisons pass.
- Characterization is TT, 1.8 V, 25 C using the course's fixed ngspice, HD thresholds, 20-80% input slew, HD loads, per-pin/side-input cases, capacitance, timing sense, and BSIM4 stress distances. Validate all six reference cells before characterizing generated cells.

Option 1 milestones later are: M1 - checked HD frame plus regenerated `inv_1` and `nand2_1`; M2 - six reference comparisons, multi-stage cells, validated characterizer, test cells; M3 - characterized test cells, round-trip mapping/timing, and all deliverables.

### 2.3 Option 2: full end-to-end requirements

1. **Baseline mapping.** Map every listed design using the reduced library and both fixed ABC scripts. Reproduce Table 1 for the six required designs before claiming any custom-cell saving.
2. **AIG extraction.** After Yosys synthesis, create AIGER with `aigmap` and `write_aiger`. For asynchronous-reset flip-flops, use `async2sync` and `dffunmap`. Also write an ABC-restructured AIG (for example, `strash; dch`) and compare both variants.
3. **Cut enumeration.** Enumerate cuts of up to four inputs in project code. Compute a truth table for every cut and validate it by simulating the cut's logic over every assignment.
4. **Classification.** Group functions up to input permutation and output inversion; additionally count NPN classes. The former is the CMOS-relevant count because input inversions cost transistors in CMOS.
5. **Cost model.** Estimate stages, input/output inverters, and transistor count, constrained to at most three devices in series per stage. Fit an area model to HD x1 cells and report its fit error.
6. **HD redundancy.** Compare candidates with every single-output combinational cell in the **full** HD Liberty library, across drives and kinds: `Exists`, `Exists with an inverter`, `Contained`, or `New`.
7. **Ranking and selection.** Estimate saving from currently mapped replaced cells minus candidate cost. Greedily add the next candidate, remap, retain only if total area over required designs falls, and stop at ten cells or no further benefit.
8. **Library and request generation.** Add new cells to the same library group as `hd_reduced.lib`; each needs estimated/real area, directions, capacitance, Boolean function, and one timing group per input. Write a request for each chosen candidate.
9. **Measurement and validation.** Map baseline/extended libraries with scripts A/B, use ABC CEC and Tutorial 4 gate-level testbenches, report same-script and best-of-both reductions, new-cell instances, worst OpenSTA delay, estimated-versus-real results, cell-by-cell curve, and a 30%-smaller sensitivity cell experiment.

### 2.4 Inputs and baseline facts

The required designs and top modules are `cpu8/cpu8`, `dsp8/dsp8`, `arlet6502/cpu`, `uart_apb/uart_apb_master`, `risc8/cpu`, and `fir10/fir10`. Optional designs are `p16c5x/P16C5x`, `pic16/PIC16C5x`, `x18/x18`, `pic1826/cpu` (SystemVerilog), `xfir/xfir`, and `chacha/chacha`.

The reduced library has 189 cells: ordinary logic x1/x2, inverter/buffer x4/x8, and x1 full/half adders plus 17 non-scan flip-flops/latches. It excludes clock, delay, tri-state, scan, low-power, certain enable flops, and physical-only cells. The usable comparison library has 307 cells. The full HD library is used for redundancy only, never as the Option 2 baseline.

Table 1 baseline areas to reproduce (um2, Yosys 0.33) are:

| Design | A usable | A reduced | B usable | B reduced |
| --- | ---: | ---: | ---: | ---: |
| cpu8 | 4,186.5 | 4,186.5 | 4,367.9 | 4,359.2 |
| dsp8 | 5,928.2 | 5,928.2 | 6,217.2 | 6,214.7 |
| arlet6502 | 9,654.3 | 9,701.8 | 9,954.5 | 9,995.8 |
| uart_apb | 12,948.7 | 12,948.7 | 13,180.1 | 13,180.1 |
| risc8 | 28,265.9 | 28,263.4 | 27,501.4 | 27,511.4 |
| fir10 | 25,968.7 | 25,968.7 | 29,055.4 | 29,055.4 |

These are calibration targets, not numbers to copy into a report. Tool-version differences must be recorded and explained from actual saved outputs.

### 2.5 Redundancy contract

| Classification | Meaning | Required action |
| --- | --- | --- |
| `Exists` | Same truth table after input reordering. | Drop. |
| `Exists with an inverter` | Same after output or one-input inversion. | Drop unless estimated area is less than cell + inverter. |
| `Contained` | HD cell's inputs can be connected to candidate inputs or 0/1. | Drop unless estimated area is less than that cell. |
| `New` | None of the above. | Keep for costing/ranking. |

The checker must classify every combinational HD cell fed back as a candidate as `Exists`. For all four-input functions, its reference counts must be: 24 `Exists`, 20 `Exists with an inverter`, 38 `Contained`, 3,822 `New`; 9 new one-stage static-CMOS functions; 5 new one-stage functions with <=3 devices in series and <=12 transistors; and 8 simplest one-use-per-input functions, of which 6 exist and 2 are contained.

### 2.6 Option 1 / Option 2 interface (freeze in Week 1)

Option 2 requests must include `request_id`, a `dd2_<group>__...` cell name, ordered `inputs`, `output`, `expression`, hexadecimal `truth_table`, `sizing` (`hd` or `stack`), and `estimated_area_um2`. Input index 0 is the least significant truth-table bit variable.

Option 1 responses include status/reason, built cell name, stages, transistor count, width sites, real area, GDS/Liberty/Verilog/report paths, DRC/LVS/RC-LVS/truth/abutment/layer checks, ngspice hash, and tool version. A non-`pass` response must never be mapped. A returned Liberty file contains exactly one requested cell group and, when appended to the reduced library group, loads in Yosys.

## 3. Current Milestone: Option 2 M1 / Checkpoint 1

M1 is a 10-minute TA meeting beginning Tuesday 27 October 2026 at immutable tag `cp1`. Bring data and check results, not slides. Anything not shown is not met.

### M1 definition of done

- AIGs for **every required design**, before and after ABC restructuring, are generated and retained with a manifest of sizes/counts.
- The <=4-input cut enumerator passes its independent truth-table check.
- Reduced- and usable-library Table 1 baselines are reproduced for all six required designs under both scripts, with raw logs and parsed saved measurements.
- A class table of HD is generated from the appropriate Liberty function attributes.
- The redundancy checker passes: every combinational HD cell is `Exists`, and exhaustive four-input reference counts match Table 4.
- `make setup`, `make check`, and `make test` exercise the implemented M1 scope from a clean checkout. Tests include a broken truth table and an HD-cell-as-candidate case.
- `README.md`, AI logs, and `results/` point to real outputs only. No final candidates, estimated Liberty extensions, real-cell generation, savings claims, or OpenSTA results are claimed yet.

### M1 out of scope

Candidate transistor/stage costing, area-model fitting, candidate ranking, generated Liberty/request files, extended-library mapping, CEC/gate-level/OpenSTA measurements, greedy selection, real cells, and the 30% experiment start after M1. Option 1 code also remains later work.

## 4. M1 Implementation Design

### Proposed file structure

| Path | Purpose |
| --- | --- |
| `src/dd2cell/config.py` | Typed design/script catalog, paths, and immutable input descriptions. |
| `src/dd2cell/flow.py` | Safe subprocess runner, command manifests, and artifact-path helpers. |
| `src/dd2cell/aig.py` | Yosys scripts for synthesized and ABC-restructured AIGER artifacts; parse AIGER header. |
| `src/dd2cell/cuts.py` | AIG parser/traversal, <=4-leaf cut enumeration, truth-table evaluation, and validation. |
| `src/dd2cell/canonical.py` | Permutation/output-inversion canonical form used by reporting and later redundancy checks. |
| `src/dd2cell/liberty.py` | Minimal Liberty-function extraction and normalized HD cell records. |
| `src/dd2cell/redundancy.py` | `Exists` / inversion / containment comparison and exhaustive reference self-test. |
| `src/dd2cell/cli.py` | Explicit subcommands: `check`, `map-baselines`, `extract-aigs`, `enumerate-cuts`, `classify-hd`, `self-test-redundancy`, `m1`. |
| `tests/test_cuts.py` | Pure cut/truth-table tests and broken-table rejection. |
| `tests/test_redundancy.py` | HD function and exhaustive four-input reference-count tests. |
| `tests/test_flow.py` | Command generation and missing-input checks. |
| `tests/broken/` | Immutable intentionally malformed truth/AIG/Liberty cases. |
| `results/m1/` | Versioned manifests, raw tool logs, parsed areas, AIG statistics, cut/class reports, and self-test result. |

### Command and artifact contract

| Command | Inputs | Required output |
| --- | --- | --- |
| `make setup` | `PDK_ROOT`, `GIVEN` | `pdk` and `given` links plus a setup manifest. |
| `make check` | local tools/links | versions, PDK/given validation, Liberty load check. |
| `make test` | source + fixtures | pass/fail unit tests and expected broken-case failures. |
| `make m1` | supplied required designs | every M1 artifact under `results/m1/`. |
| `make all` | same as M1 for now | delegates to `make m1`; later extends the full Option 2 flow. |
| `make demo IN=<design>` | arbitrary design path | re-runs the implemented M1 front end on that design without overwriting curated evidence. |

All result records must include command line, input file hashes, tool versions, UTC timestamp, status, and paths to raw logs. A report table is generated from these records, never hand-entered.

## 5. Task Plan

### Task 1: Bootstrap the repository and executable checks

**Files:**
- Create: `README.md`, `Makefile`, `src/dd2cell/__init__.py`, `src/dd2cell/cli.py`, `tests/test_flow.py`, `tests/broken/README.md`, `ai/use_log.md`, `ai/mistakes_log.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Produces `make setup`, `make check`, `make test`, `make m1`, `make all`, and `make demo IN=...`.
- `cli.py` exposes `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write environment and missing-input tests.** Assert that a missing `given/hd_reduced.lib`, unreadable `PDK_ROOT`, or absent `yosys` produces a nonzero exit and an actionable error.
- [ ] **Step 2: Run the new tests to confirm they fail against the template/no implementation.** Run `python3 -m unittest tests.test_flow -v`; expect failure because the commands do not exist yet.
- [ ] **Step 3: Implement the project layout and command dispatcher.** `make setup` creates only symlinks; `make check` verifies versions/paths and loads supplied Liberty through Yosys; no target claims a passing unimplemented check.
- [ ] **Step 4: Record exact local tool versions in `results/m1/environment.json`.** The record is evidence, not a compatibility assertion.
- [ ] **Step 5: Run `make setup`, `make check`, and `make test`.** Expected: all implemented checks pass and deliberately absent dependencies fail in their isolated test.
- [ ] **Step 6: Commit.** Commit only source, tests, documents, small evidence, and AI logs with the required trailer.

### Task 2: Reproduce baseline mappings and preserve evidence

**Files:**
- Create: `src/dd2cell/config.py`, `src/dd2cell/flow.py`, `src/dd2cell/mapping.py`, `tests/test_mapping.py`
- Create at runtime: `results/m1/baseline/<design>/<script>/<library>/{command.json,stdout.log,stat.json}` and `results/m1/table1.csv`

**Interfaces:**
- `required_designs() -> tuple[Design, ...]` returns the six exact name/top pairs.
- `run_mapping(design: Design, library: Path, script: Literal['A', 'B'], output_dir: Path) -> MappingResult` writes paths plus parsed area.
- `write_table1(results: Iterable[MappingResult], path: Path) -> None` rejects missing cells in the 6x2x2 matrix.

- [ ] **Step 1: Write failing tests for the six required tops, both exact ABC scripts, the expected 24 mapping cells, and `pic1826`'s `-sv` configuration.**
- [ ] **Step 2: Run `python3 -m unittest tests.test_mapping -v`.** Expected: failure because no mapping catalog/runner exists.
- [ ] **Step 3: Implement deterministic Yosys command/script creation and `stat` area parsing.** Persist the raw log even when parsing fails; never substitute handout values.
- [ ] **Step 4: Execute the 24 required baseline mappings and write the parsed table plus a comparison-to-handout note.** Differences remain measured facts with version metadata, not test failures unless the course check specifies a tolerance.
- [ ] **Step 5: Run `make m1-baseline` and `python3 -m unittest tests.test_mapping -v`.** Expected: all matrix/artifact tests pass.
- [ ] **Step 6: Commit.**

### Task 3: Extract both AIG variants for each required design

**Files:**
- Create: `src/dd2cell/aig.py`, `tests/test_aig.py`
- Create at runtime: `results/m1/aigs/<design>/{synth,aig_restructured}.{aig,log,json}`

**Interfaces:**
- `extract_aig(design: Design, variant: Literal['synth', 'restructured'], output_dir: Path) -> AigArtifact` invokes Yosys with `aigmap`/`write_aiger`; it applies `async2sync` and `dffunmap` before writing AIGER.
- `parse_aiger_header(path: Path) -> AigStats` returns input/latch/output/AND counts from the AIGER header.

- [ ] **Step 1: Write failing parser tests using a tiny valid AIGER fixture and a malformed-header fixture.**
- [ ] **Step 2: Run `python3 -m unittest tests.test_aig -v`.** Expected: failure because the parser/extractor is absent.
- [ ] **Step 3: Implement both named variants and record commands, logs, SHA-256s, and AIGER header stats.** The restructured variant must be a separately generated graph, not a copy renamed as one.
- [ ] **Step 4: Run extraction for all six required designs.** Generate `results/m1/aigs/manifest.json` with both artifact paths and counts per design.
- [ ] **Step 5: Run `make m1-aigs` and `python3 -m unittest tests.test_aig -v`.** Expected: manifest has exactly twelve AIG artifacts and parser tests pass.
- [ ] **Step 6: Commit.**

### Task 4: Enumerate and independently validate <=4-input cuts

**Files:**
- Create: `src/dd2cell/cuts.py`, `src/dd2cell/canonical.py`, `tests/test_cuts.py`, `tests/broken/wrong_truth_table.json`
- Create at runtime: `results/m1/cuts/<design>/<variant>.jsonl` and `results/m1/cuts/summary.csv`

**Interfaces:**
- `enumerate_cuts(aig: Aig, max_leaves: int = 4) -> Iterator[Cut]` emits cuts in stable topological/node-ID order.
- `truth_table(aig: Aig, cut: Cut) -> int` maps ordered cut inputs to a packed integer with input 0 as the least-significant variable.
- `validate_cut(aig: Aig, cut: Cut, table: int) -> ValidationResult` exhaustively simulates `2 ** len(cut.leaves)` assignments.
- `canonical_pn(table: int, arity: int) -> int` canonicalizes input permutations and output inversion; NPN counting is separately named so the two cannot be conflated.

- [ ] **Step 1: Write failing tests for AND, XOR, complemented edges, repeated logic leaves, fewer-than-four inputs, canonical equivalence, and a one-bit-corrupt table.** The corrupt table fixture must be expected to fail validation.
- [ ] **Step 2: Run `python3 -m unittest tests.test_cuts -v`.** Expected: failure because enumeration/validation is absent.
- [ ] **Step 3: Implement cut enumeration without invoking ABC's cut implementation.** Store leaf ordering, root, truth table, validation status, and provenance for every emitted cut.
- [ ] **Step 4: Enumerate and validate cuts for both AIG variants of all six required designs.** Fail the M1 run if any saved cut fails independent validation.
- [ ] **Step 5: Run `make m1-cuts` and `python3 -m unittest tests.test_cuts -v`.** Expected: all valid cuts pass; `tests/broken/wrong_truth_table.json` fails only its designated negative check.
- [ ] **Step 6: Commit.**

### Task 5: Build the HD class table and redundancy checker self-test

**Files:**
- Create: `src/dd2cell/liberty.py`, `src/dd2cell/redundancy.py`, `tests/test_redundancy.py`, `tests/broken/invalid_function.lib`
- Create at runtime: `results/m1/hd_classes.json`, `results/m1/redundancy/self_test.json`, `results/m1/redundancy/four_input_counts.json`

**Interfaces:**
- `load_hd_cells(liberty_paths: Sequence[Path]) -> list[HdCell]` retains every single-output combinational cell and its output function.
- `classify_candidate(candidate: BooleanFunction, hd_cells: Sequence[HdCell]) -> RedundancyMatch` returns exactly one Table 3 classification plus a matching cell/witness when applicable.
- `run_hd_self_test(hd_cells: Sequence[HdCell]) -> SelfTestReport` classifies every eligible HD function as `Exists`.
- `exhaustive_four_input_counts(hd_cells: Sequence[HdCell]) -> dict[str, int]` produces all required Table 4 counts.

- [ ] **Step 1: Write failing tests for an exact HD match, output/input inversion, tied-constant containment, a known new function, an invalid Liberty function, and the published four-input counts.**
- [ ] **Step 2: Run `python3 -m unittest tests.test_redundancy -v`.** Expected: failure because no parser/checker exists.
- [ ] **Step 3: Implement Liberty function extraction and Boolean normalization.** Reject unsupported or malformed function expressions explicitly; do not silently omit them from a claimed complete class table.
- [ ] **Step 4: Implement Table 3 matching in the prescribed order and write the HD class table.** Use the full HD Liberty source configured by `make setup`, rather than only `hd_reduced.lib`, for redundancy tests.
- [ ] **Step 5: Run the all-HD self-test and exhaustive four-input count test.** Expected: every eligible HD cell is `Exists`; counts match 24/20/38/3822 and the stated one-stage subsets.
- [ ] **Step 6: Run `make m1-redundancy`, `make test`, and `make m1`.** Expected: M1 produces complete stored evidence and all designed negative cases fail.
- [ ] **Step 7: Commit and create `cp1` only after the TA-ready evidence has been reviewed.** Do not create or move it merely because a partial run completes.

## 6. Milestone Evidence Checklist

Before booking the M1 meeting, verify that the checkout can demonstrate the following directly:

| Requirement | Evidence path |
| --- | --- |
| Environment and input provenance | `results/m1/environment.json`, `results/m1/setup.json` |
| Table 1 reproduction | `results/m1/table1.csv` and per-run mapping logs |
| Required AIGs, both forms | `results/m1/aigs/manifest.json` and twelve `.aig` files |
| Cut enumeration and truth checks | `results/m1/cuts/summary.csv`, per-design JSONL, test log |
| HD class table | `results/m1/hd_classes.json` |
| HD redundancy self-test/Table 4 | `results/m1/redundancy/self_test.json`, `four_input_counts.json` |
| Reproducibility | clean-checkout `make setup && make check && make test && make m1` log |
| AI accountability | `ai/use_log.md`, `ai/mistakes_log.md`, AI-assisted commit trailers |

## 7. Later Milestones and Final Submission

**M2 / cp2:** classify/cost/rank candidates, fit an area model, emit a Yosys-readable estimated-area Liberty file, map with it, run CEC, and provide a first estimated Table 5.

**M3 / final:** obtain real cells from this group's Option 1, replace estimates, rerun mapping/measurement, present same-script and best-of-both reductions, cell-by-cell curve, 30% sensitivity experiment, delay results, full deliverables, reports, and clean-checkout checks.

The final Option 2 technical report is at most 12 pages and covers method, class counts (including NPN distinction), redundancy removals, Table 5/best-of-both/cell curve, cross-design results, frequency-versus-saving counterexample, and limitations. A separate 4-8 page AI report explains the division of work, tools/models/cost, prompts/checks, five instructive mistakes, human-only decision, time tradeoffs, and - if agentic - architecture/logged decisions/fixed-choice comparison/repeated-run data.

## 8. Open Decisions to Resolve Before Implementation

- Confirm group number and members so the permanent `dd2_<group>__` naming prefix and README can be completed.
- Confirm the canonical full-HD Liberty file path supplied by the local PDK; `hd_usable.lib` is not a substitute for the full-HD redundancy input.
- Record installed Yosys/ABC, Icarus, Python, OpenSTA, and PDK revisions through `make check`; no compatibility assumption should be made from the handout's Yosys 0.33 figures.
- Choose AI mode (development aid versus a self-contained agentic system). This document assumes development aid unless the group explicitly chooses otherwise; an agentic system adds required code, per-call/run logs, limits, and fixed-choice comparison.

## 9. Self-Review

- **Spec coverage:** The document covers shared repository/AI/submission rules, the Option 1/2 contract, both option scopes, all 12 Option 2 flow steps, required designs/baselines, redundancy classes/counts, exact M1 acceptance criteria, evidence, and later milestones.
- **M1 boundary:** Tasks 1-5 cover each M1 item without claiming M2/M3 results. Option 1 has an interface/constraints section but no premature implementation task.
- **Test coverage:** Review-focus failures are assigned to Tasks 1, 2, 4, and 5, including the mandated wrong-truth-table and HD-exists negative cases.
- **Type consistency:** Task interfaces use `Design`, AIG/cut/Boolean-function records, and result records consistently; implementation must define their dataclasses in the named modules.
- **Evidence discipline:** Every measurement is generated into `results/m1/` with raw logs and provenance; handout figures are calibration references only.
