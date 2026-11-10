# Milestone 3 results

- [estimated-best/](estimated-best/) contains the estimated-area experiment for the ten chosen requests.
- [real/](real/) measures the same request IDs using characterized Liberty.
- [real/sensitivity/](real/sensitivity/) repeats the mappings with the first candidate's area reduced by 30%.
- [real-run.log](real-run.log) records baseline and extended mapping, equivalence, and tutorial simulation.
- [CellWeaver responses](../../libs/cellweaver/) include original Liberty and the remap copies, plus layout and verification evidence.

The six required Table 2 benchmarks define the aggregate in the CSV and the
curve. SPM and multiplier are tutorial designs. pic16 and p16c5x are reported
separately for the same-ISA comparison. Mapping folders retain the mapped
Verilog, saved AIGs, tool scripts, CEC, and OpenSTA evidence.
