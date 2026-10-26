# Contract: cell request / response (overview Appendix A), frozen in week 1

The canonical examples are `docs/interface/request_example.json` and `response_example.json`, copied
from `repo_template/docs/interface/` without change. JSON Schemas will live in
`docs/interface/{request,response}.schema.json` (task T041).

## Request
| Field | Type | Rule |
|---|---|---|
| request_id | string | unique per run, e.g. `B-017` |
| name | string | `^dd2_g<N>__[a-z0-9]+_1$` (N = group number, Q-3); never clashes with HD |
| inputs | string[] | 1–4 unique names. Index k = truth-table bit k (`A` is the LSB) |
| output | string | exactly one |
| expression | string | over `inputs` with `! & \| ^ ( )` only |
| truth_table | string | `0x` + max(1, 2^n/4) hex digits, upper case (`0x077F` for n = 4). **Must equal the expression**, otherwise the maker refuses |
| sizing | `hd` \| `stack` | |
| estimated_area_um2 | number | from the area model |

## Response
`request_id`, `status: pass|fail|unsupported`, `reason: string|null`, `cell`, `stages`, `transistors`,
`width_sites`, `area_um2`, `files {gds, liberty, verilog, report}`,
`checks {drc: int, lvs, rc_lvs, truth_table, abutment: int, layers}`, `ngspice_sha256`, `tool_version`.

Rules that the consumer (Option 2) enforces in code:
1. `status != "pass"` means the cell is never added to a mapping library.
2. `files.liberty` holds exactly one `cell` group, whose name and pins equal the request's. Its
   `function` must evaluate to `truth_table`.
3. Appended inside `hd_reduced.lib`, Yosys must print `Imported 190 cell types` (or 189 + k for k cells).
4. A request with more than 4 inputs or more than 1 output must come back as `unsupported`.

The agreed test vector is the example: `!((C & D) | (A & B & (C | D)))` ↔ `0x077F`. Evaluating the
expression with A = bit 0 gives `0x77f`, which confirms the bit order (checked 2026-10-26).
