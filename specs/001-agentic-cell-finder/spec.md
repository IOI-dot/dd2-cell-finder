# Feature Specification: DD2 Cell Finder

**Feature Branch**: `main`  
**Created**: 2026-10-26  
**Status**: Draft  
**Input**: User description: "Plan the complete connected cell-finder project, including a future agentic experience and visual system, while delivering Option 2 Milestone 1 first."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Produce Milestone 1 evidence (Priority: P1)

A project member starts from a clean checkout and produces all course-required Milestone 1
evidence for the six required designs. They can inspect the generated baseline table, two
logic-graph variants per design, validated cut records, HD class table, and redundancy
self-test instead of trusting a narrative or hand-entered results.

**Why this priority**: Milestone 1 is the immediate graded deliverable and establishes the
trusted evidence pipeline required by all later work.

**Independent Test**: On a configured local machine, run the documented setup, environment
check, test, and Milestone 1 commands. The run is successful only when all required artifacts
and their provenance records exist and the validation suite passes.

**Acceptance Scenarios**:

1. **Given** the required supplied inputs and local prerequisites, **When** a member runs the
   Milestone 1 workflow, **Then** it produces baseline measurements for every required design,
   both required mapping choices, and both required library inputs.
2. **Given** a completed Milestone 1 run, **When** a member inspects its graph manifest,
   **Then** each required design has a distinct synthesis-derived graph and a distinct
   restructured graph, each with command, hash, and count provenance.
3. **Given** generated cut records, **When** their truth tables are independently checked over
   every possible leaf assignment, **Then** every saved valid cut passes and a deliberately
   corrupted truth table is rejected.
4. **Given** the complete HD combinational-cell corpus, **When** each eligible HD function is
   supplied to the redundancy checker, **Then** it is classified as already existing and the
   published exhaustive four-input reference totals are reproduced.

---

### User Story 2 - Discover and deliver useful missing functions (Priority: P2)

A project member uses the completed Option 2 workflow to identify repeated functions that are
not already economically represented in the HD library, rank them by measured benefit, and
issue unambiguous build requests to the Option 1 workflow. Returned, verified cells can be
used to repeat the same measurements without changing the original baseline.

**Why this priority**: This supplies the evidence-driven handoff that turns two separate
course options into one Option 3 project.

**Independent Test**: Starting from a candidate set and verified cell responses, the user can
produce a ranked selection, request records, a remapped comparison, and trace every claim to
saved flow outputs.

**Acceptance Scenarios**:

1. **Given** a function that is equivalent to an existing cell, an inverted existing cell, or
   a contained existing cell, **When** it is screened, **Then** it is not presented as a novel
   candidate unless its measured cost rule explicitly permits it.
2. **Given** a selected candidate, **When** Option 2 issues a build request, **Then** the
   request states a stable identifier, ordered inputs, one output, Boolean representation,
   truth table, sizing request, and estimated area.
3. **Given** a passing returned cell response, **When** the extended library is measured,
   **Then** the result distinguishes estimates from verified cell results and preserves the
   baseline and extended evidence separately.

---

### User Story 3 - Build and verify requested HD-compatible cells (Priority: P3)

A project member receives a bounded request from Option 2 and produces an HD-compatible
single-output cell, including the required layout, checks, characterization, library entry,
model, report, and a machine-readable response. A failed check prevents that cell from being
used in downstream mapping.

**Why this priority**: This is the delivery side of the Option 3 closed loop and is required
for final measured results, but starts after the active Milestone 1 scope.

**Independent Test**: A requested reference or candidate function can be taken through the
documented checks; a deliberately defective cell is rejected and cannot yield a passing
response.

**Acceptance Scenarios**:

1. **Given** a valid bounded function request, **When** the cell workflow completes, **Then**
   its response identifies the produced cell and supplies pass/fail results for every required
   verification category.
2. **Given** any failed physical, logical, characterization, or interface check, **When** the
   workflow creates its response, **Then** it reports failure and downstream mapping refuses
   the cell.

---

