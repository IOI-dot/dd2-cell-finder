# GB4 · Option 2: Finding Cells Worth Adding

**For the TA: open [TA_M2/README.md](TA_M2/README.md).**
It contains the three figures, key CSV tables, measured results and the Table 4 clarification.
Figures can also be opened directly from [TA_M2/figures](TA_M2/figures/).

Group: **GB4**, numeric cell prefix `dd2_g4__`. Omar Abdel Motalb, 900232118.
Also listed by the team: Noor Elshahidi and Mohamed Azouz. Complete the remaining member details before submission.
AI is used as a development aid; the runtime needs no AI model or API key.

## Status

The latest saved WSL M2 experiment passes the mapping, equivalence, timing and
tutorial-simulation checks. See [readiness.json](results/m2/readiness.json).
Full checkpoint readiness remains **false** because Table 4 gives six verified
qualifying classes against the handout's five. No instructor correction or TA
acceptance is assumed. See [the six examples and question](TA_M2/TABLE4_CLARIFICATION.md).

Measured savings can be zero or negative. The displayed results preserve those
outcomes. The ranking graph is a heuristic; measured remapping establishes savings.

## Repository map

| Folder | Purpose |
|---|---|
| [TA_M2/](TA_M2/) | Small, obvious meeting folder: figures, key tables and Table 4 evidence |
| [src/dd2/](src/dd2/) | M1 functions and checks |
| [src/dd2m2/](src/dd2m2/) | Costing/model, ranking, requests/Liberty, mapping, checks, timing and tutorials |
| [tests/](tests/) | Active tests and deliberately broken cases |
| [results/m1/](results/m1/), [results/m2/](results/m2/) | Full generated measurements, netlists, scripts and logs |
| [libs/](libs/) | Generated estimated-cell library |
| [config/](config/) | GB4 identification; host-specific tool selection is ignored by Git |
| [docs/interface/](docs/interface/) | Cell request/response schemas and examples |
| [docs/option2-m2-plan.md](docs/option2-m2-plan.md) | Current Option 2 scope, validation and remaining work |
| [tools/](tools/) | Pinned tool installer for reproducible setup |
| [ai/](ai/) | AI-use and caught-error evidence |
| src/cellgen/, agent/, web/, cells/, results/option1/, results/option3/ | Retained optional generator/platform experiments; outside the submitted Option 2 M2 scope |
| report/ | Final reports and their sources, due at the final milestone |

## Setup and commands

Use Ubuntu/WSL, Python >=3.11, recent OpenSTA, Yosys >=0.34 and Icarus >=13.
The tool installer selects the SHA256-pinned official OSS CAD Suite release
2026-10-27. Keep Ubuntu Yosys 0.33 and its ABC separately for the M1 reference table.

External course inputs stay outside Git:

- `GIVEN`: defaults to `~/DD2_Project1_student_pack/given`.
- `PDK_ROOT`: defaults to `~/dd2-inputs`, containing `sky130A` and the full HD Liberty.
- `TUTORIALS`: defaults to `~/dd2-inputs/tutorials`, with `spm/` and `multiplier/`.
  These contain the original Tutorial 4 SPM/CSADD/TCMP sources and SPM testbench,
  and Tutorial 2 multiplier source and exhaustive testbench. Keep their licence notices.

```sh
export PATH="$HOME/.local/bin:$PATH"
make setup
.venv/bin/python tools/install_course_tools.py
make check-versions
make test
make all
```

`make setup` links `given/`, `pdk/` and `tutorials/`; it does not supply these inputs.
This project consumes the full HD Liberty; a Liberty-only input directory is not a
complete physical PDK. Install/build OpenSTA separately as in the course setup.
Tool binaries, environments, supplied inputs and download/update ZIPs stay outside Git.

| Command | Purpose |
|---|---|
| `make check`, `make check-versions` | Input/tool checks; strict minimum-version check |
| `make test` | Complete Option 2 tests and frozen broken-case hashes |
| `make m1` | Reference Table 1, AIGs, cuts, HD classes and redundancy self-test using reference Yosys |
| `make m2` | Six benchmarks plus tutorials: estimated-cell experiment, CEC, timing, GLS and plots |
| `make ta` | Refresh the TA folder from existing results; no experiment rerun |
| `make all` | M1 followed by M2 and TA-folder generation |
| `make readiness` | Print recorded blockers; returns nonzero while any remain |
| `make demo IN=given/designs/cpu8.v TOP=cpu8` | Existing M1 single-design demo; full final demo remains pending |

The Makefile also exposes each M1/M2 step separately. On another installation,
override `REFERENCE_YOSYS` and `REFERENCE_ABC` when the reference binaries are elsewhere.
All M2 baseline/extended comparisons use the same selected toolchain and A/B recipes.
M1 reference numbers and M2 newer-tool numbers are distinct experiments.

## Checks and limits

Every cut is checked against exhaustive cut simulation. Redundancy compares
against the full HD combinational library. New candidate stages have at most
three transistors in series; native HD calibration permits four-stack cells.
Cost features describe explicit realizations, not extracted HD transistor counts.
The fitted model covers HD x1 cells with up to four inputs and reports held-out error.

ABC CEC checks RTL-derived gold against the mapped circuits with named state
cutpoints; a separate bounded Yosys induction attempt is diagnostic. Tutorial GLS
runs the original testbenches with functional models from the exact mapping Liberty.
It is zero-delay functional simulation, without SDF or real timing-check validation.
New-cell timing and capacitance are placeholders. OpenSTA reports declared
pre-layout comparisons, not characterized-cell or signoff timing.

## Final milestone

Still required later: real generator cells, greedy final selection, real-area
reruns, the cell-by-cell curve, the 30% sensitivity experiment, final technical
and AI reports, and the full unseen-design workflow/demo.

The team has selected **Option 2**. Additional generator, agent and studio work is
retained in its existing directories and is optional. Historical filenames/commands
such as `option3.py`, `make o3` and `results/option3/` refer to an extra real-cell
experiment; they do not declare our submitted project option.

Default `make setup`, `make check`, `make test` and `make all` cover Option 2.
The full retained work remains available through `make setup-extended`,
`make check-extended`, `make test-extended`, `make all-extended` and the existing
explicit generator/studio targets. Do not claim the whole extended suite passed
from an Option 2-only test log.

## M2 source files

- `src/dd2m2/pipeline.py`: orchestrates the run.
- `cost.py`: costs proposed implementations, fits the regression and predicts area.
- `areamodel.py`: collects HD calibration data.
- `candidates.py`, `cones.py`: redundancy/ranking/requests and reclaimable mapped logic.
- `library.py`: writes the extended Liberty.
- `measure.py`, `evaluate.py`: baseline/extended runs, Yosys/ABC checks and OpenSTA.
- `tutorials.py`: tutorial discovery and original-bench RTL/GLS.
- `report.py`: plots, readiness, summaries and the TA meeting copies.
- `flow.py`: preserves the old public function names after the module split.
