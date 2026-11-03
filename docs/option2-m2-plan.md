# Option 2: current milestone status

Option 2's flow is a deterministic command-line workflow; it runs no model. It is one half of the group's
Option 3 project: Option 1 (`src/cellgen`) builds the cells Option 2 asks for, and `docs/roadmap.md` plans
the connection. The Table 4 disagreement stays documented as unresolved.

## Completed and verified on WSL

- Reference Table 1, AIG extraction, exhaustive cut checks and HD classification.
- Candidate classification, full-HD redundancy and explicit CMOS costs.
- HD x1 single/multi-stage area model and held-out prediction error.
- Mapped-cone area ranking, requests and an importable extended Liberty.
- Both-script baseline/extended mappings of six benchmarks and two tutorials.
- Required ABC CEC, OpenSTA comparisons and original tutorial RTL/GLS tests.
- Generated tables, figures, netlists, tool versions, hashes and logs.

See results/m1/summary.md and results/m2/readiness.json for measured status.
The TA-facing copies in TA_M2/ are refreshed by make ta or make m2.

## Unresolved reference item

The limited single-stage row of Table 4 gives six verified witnesses; the
handout lists five. Preserve both numbers. Do not exclude a function merely
to force agreement, change the original checks, or infer TA acceptance.
The checker has not fully matched the reference. Ask which restriction excludes
one witness, or whether the reference needs a correction.

## Reproducibility and presentation

M1 uses separate reference Yosys/ABC binaries; M2 uses the pinned newer suite.
Keep course inputs, tutorials, the PDK, tool installations and environments
outside Git. Generated evidence stays in results/, with a small TA_M2/ gallery.
Original M1 code/checks and frozen broken cases remain unchanged.

The original group README still needs the other members' names/IDs.

## Final milestone

Real generator responses; real-area reruns; greedy final selection; cell-by-cell
curve; 30% sensitivity; final technical/AI reports; complete unseen-design demo.
