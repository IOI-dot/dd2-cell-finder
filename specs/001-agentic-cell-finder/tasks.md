---
description: "Task list for DD2 Cell Finder: Option 2 Milestone 1 in full detail, later milestones planned"
---

# Tasks: DD2 Cell Finder (Option 3)

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: **required**. Constitution III makes TDD non-negotiable. Every implementation task is
preceded by a test task that must be run and **seen to fail** first. Run everything through `uv run`,
never with the host `python3` (3.9).

**Rules for whoever executes this (human or AI)**: read `AGENTS.md` and `index.yml` first. Never edit
`given/`, `pdk/`, the student pack, or `tests/broken/` once a case is committed. Never type a
measured number into a file. Add an `AI-assisted: <tool>/<model>` trailer to AI-assisted commits, and
log the work in `ai/use_log.md` and any caught mistake in `ai/mistakes_log.md`.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup and unblocking (do today)

- [x] T001 Fix repository hygiene (research R-2, D-12): `git rm -r --cached DD2_Project1_student_pack "DD2 Project 1 - "*.pdf`, move the pack to `../DD2_Project1_student_pack`, and add `DD2_Project1_student_pack/`, `*.pdf`, `references/`, `runs/` and `build/` to `.gitignore`. Ask the group (Q-4) before any history rewrite or force-push. Do **not** tag cp1 until this is settled.
- [ ] T002 Free disk (R-0): get at least 2 GB free for M1 and 15 GB before M2 (Docker, full HD views, OpenSTA). The machine owner chooses what to delete; an assistant must not delete anything. Record the `df -h` output in `ai/use_log.md`.
- [x] T003 Create `pyproject.toml` (uv, `requires-python = ">=3.11"`, package `dd2` under `src/`, extras `dev = [pytest]`, `agent = [langgraph>=1,<2, langchain>=1.2, ag-ui-langgraph==0.0.47, fastapi]`, `flow = [yowasp-yosys==0.33.0.0.post574]`), `.python-version` (3.12), `src/dd2/__init__.py`, `tests/{unit,contract,integration,broken}/`, and `tests/conftest.py`. Check that `uv run pytest` collects 0 tests.
- [ ] T004 Verify the pinned Yosys (research D-2): `uv run yowasp-yosys -V`, then run the handout §2 commands on `given/designs/cpu8.v` with `given/hd_reduced.lib` and script A. **Pass condition: area = 4186.5 µm² (±0.05).** Also find out whether the wheel provides an ABC entry point. Write the outcome into research.md D-2 (replace "Unverified"). If it fails, switch to the `docker/flow.Dockerfile` source build and record why.
- [x] T005 [P] Copy the template layout from `../DD2_Project1_student_pack/repo_template/`: `README.md` (the ten Appendix C sections, placeholders allowed), `docs/interface/{request,response}_example.json` (byte-identical), and `results/ libs/ cells/ report/ prompts/` with `.gitkeep`.
- [x] T006 (as built: targets call `.venv/bin/python -m dd2` with `PYTHONPATH=src`, not `uv run`; `YOSYS` defaults to the host `yosys` until T004) Write the `Makefile` with every target in [contracts/cli.md](contracts/cli.md). Defaults: `PDK_ROOT ?= $(HOME)/.ciel`, `GIVEN ?= ../DD2_Project1_student_pack/given`, `YOSYS ?= uv run yowasp-yosys`. Every target calls `uv run python -m dd2 …`. Targets that are not implemented yet exit 1 with `not implemented: <task id>`.

---

## Phase 2: Foundational (blocks every story)

