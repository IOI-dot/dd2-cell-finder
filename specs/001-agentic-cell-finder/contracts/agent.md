# Contract: agent tools, audit log and AG-UI stream (US4, planned for M2/M3)

## Tools (Pydantic models, `strict=True`; the agent sees only these)
| Tool | Args | Reads | Writes | Approval |
|---|---|---|---|---|
| `list_designs` | n/a | catalog | n/a | no |
| `run_baseline` | design, library ∈ {reduced}, script ∈ {A,B} | given/, pdk | `runs/<run>/baseline/` | no |
| `extract_candidates` | design, variant | `runs/<run>/` | `runs/<run>/candidates.json` | no |
| `classify` | tt, arity ≤ 4 | full HD lib | n/a | no |
| `write_requests` | candidate ids (≤ 5) | candidates | `runs/<run>/requests/*.json` | **yes** (sends work to Option 1) |
| `map_extended` | design, library_path under `runs/<run>/`, script | | `runs/<run>/mapping/` | no |
| `check_equivalence` | mapping id | | `runs/<run>/cec/` | no (the verdict is deterministic) |
| `select_greedy_step` | candidate id | | `runs/<run>/selection.json` | no |
| `finish` | summary, result_file | | final audit line | n/a |

Policy (`agent/dd2_agent/policy.py`, deterministic):
- Writes only under `runs/<run_id>/`. Any path that resolves into `given/`, `pdk/`, `tests/`,
  `src/`, `results/` or `.specify/` is refused and logged as `kind: policy`.
- Arguments are validated before execution. The tool layer clips sizes (≤ 5 requests per call,
  arity ≤ 4).
- Budget middleware: `max_iterations=25`, `max_seconds=1800`, `max_tokens_in=400k`,
  `max_tokens_out=40k`, `max_usd` from `config/agent.toml` (the instructor's budget, Q-2), and
  `max_input_bytes=2 MB`. When a budget is exceeded the run stops with status `budget_exceeded`.
- Model calls get a timeout and 2 retries with backoff; a fallback model is configurable.
  Prompts come from `prompts/<agent>.md`, logged as `prompts/<agent>.md@<git-short-hash>`.

## Audit log: `ai/runs/<run_id>.jsonl` (overview Appendix B, verbatim keys)
```json
{"run":"A-12-03","step":17,"agent":"selector","kind":"tool","tool":"map_extended","args":{...},"result":"runs/A-12-03/mapping/17.json"}
{"run":"A-12-03","step":18,"agent":"selector","kind":"model","model":"<name@version>","prompt":"prompts/selector.md@9e1f","tokens_in":6120,"tokens_out":410,"decision":"..."}
{"run":"A-12-03","step":40,"kind":"result","status":"pass","checks":"runs/A-12-03/checks.json"}
```
The last line records pass or fail **and** names the check file. A `pass` without that file is a failure.

## AG-UI stream (`POST /agent` via `add_langgraph_fastapi_endpoint`)
The UI consumes the standard events `RUN_STARTED`, `STEP_STARTED/FINISHED`, `TOOL_CALL_START/ARGS/END`,
`TOOL_CALL_RESULT`, `TEXT_MESSAGE_*`, `STATE_SNAPSHOT/DELTA` (budget, artifacts), `RUN_ERROR` and
`RUN_FINISHED` (with `outcome.type == "interrupt"` for approvals, `emit_interrupt_outcome=True`). Resume
uses `RunAgentInput.resume[]`. The audit JSONL stays the record of truth. The UI is a viewer and never
writes evidence.
