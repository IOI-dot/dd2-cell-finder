# AI use log

| ID | Date | Who | Tool and model | What was requested | What was kept or changed | How it was checked | Commit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L-001 | 2026-10-26 | Project team | Codex / GPT-5 | Read the three project handouts and `AGENTS.md`; document the complete scope while planning only Option 2 Milestone 1. | Kept a source-grounded scope and implementation plan at `docs/superpowers/plans/2026-10-26-option2-milestone1.md`. No project code or measured results were created. | Extracted all PDF text, visually reviewed all pages, read `AGENTS.md` and the student-pack/template files, then ran `git diff --check`. | Not committed |
| L-002 | 2026-10-26 | Project team | Codex / GPT-5 | Read `Backend.md`, choose an initial agent-platform boundary, and install the Spec Kit workflow for the whole Option 3 project. | Installed the eight core `speckit-*` skills in the Codex user skill directory. Recommended a local-first, bounded CLI agent platform rather than an external backend for this course project. | Read all 479 lines of `Backend.md`; checked the Spec Kit skill source, install counts, repository metadata, and installation output. | Not committed |
| L-003 | 2026-10-26 | Project team | Codex / GPT-5 | Initialize Spec Kit, add the repository index and ignore policy, and set up the local course toolchain. | Added the Spec Kit scaffold, root `.gitignore`, `index.yml`, and governance references in `AGENTS.md`. Started Colima and attempted the course-provided layout-tools image build. | Confirmed Yosys 0.70, Icarus 13, ABC, Spec Kit, and the SKY130 PDK. Docker build failed with filesystem I/O errors; diagnosis found 109 MB free on the host data volume. No user data was deleted or pruned. | Not committed |
| L-004 | 2026-10-26 | Noor Elshahidi | Claude Code / Claude Opus 5.5 | Verify the earlier session's work; plan the whole Option 3 project through Spec Kit, with Option 2 M1 in full detail and M2 planned; use LangGraph/LangChain, AG-UI and the Graphite Cyan design system for the later agent and UI. | Wrote `specs/001-agentic-cell-finder/{plan,research,data-model,quickstart,tasks}.md` and `contracts/`. Corrected `AGENTS.md` (PDK_ROOT, uv), `index.yml`, and marked the old plan superseded. No project code or results/ evidence was created. | Ran spikes on this host (saved in `specs/.../research/`): 24 baseline mappings on Yosys 0.70; AIG extraction on cpu8; a Table 4 prototype against the full HD Liberty (reproduces 6 of 7 rows; row 6 is 6 vs 5, open). Every test example in tasks.md was checked against the spike. | 71656fb |
| L-005 | 2026-10-26 | Noor Elshahidi | Claude Code / Claude Opus 5.5 | Check the handout PDFs for hidden instructions; implement all of Option 2 Milestone 1 from `specs/001-agentic-cell-finder/tasks.md`; have a subagent verify. | Kept: `src/dd2/` (env check, mapping, AIG, cuts and independent check, Liberty reader, HD class table, stage costing, redundancy and Table 4 self-test, Appendix A validator, summary), `agent/dd2_agent/` (typed tools, policy, Appendix B logs), Makefile, tests and broken cases, README. Changed: plan items found missing from Figure 2 of the overview (agentic and Option 3 cp1 rows) were added as T071/T072. | PDFs: font colour, size and position scan, metadata and figures (research D-16). Code: 81 pytest tests, written red first except the interface tests (M-011); `make all` regenerated results/m1 from scratch; every number in README section 6 is generated from records. | 71656fb |
| L-006 | 2026-10-26 | Noor Elshahidi | Claude Code / Claude Opus 5.5 (with a verification subagent) | Have an independent subagent verify M1 adversarially; fix every finding that does not need a human; organise the repository for the planned backend and agent front end; update the index; use the lectures 9-10 slides as context. | Kept: fixes to findings 3-7 and 11-18 (AIG outputs and cec, agent guard, honest Table 1 and self-test labels, XOR precedence, Liberty reader accounting, vacuous checks); `docs/architecture.md`; `backend/`, `web/`, `docker/` placeholders; two proposed broken cases left for human review. Not done: Option 1 cp1 work, tag and push, group names (human decisions). | Each fix started as a failing test (106 tests now). The verifier's own scripts reproduced Table 4, all cuts and the HD exclusions (69/13/12/10/1). `make all` was regenerated from scratch, and the precedence is compared with Yosys `eval`. | see git log |
| L-007 | 2026-10-26 | Noor Elshahidi | Claude Code / Claude Opus 5.5 (with the verification subagent) | Re-verify a9e925a, then fix the six remaining minor items (symlink escape from the write guard, a cut count that confirmed itself, a missing area defaulting to 0.0, a stale README, absolute paths in records, a doubly nested baseline output). | Kept all six fixes and the verifier's two notes (cec scope documented; requests must be fully parenthesised, task T041). | Each fix started as a failing test (115 tests). The regenerated result tables are byte-identical to a9e925a, and the new evidence contains no absolute paths. | see git log |
| L-008 | 2026-10-26 | Noor Elshahidi | Claude Code / Claude Opus 5.5 | Set up the whole environment ("download what we need") and reproduce Table 1; ignore all course and plan documents in git. | Kept: restored the missing HD views (gds, spice, cdl, lef, mag, maglef) from the identical ciel release; built the course image dd2-layout-tools (stress test passes) and a dd2-flow image with Ubuntu's Yosys 0.33; `make m1-docker`, `make test-docker`; the synth AIG now uses `-zinit`. Dropped the YoWASP route. | The release's Liberty, Verilog and techlef hashes equal the installed files. Table 1 matches 24/24 and the AIG AND counts 6/6 on Linux Yosys 0.33; 115 tests pass on the host and in the container. | see git log |
| L-009 | 2026-10-26/27 | Noor Elshahidi | Claude Code / Claude Opus 5.5 | Do Option 1 checkpoint 1 as a student would; fix the failing broken-case test; verify all of M1. | Kept: `src/cellgen` (request reader, single-stage networks and switch check, paired Euler ordering, rule table, li1 router, layout in the plan_hd.json frame, Magic/Netgen/ngspice wrappers, layer check, abutment fixtures, comparison with installed cells), `make o1-m1`, `make o1-image`, the stress test in `make check`. Changed: the LVS verdict now also fails on Netgen pin "**Mismatch**" lines. | Every check failed first on a broken case (gate pitch, wrong W, swapped pins, swapped series order, missing tap, deleted pull-up, wrong model row, missing hvtp/npc). Magic full DRC was first calibrated on the installed cells (lone cell fails nwell.4, row passes). 155 host tests, 141 in dd2-flow. | see git log |
| L-010 | 2026-10-27 | Noor Elshahidi | Claude Code / Claude Opus 5.5 (two verification subagent passes) | Verify that Milestone 1 is 100% complete for both options and fix what the verifier finds. | Kept: section 4.1 rows gate the cell status; timing row; PDK views required by make check; agent covers Option 1; DRC parser keeps every reason; pin check over every label, using the cell's npc layer (HD's o21ai_1 puts B1's contact above the nominal band); rails must cover the full width; a standalone DRC with unparsed errors fails; refused requests get a response.json. | The second verification pass ran a clean clone: all targets pass and the regenerated results are byte-identical. Verdict: M1 complete apart from the human items. 186 host tests, 153 in dd2-flow. | see git log |
| L-011 | 2026-11-02 | Noor Elshahidi | Claude Code / Claude Opus 5.5 | Option 1 Milestone 2 and the agent: verify M1; multi-stage decomposition, sizing, layout engine, router with met1 fallback, SA/SB, characterizer, Liberty writer, OpenSTA, agent and fixed-choice version | Kept after each failing check was fixed; see M-027 to M-036 | make test, make o1-m2, Magic, Netgen, ngspice, OpenSTA; verification subagent | uncommitted at the time of writing |
| L-012 | 2026-11-02 | Noor Elshahidi | Claude Code / Claude Opus 5.5; GPT-5.6 Sol through the Codex CLI for ideas | Try a game-like 3D front end, then drop it and return to a technical studio: live run stream, a page per step, a trace beside the chat, friendlier time labels, parallel checks. | Kept: `stepdata.py`, per-attempt layout data, `timings.py`, chat updates, questions answered from run facts, steps opened from the chat, Parakeet mic with right Option and an in-place wave, the web app's own minimal UI primitives (`web/src/ui.tsx`) with the private design system ignored by git, `docs/roadmap.md`, `ABOUT_PROJECT` intent and `focus` with interpreter prompt v6, `RunView`, `stepviews`, `Steps`, `Chat`, `time.ts`, parallel DRC and SPICE. Rejected by the user: the Three.js game and all game language, removed. | Checked with `pytest`, `tsc`, `vite build`, real agent runs in Chrome including a three-revision mux, viewports 375 and 1470, and the transient plot against the truth table in all 48 slots. | not committed yet |


