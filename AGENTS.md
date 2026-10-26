# Instructions for the AI assistant

## Project
Option 3: build the connected Option 1 and Option 2 tools. Option 2 finds repeated Boolean
functions in synthesized circuits, identifies functions missing from SKY130 HD, and measures
custom-cell savings. Option 1 later turns selected functions into verified HD-compatible cells.
The active implementation scope is Option 2 Milestone 1. Use Python, Yosys/ABC and OpenSTA.

## Repository index
Read `index.yml` before changing project files. It is the machine-readable map of repository
ownership, protected paths, course inputs, toolchain assumptions, and the agentic-system contract.
Update it whenever a tracked path, responsibility, or tool dependency changes.

## Reference material
- `Backend.md` supplies local-agent platform guidance: typed tool schemas, bounded loops, prompt
  versioning, JSONL audit logs, limits, retries, and deterministic authorization.
- `DesignSystemStudio/` is the approved visual source for a future UI only. Read
  `DesignSystemStudio/INDEX.md` before using its components. The UI uses the Graphite Cyan theme in
  `DesignSystemStudio/GraphiteCyan/` and is specified as US4 in the active spec. Do not start it
  before US1 (Milestone 1) is complete.
- `references/ag-ui` and `references/langchain-skills` are read-only upstream clones for the agent
  (LangGraph/LangChain) and the AG-UI front end. They are not committed.
- `.specify/memory/constitution.md` is the governing Spec Kit constitution. Follow Spec Kit for
  constitution, specification, plan, tasks, analysis, and implementation; use TDD inside tasks.

## Toolchain
- `PDK_ROOT` is the directory that contains `sky130A` (locally `~/.ciel`, so the PDK is
  `~/.ciel/sky130A`). `make setup` links `pdk -> $PDK_ROOT/sky130A`.
- Run Python only from `.venv` (made by `make setup` with uv, Python >= 3.11). The host `python3` is
  3.9 and is too old.
- The active plan and task list are `specs/001-agentic-cell-finder/{plan,research,tasks}.md`.
  `docs/superpowers/plans/2026-10-26-option2-milestone1.md` is superseded by them.
- `make setup` must create the `pdk` and `given` links instead of copying either input.
- The course layout tools run in the `dd2-layout-tools` container. OpenSTA is a required later
  dependency and must be checked explicitly by `make check`.

## Verification
- `make check`: tools, PDK and supplied inputs (`src/dd2/envcheck.py`).
- `make test`: every pytest test, plus `tests/broken/SHA256SUMS`. Each check has a broken case.
- `make all` (= `make m1`): regenerates `results/m1/`; `make m1-summary` writes `results/m1/summary.md`.
- `make agent-check`: the scripted agent run (wrapped tools, policy refusals, Appendix B log).
- Write a failing test first, run it red, then implement (Constitution III).

## Rules
- Pass or fail comes from check scripts.
- Report numbers must come from saved flow outputs.
- Never change check scripts, broken cases or the PDK.
- Never invent results or claim unrun tests passed.
- Never move checkpoint tags after their deadlines.
- Never commit the PDK, given files, build trees or files over 50 MB.
- Save report evidence in results/.
- Record AI use and mistakes in ai/.
- Add an AI-assisted trailer to AI-assisted commits.
- Never edit files in `tests/broken/` or `tests/broken/SHA256SUMS`; only a human adds a broken case
  and regenerates the checksums.
- Never type a measured number into README, reports or summaries: they are generated from records.
- Keep agent runs bounded and auditable: version prompts, validate tool arguments, log every
  model/tool call, enforce time/token/cost limits, and let deterministic code guard protected paths.
