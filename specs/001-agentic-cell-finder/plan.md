# Implementation Plan: DD2 Cell Finder (Option 3), with Option 2 Milestone 1 first

**Branch**: `main` (feature dir `001-agentic-cell-finder`) | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-agentic-cell-finder/spec.md`

## Summary

Build the Option 3 project: Option 2 finds repeated ≤4-input functions in synthesized designs, drops
those that HD already provides, and measures the area that new cells save. Option 1 builds the chosen
cells. The two are joined by the Appendix A request/response files. A bounded LangGraph agent with an
AG-UI web front end sits **on top of** the deterministic CLI, never inside it.

**Active scope: Option 2 Milestone 1 (cp1, TA meetings from Tue 27 Oct 2026, which is tomorrow).**
Its deliverables are: AIGs of every required design (both variants), a cut enumerator that passes its
own exhaustive check, Table 1 reproduced, the class table of HD, and a redundancy checker that passes
its self-test against Table 4. The research spikes have already shown that the Table 4 definitions
reproduce the handout on every row except one, which stays an open question (research D-7). They also
showed that host Yosys 0.70 does not reproduce Table 1, so the flow pins Yosys 0.33 (research D-2).

## Technical Context

**Language/Version**: Python ≥ 3.11 via `uv` (the host default 3.9.6 is too old); TypeScript 5 / React 19 for `web/` (later)
**Primary Dependencies**: M1: stdlib only, plus Yosys 0.33 (`yowasp-yosys==0.33.0.0.post574`, verification T004) and its ABC. Later: OpenSTA, Icarus 13; `langgraph`, `langchain`, `ag-ui-langgraph`, `fastapi` (extra `[agent]`); `@ag-ui/client`, DesignSystemStudio components, Graphite Cyan tokens (`web/`)
**Storage**: files only. `results/` (committed evidence), `build/` (ignored scratch), `ai/runs/*.jsonl` (agent audit); LangGraph `SqliteSaver` for interrupt checkpoints (later). No database server.
**Testing**: `pytest` (unit, contract, integration), with immutable negative cases in `tests/broken/` that `make test` must see fail
**Target Platform**: macOS arm64 (this host) and Linux (the TA's clean machine and Docker)
**Project Type**: CLI pipeline (core) + optional agent service + optional web app
**Performance Goals**: the full `make m1` on six designs takes ≤ 15 min on a laptop (all 24 mappings took < 20 s on 0.70; the cut volume dominates)
**Constraints**: offline-capable; no committed file > 50 MB; protected paths are read-only; **376 MB free disk now** (R-0)
**Scale/Scope**: 6 required designs + 6 optional; ≤ 15.9k AIG ANDs (xfir); about 10^5–10^6 4-cuts per design variant

## Constitution Check

*GATE: checked before Phase 0 and again after Phase 1.*

| Principle | How the plan complies | Status |
|---|---|---|
| I. Course evidence is the source of truth | Every number comes from `results/m1/**` records with command, hashes, versions and timestamp. Handout numbers appear only in `expected` columns. Q-1 is reported as a mismatch and not tuned away. | ✅ |
| II. Local-first, reproducible | The core is stdlib Python + Yosys, driven by `make`. The agent and web are optional extras, not needed for `make check test all`. | ✅ |
| III. TDD | Each task in tasks.md writes a failing test first. Each check has a `tests/broken/` case. | ✅ |
| IV. Bounded, auditable agent | Planned for US4: typed tools, a budget middleware, JSONL audit, versioned prompts, read-only mounts, and a fixed-choice twin. | ✅ (design only) |
| V. Explicit boundaries and index | `index.yml` is updated for `agent/`, `web/`, `docker/`, `references/`. Modules talk only through the CLI, JSON contracts or AG-UI. | ✅ |
| Protected inputs / 50 MB / tags | **Violated by the earlier commit `e55f766`**, which committed and pushed the student pack. Remediation is T001 and Q-4. | ⚠️ must be fixed before cp1 |

Post-design re-check: no new violations. The agent/web adapters stay optional (Constitution II), and
the Complexity Tracking table below justifies them.

## Project Structure

### Documentation (this feature)

```text
specs/001-agentic-cell-finder/
├── spec.md          # (existing) the whole project specification
├── plan.md          # this file
├── research.md      # Phase 0: decisions D-1…D-14, open questions Q-1…Q-5
├── research/        # spike scripts and raw outputs (research only, not report evidence)
├── data-model.md    # Phase 1: entities and records
├── quickstart.md    # Phase 1: runnable validation guide
├── contracts/       # Phase 1: CLI, result records, Appendix A, agent tools and audit, AG-UI
└── tasks.md         # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
Makefile                 # setup check test all demo clean + m1, m1-* steps; later: agent, fixed, web
pyproject.toml           # uv; core = stdlib; extras: [dev] pytest, [agent] langgraph/langchain/ag-ui
src/dd2/                 # deterministic core (the "lib"). Nothing in it imports agent/ or web/
├── paths.py             # repo root, PDK_ROOT, given/ links, results/build dirs
├── provenance.py        # RunRecord: argv, input sha256, tool versions, UTC time, status
├── tools.py             # subprocess runner (timeout, captured logs), tool version probes
├── designs.py           # the 12-design catalog (name, top, -sv, required?)
├── mapping.py           # handout §2 flow + stat -json parsing; Table 1 writer
├── aig.py               # synth/restructured AIGER extraction; AIGER (aig/aag) reader
├── cuts.py              # 4-feasible cut enumeration with bit-parallel truth tables
├── cutcheck.py          # independent per-assignment cone simulation (no shared TT code)
├── boolfn.py            # TT ops: permute, flip, P/PN/NPN canon, expression parser/printer
├── liberty.py           # Liberty cell/pin/function reader
├── stage.py             # one-stage SP costing DP (Table 4 rows 5–7; reused by M2 costing)
├── redundancy.py        # Table 3 classifier + Table 4 / all-HD self-test
├── hdclasses.py         # class table of HD
├── cli.py, __main__.py  # `uv run python -m dd2 <step> …` (contract: contracts/cli.md)
└── (M2) costing.py areamodel.py rank.py libwriter.py requests.py measure.py cec.py sta.py select.py
tests/
├── unit/  contract/  integration/
└── broken/              # immutable negative cases (never edited by AI; see AGENTS.md)
results/m1/              # committed evidence (contracts/results-schema.md)
agent/dd2_agent/         # (US4) LangGraph graph, tools.py, policy.py, budget.py, audit.py, server.py
prompts/                 # (US4) versioned prompt files
web/                     # (US4) Vite/React app using DesignSystemStudio + Graphite Cyan + @ag-ui/client
docker/                  # flow.Dockerfile, agent.Dockerfile, web.Dockerfile, compose.yml
docs/                    # architecture.md, interface/ (Appendix A examples), runbook.md
```

**Structure decision**: a single Python project with a deterministic `src/dd2` core. `agent/` and
`web/` are optional adapters that reach the core only through the CLI and JSON contracts. This follows
the course layout (overview §5.1) and Backend.md's lib/app separation.

## Phases and milestones

| Phase | Milestone / tag | Contents | Spec stories |
|---|---|---|---|
| 0 | before anything else | Unblock: free disk, fix repository hygiene (T001), pin Yosys 0.33 (T004), Python venv | n/a |
| 1 | **M1 → `cp1` (from 27 Oct)** | setup/check/test targets, Table 1, AIGs ×12, cuts + check, HD class table, redundancy + Table 4 self-test, README, AI logs | US1 |
| 2 | M2 → `cp2` (from 3 Nov) | costing, area model, ranking, requests, Liberty writer, extended mapping + cec + gate-level sim, first Table 5 (estimated), OpenSTA. **Agent + fixed-choice version must exist** (overview §3). | US2, US4 (core) |
| 3 | M3 → `final` (10 Nov) | real cells from Option 1, greedy selection, final Table 5, best-of-both, cell curve, 30% experiment, reports, web UI, Docker | US2, US3, US4 |

Option 1 (US3) has its own cp1/cp2 rows, which the Option 1 sub-team owns. It is blocked here by R-0
and R-1 (research D-14).

## Complexity Tracking

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| LangGraph + AG-UI web app | The user chose an agentic system (overview §4.2). The spec asks for a reviewable live run (US4). | A CLI-only agent satisfies the course but not the user's request. It is still the required headless path. |
| Docker images | A reproducible clean-machine run for the TA, and read-only mounts that enforce rule 4.3.4 | Host-only setup cannot enforce read-only check scripts for an agent |
| Pinned old Yosys (0.33) | Table 1 must be reproduced (research D-2) | Host 0.70 changes the Table 1 conclusion |