- [x] T007 [P] Tests then code for `src/dd2/paths.py`: repo root, `pdk/` and `given/` link resolution, the full HD lib path `pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib`, and `build/` / `results/` dirs. Test file: `tests/unit/test_paths.py`.
- [x] T008 [P] Tests then code for `src/dd2/provenance.py`: a `RunRecord` dataclass (data-model.md), sha256 of inputs, UTC times, and `write_json(path, record)` with sorted keys. Test file: `tests/unit/test_provenance.py`.
- [x] T009 [P] Tests then code for `src/dd2/tools.py`: `run(argv, log_path, timeout)`, which captures stdout/stderr to the log, enforces the timeout, and returns exit code and duration; plus `versions()` for python, yosys, yosys-abc, iverilog and sta (None when missing). Test with `sh -c` stubs. Test file: `tests/unit/test_tools.py`.
- [x] T010 [P] Tests then code for `src/dd2/designs.py`: the 12-design catalog with exact tops, `sv=True` only for pic1826, and `required()` returning the six. Test file: `tests/unit/test_designs.py`.
- [x] T011 [P] Tests then code for `src/dd2/boolfn.py`: `var_tt`, `permute`, `flip_input`, `negate`, `depends_on`, `canon_p`/`canon_pn`/`canon_npn` (cached 65,536-entry tables for n ≤ 4, brute force up to n = 6), and an expression parser/evaluator over `! ' & * | + ^ ( ) 0 1` with precedence ! > & > ^ > |. Must include the vector `!((C & D) | (A & B & (C | D)))` → `0x077F` (A = LSB). Test file: `tests/unit/test_boolfn.py`.
- [x] T012 (as built: `dd2 check` writes the environment record, there is no separate `dd2 env`; `make setup` installs pytest, not the `flow` extra) Tests then code for `src/dd2/cli.py` and `src/dd2/__main__.py` (subcommand dispatch, exit codes 0/1/2), plus `dd2 env`. Implement `make setup` (symlinks only, then `uv sync --extra flow`) and `make check` as in contracts/cli.md: Yosys `read_liberty -lib` must print `Imported 189 cell types` / `Imported 307 cell types`, and OpenSTA and the ngspice stress test are reported as later requirements. Add the broken case `tests/broken/missing_given/` and `tests/integration/test_check.py`, which asserts that `make check GIVEN=tests/broken/missing_given` exits non-zero with an actionable message.

**Checkpoint**: `make setup && make check` pass, and `make test` runs the foundation tests.

---

## Phase 3: User Story 1: Produce Milestone 1 evidence (P1) 🎯 MVP → tag `cp1`

**Goal**: every cp1 row of Option 2 Table 6 (M1), shown from files.
**Independent test**: quickstart.md §1–§3 on a clean checkout.

### AIGs (both variants, research D-4)
- [x] T013 [P] [US1] Tests then code for `src/dd2/aig.py::extract()`. The synth variant runs `read_verilog [-sv]; synth -flatten -top; async2sync; dffunmap; aigmap; write_aiger`. The restructured variant runs ABC `read; strash; dch -f; strash; write_aiger`. Measure the latch count with and without `-zinit` against `stat` FF counts after `synth`, keep the variant that matches, and note the result in research.md D-4. Test (integration, cpu8): both files exist, they have different sha256, and the restructured file has no choice nodes. Test file: `tests/integration/test_aig.py`.
- [x] T014 [P] [US1] Tests then code for `src/dd2/aig.py::read_aiger()`, which reads binary `aig` (delta-encoded ANDs) and ASCII `aag`. Fixtures: a hand-written 3-AND `aag` and the same graph in binary; a malformed header must raise. Test file: `tests/unit/test_aiger_reader.py`.
- [x] T015 [US1] Implement `dd2 aig` and `make m1-aigs`. Write `results/m1/aigs/<design>/{synth,restructured}.{aig,json,log}`, a `manifest.json` that must have exactly 12 entries (asserted), and `compare.csv` (ANDs and levels before and after).

### Baseline mapping (Table 1, research D-2/D-3)
- [x] T016 [P] [US1] Contract test `tests/contract/test_map_command.py`: the command and script strings built by `src/dd2/mapping.py` equal those in `given/scripts/map.sh` for A and B, apart from the added `stat -json`.
- [x] T017 [US1] Tests then code for `src/dd2/mapping.py::run_mapping(design, library, script, out, yosys)`. Parse `stat.json` for area and per-cell counts, and keep the raw log even when parsing fails. Test on cpu8/reduced/A: area > 0, cells > 0, and the RunRecord is complete. Test file: `tests/integration/test_mapping.py`.
- [x] T018 (as built: the canonical run is Yosys 0.70 because T004 is blocked, so there is no separate `baseline_yosys070/`; `table1.csv` has `matches_handout` and the summary says NOT REPRODUCED) [US1] Implement `dd2 baseline` and `make m1-baseline` (24 runs) and `results/m1/table1.csv` (data-model.md BaselineMeasurement). Handout values go into `handout_*` columns from `src/dd2/designs.py` constants and are labelled as reference values. Assert that the matrix is complete. Run it once with `YOSYS=yosys` (0.70) into `results/m1/baseline_yosys070/` so the version effect is evidenced.

