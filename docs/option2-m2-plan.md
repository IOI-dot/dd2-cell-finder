# Option 2: current milestone status

The group has selected Option 2. Its flow is deterministic and runs no model.
The existing modular implementation, measured evidence and TA folder are retained.
Generator/agent/studio work stays available as optional supporting experiments;
it is not the submitted project option. The TA accepted the Table 4 result as submitted, per the team.

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

## Table 4 disposition

The limited single-stage row gives six verified witnesses and the handout lists
five. The TA accepted the recorded result for GB4, per the team. The recorded
counts, expressions and original self-test remain the same.

## Reproducibility and presentation

M1 uses separate reference Yosys/ABC binaries; M2 uses the pinned newer suite.
Keep course inputs, tutorials, the PDK, tool installations and environments
outside Git. Generated evidence stays in results/, with a small TA_M2/ gallery.
Original M1 code/checks and frozen broken cases remain unchanged.

The original group README still needs the other members' names/IDs.

## Final milestone

Run the estimated and real M3 targets, write the final reports and rehearse the
unseen-design demo. See the README for the run order and generator requirements.

## Default commands

make setup/check/test/all run Option 2 only. Extended targets preserve the extra
generator/platform dependencies and tests. All original Option 2 test cases and
assertions remain active, including the two original Liberty/CEC broken cases.
