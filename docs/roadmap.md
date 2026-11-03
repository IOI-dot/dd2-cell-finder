# Roadmap: from Atlas Cell Studio to Option 3

For the five-person team. It records what the studio does today, how Options 1 and 2 will be connected, what
we plan to add for the demo, and the order of work up to the interview. Measured results are not repeated here:
they live in `results/`, and the Evidence tab shows them.

## Dates

| Date | Event | What it needs |
| --- | --- | --- |
| From Tue 3 Nov | Checkpoint 2 with the TA, tag `cp2` | Option 1 M2, Option 2 M2, the agent on the test cells and its fixed-choice version |
| Tue 10 Nov | Submission, tag `final` | A clean clone passes `make check` and `make test`, and every deliverable exists |
| Wed 11 Nov | Interview with Dr. Shalan | A demo from a clean checkout, on new functions or a new design given on the day |

No tag exists yet for `cp2`. Nobody moves a checkpoint tag once its deadline has passed.

## What exists today

### Option 1 (`src/cellgen`)

Milestones 1 and 2 are built: network, Euler ordering, layout, DRC, abutment, extraction, LVS, RC-LVS, SPICE,
Verilog model, characterizer and OpenSTA timing. Records are in `results/option1/`.

### Option 2 (`src/dd2`)

Milestone 1 is built. Milestone 2 is being delivered separately by a teammate, and is not in the studio yet.

### The agent (`agent/dd2_agent`)

A bounded LangGraph agent drives GPT through the Codex CLI. The model picks a next step from a closed list, code
checks each reply, and only the check scripts decide whether a cell passes.

- **Questions:** it answers questions about the project and about the current run. A number in an answer must
  appear in what it was given, or code replaces the answer.
- **Opening steps:** when a person asks to see a step, or why something happened in one, it opens that step.
- **Nothing to build:** a constant, a plain wire or an unused input is explained at once, with no tool or model call.
- **Crashes:** a crashed tool ends the run, and its error is shown in plain words.

### The studio (`web/`)

| Area | What it does |
| --- | --- |
| Pipeline, left | Each step with its state, time and estimate. Pressing one opens it. |
| Run, middle | The run in order, with real tables and graphs, following the live step. A step's page adds every call and its raw log. |
| Agent, right | The chat, streamed, with short updates and a closing summary. Model, tool and guardrail actions stay one line until opened. |
| Mic | Speech to text with Parakeet on this machine. The audio is never saved or sent anywhere. |
| Evidence tab | The saved records of Option 1 Milestone 2. |

Rules the interface follows: no game elements, no scroll areas inside the page, no cut-off text, and small 3D views
only where they explain something.

## How Options 1 and 2 connect

The contract is Appendix A, unchanged. `docs/interface/` holds its schemas, `dd2.interface` validates both sides,
`cellgen.request` reads a request, and `cellgen.flow.response` writes a response. So most of the connection already
exists, and what is missing is the loop around it.

```text
design
  → Option 2: map, find cuts, classify, cost, rank
  → one Appendix A request per chosen candidate (requests/)
  → Option 1: build and verify that cell, as a studio run does today
  → Appendix A response (cells/<name>/response.json)
  → Option 2: accept only "pass", add the cell to the Liberty, remap, check cec, measure
  → savings for this design
```

### The handshake

These are the steps of section 7.1 of the implementation plan.

1. `discovery.requests.write` writes a request with the exact ordered inputs, expression, truth table, cell name,
   sizing and estimated area.
2. `foundry.request.validate` checks the schema and that expression and truth table agree, before any EDA tool runs.
3. `foundry.publish` returns `pass`, `fail` or `unsupported`, with evidence.
4. `discovery.library.extend` accepts only `pass`, and adds the cell to `hd_reduced.lib` inside the same library group.
5. The mapping must pass `cec`, or its saving is not counted. A negative saving is reported as it is.

Failures keep their meaning from section 7.2 of the plan. More than 4 inputs or several outputs is `unsupported` and
the candidate is excluded. A failed cell is never added to the library, and its evidence stays for audit.

