# Data Model: DD2 Cell Finder

All records are JSON (or JSONL/CSV for bulk data) and are written by the flow, never by hand. Shared
conventions:

- `sha256`: hex digest of the file's bytes.
- Times are UTC ISO-8601.
- Truth tables (`tt`) are hex strings with input k = bit k of the row index (Appendix A, so `A` is the LSB).
- Paths are relative to the repository root.

## M1 entities

### Design (static catalog, `src/dd2/designs.py`)
| Field | Type | Rule |
|---|---|---|
| name | str | One of the 12 names in Option 2 Table 2 |
| top | str | `cpu8, dsp8, cpu, uart_apb_master, cpu, fir10, P16C5x, PIC16C5x, x18, cpu, xfir, chacha` |
| source | path | `given/designs/<name>.v` |
| sv | bool | true only for `pic1826` |
| required | bool | true for cpu8, dsp8, arlet6502, uart_apb, risc8, fir10 |

### RunRecord (provenance, embedded in every result)
`argv: list[str]`, `cwd`, `inputs: {path: sha256}`, `tools: {yosys: "0.33 …", abc: "…", python: "…"}`,
`pdk: {root, ciel_version}`, `started`, `finished`, `exit_code`, `status: pass|fail|error`, `logs: [path]`.
Rule: a result whose RunRecord lacks `status: pass` and an existing log path counts as a failure.

### BaselineMeasurement (`results/m1/baseline/<design>/<lib>/<script>/result.json`)
`design`, `library: reduced|usable`, `script: A|B`, `area_um2: float`, `cells: int`, `cell_counts: {cell: n}`,
`run: RunRecord`. Unique key: (design, library, script). The Table 1 matrix must be complete (6×2×2 = 24).
Derived file: `results/m1/table1.csv`, with columns design, script, usable, reduced, handout_usable,
handout_reduced, delta_pct, yosys_version.

### AigArtifact (`results/m1/aigs/<design>/<variant>.json` + the `.aig` itself)
`design`, `variant: synth|restructured`, `aig_path`, `aig_sha256`, `header: {M, I, L, O, A}`,
`ffs_after_synth: int`, `commands: [str]`, `run: RunRecord`.
Rule: the restructured variant's `commands` must contain `dch` and its sha256 must differ from synth.
The manifest `results/m1/aigs/manifest.json` lists exactly 12 required artifacts.

### Cut
`root: int` (AIG literal/2), `leaves: list[int]` (sorted ascending, 1 ≤ len ≤ 4), `tt: hex`,
`arity: int`, `p_class`, `pn_class`, `npn_class` (all hex).
Rule: `tt` is over `leaves` in the listed order. A trivial cut (`leaves == [root]`) is excluded from class counts.

### CutValidation (`results/m1/cuts/<design>/<variant>.summary.json`)
`cuts_total`, `cuts_checked` (must equal `cuts_total`), `failures: list[{root, leaves, stored, simulated}]`
(must be empty), `nodes`, `max_cuts_per_node`, `pn_class_histogram: {pn_hex: count}`, `npn_classes: int`,
`full_list: build/…jsonl.gz (sha256)`, `sample: results/…sample.jsonl`, `run: RunRecord`.
The state is `pass` only if `cuts_checked == cuts_total` and there are no failures.

### BooleanFunction
`arity ≤ 6` (HD cells; candidates ≤ 4), `tt`, `inputs: [str]`, `expression?: str`.
Validation: `tt < 2^(2^arity)`; when an expression is present, its evaluated table must equal `tt`.

### HdCell (`results/m1/hd_classes.json`)
`name`, `inputs`, `arity`, `tt`, `area_um2`, `in_reduced: bool`, `p_class`, `pn_class`, `npn_class`,
`essential_inputs: int`.

### RedundancyMatch
`candidate: BooleanFunction`, `class: Exists|ExistsWithInverter|Contained|New`,
`witness?: {cell, input_map: {hd_pin: candidate_input|0|1}, inverted: output|<input>|null}`.
Rule: the order is fixed (Exists → inverter → Contained → New); first match wins.

### SelfTestReport (`results/m1/redundancy/self_test.json`)
`hd_cells_total`, `hd_cells_exists` (must be equal), `table4: [{row, handout, measured, status: match|mismatch|definition-open, witnesses?}]`, `run`.
Overall `pass` = all HD cells Exists **and** rows 1–5 and 7 match. Row 6 is reported (Q-1).

## M2+ entities (planned)

| Entity | Key fields | Notes |
|---|---|---|
| CandidateClass | pn_class, occurrences per design/variant, stages, inverters, transistors, max_series, redundancy | Costing at most 3 in series per stage |
| AreaModel | form (`sites = a + b·T`), coefficients, fit set (HD x1 cells), per-cell residuals, MAE/max error | Needs HD SPICE transistor counts (R-1) |
| RankedCandidate | candidate, est_area, replaced_area, est_saving, rank | |
| CellRequest | Appendix A request (contracts/appendix-a.md) | `name` = `dd2_g<N>__<fn>_1` (Q-3) |
| CellResponse | Appendix A response | `status != pass` means the cell is never mapped |
| ExtendedLibrary | path, base sha256, added cells, `Imported N cell types` check (N = 189 + k) | |
| MappingResult | baseline/extended × A/B, area, new-cell instances, cec status, gate-level sim status, STA worst delay | Table 5 row |
| SelectionStep | k, added cell, total best-of-both area, kept? | Greedy curve |

## Agent entities (US4, planned)

| Entity | Fields | State transitions |
|---|---|---|
| AgentRun | run_id (`A-<dd>-<nn>`), mode `agent|fixed`, input, limits {iterations, seconds, tokens_in/out, usd, input_bytes}, model {name, version, settings}, prompt refs, status | `created → running → (paused_for_approval ↔ running) → passed|failed|cancelled|budget_exceeded` |
| AuditEvent | JSONL per Appendix B: run, step, agent, kind `tool|model|policy|approval|result`, tool/args/result or model/prompt/tokens/decision | append-only |
| Approval | interrupt_id, tool_call, reason, response `approve|edit|reject`, by, at | |