## 2026-11-03 Option 2 M2 update

ChatGPT/Codex prepared the Option 2-only update at user request. Original Option 1 code/checks archived unchanged; frozen cases preserved. Added explicit costs, HD area-model validation, mapped-cone ranking, requests/Liberty, dual-script mapping and ABC proofs. Development smoke tests are separate from the user WSL checkpoint evidence. Code is pushed before the user flow; no cp2 created. Active mode is AI as a development aid.


## 2026-11-03 first WSL result review and repairs

User ran the code locally: all 90 tests and all 24 baseline/extended ABC proofs passed. Every timing report failed on the unsupported PathEnd arrival property. Updated the query to the endpoint PathRef, removed clock-port data input delays, and added numbered-error rejection plus a real OpenSTA smoke test. Corrected native-HD calibration stack limits and simplified explicit implementations; no reported measurement is edited by hand. The user now requires testing/review before any push or tag.

### GB4 tutorials and tool selection, 2026-11-03
Recovered unmodified RTL/testbenches from prior tutorial submissions. Added
tutorial discovery, mapping, original-bench functional GLS, strict failure
parsing and tests. Models derive from the exact Liberty, not real-cell SDF.
Added SHA256-pinned official tool bundle installer, retained reference Yosys
for M1, and an explicit TA clarification table. No TA acceptance is inferred.