### The agent

The Option 2 agent is a second bounded graph that reuses the same guardrails, audit log, budget and tool policy. Its
tools are `discover_candidates`, `request_cell` and `map_design`. The model chooses which ranked candidate to request
next, and when to stop. It cannot change a ranking, an area, a mapping result or a `cec` verdict. `request_cell` runs
the existing Option 1 agent, so a whole design run contains several complete cell runs.

### The studio

No new layout is needed, so it stays uncrowded. A run gains a level above the one we have:

- **Pipeline:** Discovery, Candidates, Cells, Mapping and Savings. Under Cells, one row per requested cell.
- **Run:** new views for the ranked candidates, the mapped result and the savings. Pressing a cell opens today's
  cell run unchanged.
- **Agent:** the same chat. "Which function saved the most?" opens that step.
- **Evidence:** a second section for Option 2, beside Option 1.

### What we need from the Option 2 push

Before wiring anything, confirm these four things in the pushed code:

1. The command that takes a design and writes ranked candidates, and its output file.
2. Where requests are written, and whether they pass `dd2.interface.validate_request`.
3. How a passing cell's Liberty group is added, and what remap command follows.
4. Where the area and `cec` results are saved.

## What we plan to add for the demo

| Priority | Feature | Why it impresses | Work | Where it lives |
| --- | --- | --- | --- | --- |
| 1 | Closed loop, design to proven savings | It is the whole point of Option 3 | The connection above | The studio's design run |
| 2 | Try to break it, live | Trust is shown, not claimed | Small: a prepared list of attacks and a page of refusals from the audit log | Evidence, no new workbench UI |
| 3 | Recovery from a real failure | Shows the agent reasoning on a real defect | Medium: a failing setting the agent can recover from, shown as a normal run | A normal run, with no new UI |
| 4 | Map of every 4-input function | A new dataset: all 222 classes, and what SKY130 HD lacks | Medium: mostly machine time, run overnight in batches, and one chart | One section in Evidence |
| 5 | Real silicon | Physical chips | Feasibility check only: whether a SKY130 shuttle is open, and its cost and rules | A note in the report |

Item 5 cannot finish before the course ends, so it is not part of any deadline. Items 2 and 3 must use the broken cases
as they are: `tests/broken/` and its checksums stay untouched, and new cases go to `tests/broken_proposed/`. Item 4
starts only after Items 1 to 3, and each result must come from the same check scripts.

## Order of work

### Now, for `cp2`

1. Commit the studio work on a branch with a proper name. `foundry-game` no longer describes it.
2. Rerun `dd2_agent.compare` with the code frozen, then `python -m cellgen.m2 summary`. The current
   `results/option1/m2/agent_vs_fixed.csv` is partial and stale, and the Evidence tab shows it.
3. Run an independent verification, then update `README.md` and `ai/`.
4. Merge, and tag `cp2` once the team agrees. Option 2's M2 must be in the tag.

### After the Option 2 push

1. Confirm the four points above, then connect the loop from the command line first.
2. Add the Option 2 agent and its fixed-choice version, with the same logs.
3. Add the design run to the studio.

### Before `final`

1. Finish Option 1 M3: every test cell characterized with its Liberty cell, Verilog model and response, the round
   trip of section 3.3, and a small design mapped, simulated and timed.
2. Rehearse from a clean clone, including a function and a design chosen by someone else.

## Risks

- **The mic depends on this machine.** It uses the model Handy keeps. On any other machine the mic reports that the
  model is missing, and everything else works. Do not rely on it for the graded part of the demo.
- **Hard cells take minutes.** Some multi-stage cells search for several minutes. For the demo, know which kinds are
  slow, and start with a fast one.
- **The model can be unavailable.** The agent needs the Codex CLI and a login, and the TA should confirm this is
  acceptable. A bare expression still builds, and the deterministic flow runs without a model.
- **Disk space.** Docker has filled this disk twice, so check free space before long batches such as Item 4.
