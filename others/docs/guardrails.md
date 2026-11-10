# Agent guardrails

The prompts tell the model the rules, and `prompts/guardrails.md` opens every role. A prompt is a
request, though, not a control, so each rule below is also enforced in code that the model cannot reach.
The list follows the OWASP Top 10 for LLM Applications (2025).

| Risk | What could go wrong here | Control | Test |
|---|---|---|---|
| LLM01 Prompt injection | A request or a name tells the model to mark a cell as passing | The model has no tools or authority; `FORBIDDEN_TEXT` refuses such requests with no model call; a function must match the request grammar; untrusted text sits inside `<facts>` and `<request>` | `test_agent_graph.py`: `test_a_rule_refuses_forbidden_requests_before_any_model`, `test_only_a_real_expression_skips_the_model` |
| LLM02 Sensitive information | A secret reaches a prompt or a log | Prompts carry only numbers and names from check reports; Codex CLI keeps its own login; the CLI starts in an empty directory with no user config | `test_codex_cli.py` |
| LLM03 Supply chain | A dependency changes behaviour | Versions pinned; OpenSTA pinned by commit; OpenUI's self-loading devtools are stubbed out | `make check` |
| LLM05 Improper output handling | Model text becomes HTML or a command | Every reply is parsed into `Decision` or `Intent`; pages pass `check_page`; only library components render; no tool takes a string to run | `test_a_bad_page_is_refused`, `test_every_forbidden_action_is_refused` |
| LLM06 Excessive agency | The model edits a check or the PDK | A closed list of actions; the CLI runs with the shell off and read-only, and any tool use is refused; `policy.may_write` limits writes to the run; a digest of the protected files is compared around each call | `test_tool_use_is_refused`, `test_agent.py` |
| LLM07 System prompt leakage | The prompt is drawn out | The prompts hold no secret, and the model is told not to repeat them | `prompts/guardrails.md` |
| LLM09 Misinformation | The model states a number or a failure that is not real | Numbers in its words must be in the facts; evidence ids must exist; nets must exist; panels fetch their own numbers; the verdict comes from the report | `test_claims_the_facts_do_not_support_are_refused`, `test_a_fail_verdict_cannot_become_a_pass` |
| LLM10 Unbounded consumption | A run spends without limit | Limits on model calls, tool calls, time, tokens and cost; a closed tab stops the run, its containers and the model call | `test_the_cost_limit_stops_a_run`, `test_cancel_stops_the_tool_and_its_containers` |

LLM04 (data poisoning) and LLM08 (vector weaknesses) do not apply: nothing here trains a model or uses embeddings.

The Notes a model writes are its own words. They can be wrong without containing a wrong number: a verification
run found a reason that named a route failure that never happened. So the UI marks a Note as the agent's and
not a check result, and no decision reads it.
