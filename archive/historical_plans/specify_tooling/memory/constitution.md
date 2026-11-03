<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Modified principles: none; initial adoption.
- Added sections: Core Principles; Project Constraints; Delivery Workflow; Governance.
- Removed sections: none.
- Follow-up TODOs: confirm the group-number prefix and the course-approved model/API provider
  before an agentic run is implemented.
-->
# DD2 Cell Finder Constitution

## Core Principles

### I. Course Evidence Is the Source of Truth

Every pass/fail decision MUST come from committed check scripts or tool output. Every reported
number MUST be traceable to a saved artifact in `results/`; course handout values are calibration
references, never substitute measurements. The PDK, supplied inputs, check scripts, and deliberately
broken test cases are protected and MUST NOT be weakened, replaced, or modified by an assistant.

### II. Local-First, Reproducible Tooling

The deliverable MUST run from a clean checkout with documented commands. The primary product is a
local Python/Yosys/ABC/OpenSTA CLI pipeline, not a hosted service. External services, databases, or
web backends require a separately approved feature specification and MUST remain optional adapters;
they must never become a prerequisite for the TA's offline evaluation.

### III. Test-Driven Development Is Non-Negotiable

Every behavioral change MUST follow red-green-refactor: write a focused failing test, run it to show
failure, implement the smallest change, then run the relevant tests. Each verification check needs an
immutable broken case under `tests/broken/` that proves the check can fail. `make check`, `make test`,
and the feature-specific flow are mandatory quality gates before a checkpoint or completion claim.

### IV. Bounded, Auditable Agentic Automation

The agentic system MUST be self-contained and invocable from one documented command. Tool wrappers
MUST have explicit schemas; the orchestrator MUST enforce file permissions, maximum iterations,
time, token/cost limits, input-size limits, retries/timeouts, and a correlation/run ID. Prompts are
versioned files. Each model and tool call MUST be logged as JSONL with its inputs, result artifact,
and final check result. Critical decisions and protected-path writes remain deterministic code, not
model choices. A fixed-choice pipeline provides the required comparison baseline.

### V. Explicit Boundaries and Indexed Context

`index.yml` is the machine-readable map of repository ownership, protected paths, authoritative
inputs, generated evidence, and tool assumptions. `AGENTS.md` tells assistants to read it before
changing files and to update it when paths or responsibilities change. `Backend.md` is guidance for
the local agent platform; `DesignSystemStudio/` is the visual source only for an approved future UI.
Modules communicate only through documented CLI, data, or typed-tool interfaces.

## Project Constraints

This is an Option 3 project: Option 2 discovers/ranks missing functions and measures their effect;
Option 1 later builds and characterizes the selected HD-compatible cells. The active implementation
scope remains Option 2 Milestone 1 until a later feature specification expands it.

The reduced 189-cell HD library is the mapping baseline. The full single-output combinational HD
library is used for redundancy checking. Candidate functions have at most four inputs and one output.
The Appendix A request/response format is the immutable interface between Options 1 and 2 once the
group prefix is selected.

The project MUST preserve supplied design license notices, not commit PDK copies, supplied-file
copies, build trees, secrets, or files larger than 50 MB, and never move `cp1`, `cp2`, or `final`
after their deadlines. AI-assisted commits require the prescribed `AI-assisted: <tool>/<model>`
trailer; `ai/use_log.md` and `ai/mistakes_log.md` are maintained from the start.

## Delivery Workflow

Use Spec Kit as the controlling delivery workflow: constitution, specification, clarification where
needed, plan, tasks, analysis, then implementation. TDD governs every implementation task within
that workflow. Specifications state acceptance criteria and protected boundaries before code changes;
plans and task lists trace each requirement to a test and an evidence artifact.

Before a feature is considered complete, run its focused tests, `make test`, and all applicable flow
commands. Save logs, manifests, inputs, tool versions, and raw outputs that support measurements in
`results/`. A claimed result without its saved output is a failure.

## Governance

This constitution supersedes informal project practices while remaining subordinate to the course
handouts and their grading rules. Amendments require a documented rationale, a semantic-version bump,
and a review of the effect on `AGENTS.md`, `index.yml`, active specifications, tasks, and tests.

Use MAJOR for incompatible principle changes, MINOR for new or materially expanded principles, and
PATCH for clarifications. Each specification, plan, task list, review, and checkpoint must verify
compliance with this constitution. The repository's agent guidance is `AGENTS.md`; its structural
map is `index.yml`.

**Version**: 1.0.0 | **Ratified**: 2026-10-26 | **Last Amended**: 2026-10-26