### User Story 4 - Review a bounded agent-assisted run (Priority: P4)

A project member can start an agent-assisted analysis, review its proposed actions and live
progress, approve or stop sensitive work, and inspect a durable record of the prompts,
tool invocations, limits, inputs, outputs, and final deterministic checks. The same core
course workflows remain usable without an AI service or a browser.

**Why this priority**: The user explicitly wants an agentic product, but course correctness
must remain deterministic and locally runnable.

**Independent Test**: An operator can run a bounded fixed-choice analysis, compare it with the
agent-assisted recommendation, inspect its complete audit record, and verify that prohibited
file changes or invalid tool arguments are refused.

**Acceptance Scenarios**:

1. **Given** a valid design-selection request, **When** an agentic run starts, **Then** it is
   assigned a unique run identifier, records its configured limits, and streams understandable
   lifecycle and tool-status updates.
2. **Given** a request outside the approved tool or file boundary, **When** the agent attempts
   it, **Then** deterministic policy rejects it, records the reason, and preserves protected
   files.
3. **Given** an unfinished or failed run, **When** a member reviews it, **Then** the interface
   clearly distinguishes completed, failed, paused-for-review, and cancelled work without
   presenting unverified claims as results.

---

### Edge Cases

- Required tools, PDK input, supplied design links, or a required library input are unavailable
  or malformed.
- A design contains sequential or asynchronous-reset behavior that must be transformed before
  graph extraction without changing the recorded source provenance.
- A cut has complemented edges, repeated/convergent leaves, or fewer than four leaves.
- A Boolean expression is malformed, uses an unsupported form, or represents a function only
  after input/output inversion or constants are tied.
- A candidate or returned cell exceeds the one-output/four-input boundary, has a mismatched
  truth table, or fails any verification result.
- An agent run exceeds its time, iteration, token, cost, or input-size budget; an approval is
  declined; or a streamed run terminates with an error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST support the connected Option 2 discovery path and Option 1
  verified-cell path through a documented request/response boundary.
- **FR-002**: The active delivery scope MUST be Option 2 Milestone 1; work outside that scope
  MUST be clearly identified as future work and MUST NOT be reported as completed evidence.
- **FR-003**: A clean local checkout MUST provide documented setup, environment-check, test,
  Milestone 1, and demonstration commands.
- **FR-004**: Setup MUST link supplied inputs and the local PDK without copying, modifying, or
  committing protected course materials.
- **FR-005**: The Milestone 1 workflow MUST generate and retain baseline measurements for all
  six required designs, each required mapping choice, and each required baseline library.
- **FR-006**: The Milestone 1 workflow MUST retain two independently generated logic-graph
  variants for each required design and record their provenance and structural summary.
- **FR-007**: The project MUST enumerate cuts with no more than four leaves, generate a truth
  table for every retained cut, and independently validate that table on every leaf assignment.
- **FR-008**: The project MUST create an HD Boolean class table from the appropriate library
  function definitions and must distinguish permutation/output-inversion grouping from NPN
  grouping in results.
- **FR-009**: The redundancy checker MUST classify candidates as `Exists`, `Exists with an
  inverter`, `Contained`, or `New`; it MUST use the full HD combinational-cell corpus and
  satisfy its all-HD and exhaustive four-input self-checks.
- **FR-010**: The validation suite MUST include deliberately broken cases for missing inputs,
  malformed library functions, corrupted cut truth tables, and an existing HD function submitted
  as a candidate.
- **FR-011**: Every reported measurement or conclusion MUST link to a saved input, command,
  raw output, parsed result, tool/PDK version, timestamp, and result status.
- **FR-012**: The future Option 2 flow MUST estimate and rank valid novel candidates, issue
  stable build requests, and compare baseline versus extended-library measurements without
  conflating estimated and verified results.
- **FR-013**: The future Option 1 flow MUST produce only cells that meet the course's physical,
  logical, characterization, library, and interface checks; non-passing cells MUST be refused
  by downstream mapping.
