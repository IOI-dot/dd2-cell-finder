# Option 2 M2 measured evidence

Experimental flow: **pass**.
Checkpoint ready: **True**. See `readiness.json` for blockers.

Area values below use estimated cells; their timing/capacitances are placeholders.

| Design | Baseline best (um²) | Extended best (um²) | Reduction |
|---|---:|---:|---:|
| cpu8 | 4165.2448 | 4165.2448 | 0.000% |
| dsp8 | 5811.8240 | 5811.8240 | 0.000% |
| arlet6502 | 9325.1936 | 9325.1936 | 0.000% |
| uart_apb | 12773.5008 | 12773.5008 | 0.000% |
| risc8 | 28094.4448 | 28111.9616 | -0.062% |
| fir10 | 25463.1712 | 25463.1712 | 0.000% |
| spm | 2869.0016 | 2830.2144 | 1.352% |
| multiplier | 1736.6656 | 1736.6656 | 0.000% |
| TOTAL | 85633.3792 | 85650.8960 | -0.020% |

## Evidence

- `ranked_candidates.csv`, `redundancy_report.csv`, `candidate_occurrences.jsonl.gz`
- `area_model.json`, `area_model_fit.csv`, `area_model_validation.png`
- `requests/`, `requests.json`, `selection.json`, `extended_library.json`
- `table5_estimated.csv`, `best_of_both_estimated.csv`, `area_reduction_estimated.png`
- `mapping/`: scripts, netlists, hashes, mapping/CEC/sequential-equivalence/timing logs
- `reference_count_review.json`, `reference_count_witnesses.csv`

## Limitations

- Ranking is a heuristic; the remapped area, not occurrence frequency, is the measured result.
- Cost features describe explicit Boolean realizations, not transistor extraction from installed HD cells.
- Table 4 disposition: TA accepted recorded difference. See reference_count_review.json.
- Tutorial sources/testbenches are unchanged earlier submissions, installed outside git. GLS is functional, with no SDF or timing-check claim.
- TOTAL and the ranking objective cover the six required benchmark designs; tutorial rows are shown separately.
- Final reports, real-cell results and sensitivity/greedy experiments are not M2 outputs.