### Cuts and their independent check (research D-5)
- [x] T019 [P] [US1] Write failing tests in `tests/unit/test_cuts.py` for `src/dd2/cuts.py::enumerate_cuts(aig, k=4)`: an AND gate, XOR (3 ANDs, complemented edges), reconvergent fan-out, cuts with fewer than 4 leaves, dominated-cut removal, CIs (PIs and latch outputs) as leaf-only, a stable order, and truth tables with leaf 0 = LSB.
- [x] T020 [US1] Implement `src/dd2/cuts.py`: bottom-up merge, bit-parallel 16-bit truth tables, cuts only for AND nodes, and output `Cut` records (data-model.md).
- [x] T021 [P] [US1] Write failing tests in `tests/unit/test_cutcheck.py` for `src/dd2/cutcheck.py::check(aig, cut, tt)`: per-assignment cone simulation that imports **nothing** from `cuts.py`. Add the broken case `tests/broken/wrong_truth_table.json` (a real cpu8 cut with one flipped bit), which must be rejected.
- [x] T022 [US1] Implement `src/dd2/cutcheck.py` and `dd2 cutcheck`.
- [x] T023 [US1] Implement `dd2 cuts` and `make m1-cuts` for the 12 AIGs. Write the full list to `build/cuts/<design>/<variant>.jsonl.gz`, and `results/m1/cuts/<design>/<variant>.{summary.json,sample.jsonl}` with PN and NPN class histograms (excluding trivial cuts). Write `results/m1/cuts/summary.csv`. The step exits 1 if any cut fails. Add a test that fails if any file under `results/` is larger than 50 MB (`tests/integration/test_sizes.py`).

### HD class table and redundancy (research D-6–D-9)
- [x] T024 [P] [US1] Write failing tests in `tests/unit/test_liberty.py` for `src/dd2/liberty.py`: cell and pin extraction, `power_down_function` ignored, sequential, tri-state and multi-output cells excluded, and exactly 323 cells from the full HD lib. Add the broken case `tests/broken/invalid_function.lib` (an unknown operator), which must raise.
- [x] T025 [US1] Implement `src/dd2/liberty.py`. Seed it from `specs/001-agentic-cell-finder/research/table4_spike.py` but rewrite it as tested code (no global state).
- [x] T026 [US1] Implement `src/dd2/hdclasses.py`, `dd2 hdclasses` and `make m1-hdclasses` → `results/m1/hd_classes.{json,csv}` and `hd_pn_classes.csv` (research D-9). Test: inv_1 and nand2_1 rows, and `in_reduced` for a cell only in the full lib (`sky130_fd_sc_hd__a2111oi_0`: verified present in the full lib and absent from `hd_reduced.lib`).
- [x] T027 [P] [US1] Write failing tests in `tests/unit/test_stage.py` for `src/dd2/stage.py` (the single-stage SP DP, research D-7). Known points: nand2 = (2 lits, n 2, p 1), nor3 = (3, 1, 3), a21oi = (3, 2, 2), maj4n `0x077F` has the point (6, 3, 2), and positive-unate or binate functions are not one-stage.
- [x] T028 [US1] Implement `src/dd2/stage.py`.
- [x] T029 [P] [US1] Write failing tests in `tests/unit/test_redundancy.py` for `src/dd2/redundancy.py::classify()`: an exact match (a permuted a22oi), single-input inversion (`0x000B` → Exists with an inverter, which spike-verified that output negation alone does not reach), output inversion (on a synthetic two-cell HD list, because the real HD has both polarities of most functions), a contained case with a witness (`!(A&(B|(C&D)))` → Contained, spike-verified; the witness may be any HD cell, though Option 1 Table 6 names a32oi), `0x077F` → New, and the broken case `tests/broken/hd_cell_as_candidate.json` (an HD cell submitted as a candidate) → Exists. The Table 4 test asserts 24/20/38/3822, 9 and 8 (6+2), and records row 6 as definition-open (Q-1). It is not tuned to 5.
- [x] T030 [US1] Implement `src/dd2/redundancy.py`, `dd2 classify`, `dd2 selftest` and `make m1-redundancy` → `results/m1/redundancy/{self_test.json,four_input_counts.json}` (data-model.md SelfTestReport).