- **FR-014**: The future agent-assisted experience MUST expose only bounded, typed project
  actions; deterministic policy MUST validate arguments, authorize writes, enforce explicit
  run limits, and preserve an auditable record for each model and tool invocation.
- **FR-015**: The future user interface MUST present run progress, tool activity, result
  provenance, errors, and approval points in an accessible, responsive, dark-first technical
  visual system; it MUST not make AI-generated text appear equivalent to verified evidence.
- **FR-016**: The complete product MUST retain an offline-capable deterministic command-line
  path; an AI provider, browser, or remote service MUST not be required for course evaluation.
- **FR-017**: The project MUST maintain its machine-readable repository index, AI-use and
  mistake logs, source/license notices, protected-path policy, file-size limit, and immutable
  checkpoint-tag policy.

### Key Entities *(include if feature involves data)*

- **Design**: A supplied RTL input with its top module, source hash, synthesis configuration,
  and generated evidence.
- **Baseline measurement**: A single measured design/library/mapping-choice result with raw
  outputs and parsed metrics.
- **Logic graph artifact**: A provenance-bearing structural representation derived from one
  design and variant.
- **Cut record**: A graph root, ordered leaves, truth table, validation outcome, and source
  variant.
- **Boolean function/classification**: A bounded one-output function, its canonical forms, and
  redundancy classification with matching witness when applicable.
- **Candidate and build request**: A screened function and immutable cross-option request.
- **Cell response**: The Option 1 outcome, evidence locations, physical/functional status, and
  characterization metadata for exactly one request.
- **Run and audit event**: A bounded agent-assisted session, its configured limits, inputs,
  tool/model events, approvals, artifacts, and terminal status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a configured clean checkout, a member can complete the documented setup,
  check, tests, and Milestone 1 workflow without manual source or artifact editing.
- **SC-002**: Milestone 1 produces evidence for 6 required designs × 2 mapping choices × 2
  baseline libraries, and exactly 12 provenance-bearing logic-graph artifacts.
- **SC-003**: 100% of saved Milestone 1 cuts pass exhaustive independent truth-table validation;
  each deliberately corrupted cut fixture is rejected.
- **SC-004**: 100% of eligible full-HD combinational functions self-classify as `Exists`, and
  the exhaustive four-input classification totals match the course reference check.
- **SC-005**: Each reported result has a saved, inspectable provenance record; no hand-entered
  course calibration number is represented as a measurement.
- **SC-006**: Future Option 3 end-to-end delivery can issue at least one bounded build request,
  reject a non-passing response, and rerun a baseline-versus-extended comparison from retained
  artifacts.
- **SC-007**: Every agent-assisted run is uniquely identifiable and records its terminal state,
  configured limits, all tool/model invocations, and the deterministic verification outcome.
- **SC-008**: The future interface communicates a run state change, tool result, failure, and
  human approval state without relying only on color and remains usable at common desktop and
  mobile widths.

## Assumptions

- The project is an Option 3 submission, with Option 2 Milestone 1 as the only current
  implementation commitment.
- The local SKY130 PDK and supplied student pack remain authoritative inputs, and their exact
  revisions are captured by environment checks rather than assumed from this specification.
- The group identifier will be configured before permanent build-request cell names are emitted.
- The full-HD library is distinct from the reduced and usable baseline libraries and is used for
  redundancy screening.
- A future AI model provider is configurable and optional; model-assisted advice cannot alter
  deterministic pass/fail decisions.
- The visual product is a future companion to, rather than a replacement for, the local command
  line workflow.

## Scope Boundaries

### Included now

- The Option 2 Milestone 1 evidence pipeline, its deterministic checks, its project contracts,
  and its documentation.

### Planned after Milestone 1

- Candidate costing/ranking, request generation, extended-library measurement, timing and
  equivalence evaluation; Option 1 cell implementation and characterization; the bounded
  agent runtime; and the user interface.

### Explicitly excluded

- Changing supplied course inputs, PDK contents, check scripts, deliberately broken tests, or
  checkpoint tags; claiming unmeasured results; and requiring hosted infrastructure for local
  course evaluation.