### M2 release organization, 2026-11-03
Reviewed the user-uploaded DD2_GB4_M2_Results.zip: tests, mappings, timing,
tutorial simulations, generated files and all three figures. Archived unused
docker/platform documentation and superseded plans without changing their
bytes. Historical log paths above refer to their original locations; current
platform files are under archive/previous_platform, and spec/planning material
is under archive/historical_plans. Added make ta and TA_M2/ copies of existing
figures/tables with source hashes. Updated the README and status documentation.
No measured number was changed, and no reference agreement or TA acceptance
was inferred. Git commit/push remain commands for the user's WSL.

### Option 3 restored around the Option 2 M2 push, 2026-11-03
Noor Elshahidi, with Claude Code (Claude Opus 5.5). The user disagreed with archiving Option 1, so the
merge of `adb22dd` keeps every Option 2 M2 file as pushed (`src/dd2m2`, `tests/m2`, `TA_M2/`, `results/m2`,
`results/m1`, `libs/`, `config/`, `tools/`) and moves Option 1, the agent, the studio and the plans back to
their usual paths. Each archived file was first confirmed to be a byte-identical move or a copy of the old
configuration. `Makefile`, `README.md`, `AGENTS.md`, `index.yml` and `pyproject.toml` were combined so both
flows run from one place. `tests/m2/test_retained_broken.py` was removed because it only loaded two tests from
the archived copy of `tests/integration/test_proposed_broken.py`, which now runs in full from its own path.
Checked: the frozen broken-case hashes, and the whole suite on macOS (385 passed; 5 Option 2 tests skipped for
want of the WSL tools and tutorial inputs). The ten Option 2 requests pass the Appendix A validator and the
Option 1 request reader unchanged.

### Option 3 connected, and Option 2 in the studio, 2026-11-03
Noor Elshahidi, with Claude Code (Claude Opus 5.5). Added `cellgen.deliver` (Option 1 builds, checks and
characterizes each requested cell, gated on Table 5, and answers in Appendix A), `dd2m2.option3` (only passing
cells, with their real Liberty groups, replace the estimated ones; designs remapped into `results/option3/`),
`make o3`, a Docker wrapper for OpenSTA on macOS, the read-only `/api/option2` view, the Option 2 tab, and the
agent's `ABOUT_OPTION2` and `BUILD_CANDIDATE` intents (interpreter prompt v7). Kept: Option 2's code and evidence
unchanged. Checked: tests first for each part, the whole suite (397 passed, 5 skipped for WSL-only inputs), live
questions and a candidate build in the browser, and the interpreter's chosen section recorded in the run log.

### Modular Option 2, effort by role, and the Option 3 run, 2026-11-03
Noor Elshahidi, with Claude Code (Claude Opus 5.5). Split `src/dd2m2/flow.py` into one module per step, with a
module map; every moved function compares equal by syntax tree, black reformatted the package, and the regenerated
`TA_M2/` and `results/m1/summary.md` are byte-identical to the committed ones. Added thinking effort by role
(`[model.effort]`), with a refused reply retried one level higher; measured on two questions, it changed latency
little, because the CLI start and the context dominate. Ran the Option 3 loop: eight of ten requested cells pass with
real Liberty, and all twelve remappings prove equivalent, on this machine's tools. Reran the agent against fixed
choices on every test cell with the code frozen. The README now leads with Option 2 M2; no new images are committed.