### Integration and delivery
- [x] T031 [US1] Implement `make demo IN=… TOP=… [SV=-sv]`, which writes only to `build/demo/<name>/`. Test: running it on dsp8 leaves `git status --porcelain results/` empty. Test file: `tests/integration/test_demo.py`.
- [x] T032 [US1] Implement `src/dd2/summary.py`, which generates `results/m1/summary.md` (requirement → file → status read from records), and wire `make m1` and `make all`.
- [x] T033 [US1] Protect the broken cases: write `tests/broken/SHA256SUMS`; `make test` verifies it, so any edit to a broken case fails the suite. Document in `AGENTS.md` that only a human may regenerate it.
- [ ] T034 (partly: README sections 2–10 are done; section 1 still needs the group's names and IDs) [US1] Fill `README.md` sections 1–10 from real outputs (headline numbers copied by `src/dd2/summary.py`, not by hand), and update `AGENTS.md` (commands, conventions, trailer), `index.yml` (new paths: `agent/ web/ docker/ references/ runs/ specs/`) and `ai/use_log.md` / `ai/mistakes_log.md`.
- [ ] T035 [US1] Run quickstart.md §1–§5 from a **fresh clone** with timings recorded for README §2. Commit with the trailer, then, as a human decision, `git tag cp1` and push it once. Bring `results/m1/summary.md` and Q-1 to the TA meeting.

- [x] T071 [US1] Agentic cp1 rows (research D-15): `agent/dd2_agent/{tools,policy,audit,selfcheck}.py`, `tests/unit/test_agent.py`, `make agent-check` → `ai/runs/<run>.{jsonl,checks.json}`.
- [x] T072 [US1] Option 3 cp1 row: Appendix A frozen; `docs/interface/{request,response}.schema.json`, `src/dd2/interface.py`, `tests/contract/test_interface.py` (T041 brought forward).

**Checkpoint (cp1)**: every row in quickstart.md §3 passes; nothing from M2 is claimed.
- [x] T073 [US1] Verification fixes (findings 3–7, 11–18 of verification-2026-10-26.md) with tests; proposed broken cases in `tests/broken_proposed/`.
- [x] T074 Repository organised for the planned platform: `docs/architecture.md`; `backend/`, `web/`, `docker/` placeholders; `index.yml` updated.

**Status 2026-10-26**: T001–T034, T041, T071 and T072 are done. Still open: T002 (disk: 7 GB free now), T004 (Yosys 0.33 not
verified, so Table 1 is measured on 0.70) and T035 (fresh-clone run, commit; the cp1 tag is the group's call).

---

## Phase 4: User Story 2: Discover and deliver missing functions (P2) → tag `cp2` (from 3 Nov)

**Goal**: Option 2 M2 (candidates classified, costed, redundancy-checked and ranked; area model fitted; a Liberty file Yosys reads; a first Table 5 with estimated areas; every mapping passing cec).
**Independent test**: `make m2` produces `results/m2/table5_estimated.csv` with all `equivalence = pass`.

- [ ] T036 [US2] Once R-0 is cleared, reinstall the full `sky130_fd_sc_hd` views (spice/gds/lef) through ciel (R-1). Add a `src/dd2/spice.py` transistor counter, with tests on inv_1 = 2 and nand2_1 = 4.
- [ ] T037 [P] [US2] Tests then code for `src/dd2/costing.py`: a negative-unate function costs one stage (stage.py, ≤3 series); a positive-unate one costs a stage plus an output inverter (+2T); binate functions use input inverters (+2T each) or a multi-stage decomposition found by mapping with ABC onto a generated `build/stage_lib.lib` of all ≤3-series single stages (area = transistors). Return stages, inverters and transistors, keeping the minimum.
- [ ] T038 [P] [US2] Tests then code for `src/dd2/areamodel.py`: least-squares fit `width_sites = a + b·T` on HD x1 cells (single- and multi-stage), reporting per-cell residuals, MAE and max error → `results/m2/area_model.json`.
- [ ] T039 [US2] Implement `src/dd2/candidates.py`: aggregate PN-classes of cuts over the six designs (both variants), apply redundancy with the area exceptions (inverter: keep if est < cell + inv; contained: keep if est < cell), and write `results/m2/candidates.csv` and the redundancy report.
- [ ] T040 [US2] Implement `src/dd2/rank.py`: the estimated saving is the area of mapped cells covered by each occurrence (match cut root and leaves against the baseline netlist's cell outputs and inputs), minus the new cell's estimated area. Write `results/m2/ranked.csv`.
- [x] T041 (as built: `src/dd2/interface.py` instead of `requests.py`; the request writer itself comes in M2 and must write expressions fully parenthesised, because Appendix A does not define operator precedence) [P] [US2] Write `docs/interface/{request,response}.schema.json` (contracts/appendix-a.md) and `src/dd2/requests.py`. Tests: the template examples validate, and a mismatched expression/table fails.
- [ ] T042 [US2] Tests then code for `src/dd2/libwriter.py`: insert new cells inside the `hd_reduced.lib` library group into `libs/hd_extended_est.lib`, with logical-effort placeholder caps and timing and one arc per input (Option 2 §6). Yosys must print `Imported 189+k cell types`. Add the broken case `tests/broken/yosys_rejects.lib`, which Yosys must reject.
- [ ] T043 [US2] Research, then implement `src/dd2/cec.py`: ABC equivalence of the mapped netlist (cells read with `read_liberty` as functional models) against the RTL. Decide between `cec` on a combinational cut at matched registers and `dsec` for sequential designs, and record the decision in research.md. Add the broken case `tests/broken/bad_netlist.v`, which cec must reject.
- [ ] T044 [US2] Implement `src/dd2/measure.py` and `make m2-map`: baseline and extended × A/B for the six designs, new-cell instance counts, and cec status → `results/m2/mapping/**`.
- [ ] T045 [P] [US2] Install or build OpenSTA, and implement `src/dd2/sta.py` (worst delay per mapping, with an SDC that uses one clock on each design's clock port). Make `make check` require `sta` from cp2 on.
- [ ] T046 [P] [US2] Gate-level simulation with Icarus and the HD Verilog models for the designs that have testbenches (SPM from Tutorial 4) → `results/m2/gls/`.
- [ ] T047 [US2] Implement `src/dd2/table5.py`: same-script and best-of-both reductions, totals over the required designs → `results/m2/table5_estimated.csv`. Wire `make m2`, run the clean-checkout check, and have a human tag `cp2`.
- [ ] T048 [US2] (M3) Implement `src/dd2/select.py` for greedy selection (≤10 cells, keep a cell only if the total area drops); swap in real cells from Option 1 responses; produce the final Table 5, the cell-by-cell curve plot, and the 30%-smaller experiment → `results/final/**`.

---

## Phase 5: User Story 3: Build requested HD cells (P3, owned by the Option 1 sub-team)

Planned only. The Option 1 handout and the Option 1 owners own the detail. It is blocked here by R-0 and R-1 (research D-14).

- [ ] T049 [US3] Build `dd2-layout-tools` from `../DD2_Project1_student_pack/container/` unchanged, and add the stress test to `make check`.
- [ ] T050 [US3] Request reader in `src/cellgen/request.py`, reusing `dd2.boolfn` through its public functions only; refuse more than 4 inputs, or a mismatched table.
- [ ] T051 [US3] Regenerate inv_1 and nand2_1 at 2.72 µm with every check (Option 1 cp1), then the six reference cells and the characterizer validation (cp2).
- [ ] T052 [US3] Response writer in `src/cellgen/response.py`, which validates against `docs/interface/response.schema.json`.

---

## Phase 6: User Story 4: Bounded agent run with a live UI (P4). The agent and fixed-choice core are due by cp2.

**Independent test**: `make agent IN=given/designs/cpu8.v` finishes headless with a valid `ai/runs/<run>.jsonl` whose last line is a result line that names a check file. `make fixed` runs the same flow, and a policy test shows writes into `tests/broken/` being refused.

- [ ] T053 [P] [US4] Write `config/agent.toml` (model from Q-2, limits per contracts/agent.md) and `.env.example`; read keys only from the environment.
- [ ] T054 [P] [US4] Tests then code for `agent/dd2_agent/policy.py` (path authorisation, argument clipping). Test file: `tests/unit/test_policy.py`.
- [ ] T055 [P] [US4] Tests then code for `agent/dd2_agent/budget.py`, a LangChain middleware that enforces iterations, time, tokens, cost and input bytes.
- [ ] T056 [P] [US4] Tests then code for `agent/dd2_agent/audit.py` (Appendix B JSONL; the last line must name an existing check file).
- [ ] T057 [US4] Implement `agent/dd2_agent/tools.py`: the typed tools in contracts/agent.md, each shelling out to `uv run python -m dd2 …`.
- [ ] T058 [P] [US4] Write `prompts/selector.md` and `prompts/triage.md`, referenced by `path@git-hash` in the audit log.
- [ ] T059 [US4] Implement `agent/dd2_agent/fixed.py` and `make fixed IN=…`: deterministic choices (top-k by estimated saving, retry with `stack` once, then drop).
- [ ] T060 [US4] Implement `agent/dd2_agent/graph.py` (LangGraph: plan → act ↔ tools → verify → finish; `interrupt()` before `write_requests`; `SqliteSaver` checkpoint) and `make agent IN=…`, which auto-approves headless runs through a deterministic `--approve-policy` and logs every approval.
- [ ] T061 [US4] Implement `agent/dd2_agent/server.py`: FastAPI + `add_langgraph_fastapi_endpoint(app, graph, "/agent")` with `emit_interrupt_outcome=True`, plus a read-only `/evidence/*` endpoint over `results/`.
- [ ] T062 [P] [US4] Scaffold `web/` (Vite, React 19, TS). Import the Graphite Cyan tokens from `DesignSystemStudio/GraphiteCyan/catalyst-design-system-v2-graphite-cyan.css` into `web/src/styles/tokens.css`, and copy the needed primitives (sidebar, card, table, badge, chart, dialog, sonner, message, message-scroller) into `web/src/components/ui/`.
- [ ] T063 [US4] Build `web/src/pages/RunDetail.tsx` with the `@ag-ui/client` `HttpAgent`: a lifecycle timeline, tool-call cards, budget meters, and an approval dialog that resumes through `resume[]`. Verified evidence and AI text are labelled differently (FR-015).
- [ ] T064 [US4] Build `web/src/pages/{Runs,Evidence,Compare}.tsx`. Check accessibility (keyboard, contrast, not colour-only) at 375 px and 1280 px.
- [ ] T065 [P] [US4] Write `docker/flow.Dockerfile` (python 3.12-slim, uv, pinned Yosys, iverilog, OpenSTA built in a multi-stage) and `docker/agent.Dockerfile`.
- [ ] T066 [P] [US4] Write `docker/web.Dockerfile` (node 22 build → nginx) and `docker/compose.yml` with `given/`, `pdk/` and `tests/broken/` mounted `:ro`. `docker build --check` must pass, and full builds wait for R-0.
- [ ] T067 [US4] Run the agent against the fixed pipeline three times on the demo design, recording cost, time and the reason for each failure → `results/final/agent_vs_fixed.csv` (overview §4.2).

---

## Phase 7: Polish and cross-cutting

- [ ] T068 [P] Write `docs/architecture.md`: a diagram of the agents, the tools each may call, and what each tool may read or change (overview §4.2), plus the module boundaries.
- [ ] T069 [P] Write `report/report.md` → `report.pdf` (≤12 pages) and `report/ai_report.md` → `ai_report.pdf` (4–8 pages), with every number cited from `results/`.
- [ ] T070 Validate the final clean checkout (quickstart plus `make all`), then have a human tag `final` before 10 Nov.

---

## Dependencies and execution order

- **T001 and T002 block everything that writes to the repository or needs disk.** T004 blocks T018.
- Phase 2 needs T003 and T006. T011 (boolfn) blocks T020, T026, T028 and T029. T014 blocks T019–T023.
- In US1, the AIG track (T013–T015), the baseline track (T016–T018) and the redundancy track (T024–T030) are independent; the cut track (T019–T023) needs T015. T031–T035 come last.
- US2 needs US1 complete, plus R-0 and R-1 for T036/T038. US4's T053–T060 need only US1 (the tools wrap M1 and M2 commands) and are due by cp2. US3 is parallel and owned by Option 1.

## Parallel example: User Story 1

```text
Track A: T013 → T014 → T015 → T019 → T020 → T021 → T022 → T023
Track B: T016 → T017 → T018
Track C: T024 → T025 → T026 ; T027 → T028 ; T029 → T030
Join   : T031 → T032 → T033 → T034 → T035
```

## Implementation strategy

1. **Today (26 Oct)**: T001–T006, then Phase 2. Without T002 nothing below can run reliably.
2. **MVP = US1 → cp1.** If time runs short, the order of value for the TA is: Table 1 (T018), the redundancy self-test (T030, since its definitions are already proven), AIGs (T015), cuts (T023).
3. **M2 window (27 Oct–3 Nov)**: US2 T036–T047 in parallel with US4 T053–T060 (cp2 requires the agent and fixed-choice version to exist).
4. **M3 (to 10 Nov)**: T048, the UI (T062–T064), Docker, the comparison, reports, `final`.
