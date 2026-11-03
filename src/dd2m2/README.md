# src/dd2m2: Option 2, Milestone 2

`make m2` runs `pipeline.run`, which calls one module per step, in this order:

| Step | Module | What it does | Writes to `results/m2/` |
|---|---|---|---|
| 0 | `environment.py` | Checks the tools and the supplied inputs, and records their versions | `environment.json` |
| 1 | `areamodel.py` | Fits the area model on the HD x1 cells and reports its held-out error | `area_model.json`, `area_model_fit.csv` |
| 2 | `measure.py` (`baseline`) | Maps every design onto the reduced library with scripts A and B, proved with ABC cec | `mapping/*/baseline/`, `baseline_mappings.json` |
| 3 | `candidates.py` (`candidates`) | Classifies and costs every function, and ranks them by mapped-cone savings | `ranked_candidates.csv`, `candidates.json` |
| 4 | `candidates.py` (`requests`), `library.py` | Writes the cell requests (Appendix A) and the extended Liberty | `requests/`, `hd_extended_estimated.lib` |
| 5 | `measure.py` (`measure`) | Maps every design again with the new cells, proved with cec and timed with OpenSTA | `mapping/*/extended/`, `table5_estimated.csv`, `best_of_both_estimated.csv` |
| 6 | `reference.py` | Writes the Table 4 question: six verified witnesses against five in the handout | `reference_count_*` |
| 7 | `tutorials.py` | Runs the original tutorial testbenches on the mapped netlists | `tutorial_simulations/` |
| 8 | `report.py` | Figures, `readiness.json`, `summary.md`, and the TA copies in `TA_M2/` | `*.png`, `readiness.json`, `summary.md` |

Helpers: `cost.py` (explicit CMOS realizations and the model fit), `cones.py` (mapped cones), `evaluate.py` (Yosys,
ABC cec and OpenSTA runs), `tables.py` (CSV writing). `flow.py` keeps the names the command line and the tests use.
`option3.py` is a retained optional real-cell remapping experiment (historical filename). It does not change the submitted Option 2 scope.

Each step can also run alone: `make m2-fit`, `m2-baseline`, `m2-candidates`, `m2-library`, `m2-map`, `m2-plots`.
