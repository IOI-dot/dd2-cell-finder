# Architecture and repository layout

Status: 2026-10-26. The course core (Option 2 M1) is implemented. The platform around it (backend,
agent front end, data stores) is **planned**, and its system design is to be agreed with the user
(see "Open design questions").

## Layers and the one dependency rule

```text
web/  (agentic front end: AG-UI client, DesignSystemStudio + Graphite Cyan)
  │  HTTP / AG-UI event stream
backend/  (API: auth, RBAC, rate limits, runs, artifacts, audit; Postgres + vector DB)
  │  starts and observes agent runs
agent/dd2_agent/  (LangGraph agent; typed tools, policy guard, Appendix B run logs)
  │  dd2 CLI + JSON files only
src/dd2/  (deterministic course core: Yosys/ABC flow, cuts, classes, redundancy, checks)
```

Each layer may depend only on the layer below it, and only through that layer's public contract
(CLI and JSON for `dd2`, typed tools for the agent, HTTP for the backend). `src/dd2` imports
nothing from the others and uses only the standard library. A clean checkout must keep running
`make setup check test all` offline for the TA, with no backend, browser or AI service. This
follows Backend.md's lib/app split and "modules talk through controlled entry points".

## Repository map

| Path | What | State |
|---|---|---|
| `README.md`, `AGENTS.md`, `Makefile`, `pyproject.toml`, `index.yml` | Course-required root files; machine index | in use |
| `src/dd2/` | Deterministic core | M1 done |
| `agent/dd2_agent/` | Tools, policy, audit, scripted self-check; LangGraph graph later | cp1 rows done |
| `prompts/` | Versioned agent prompts (`path@git-hash` in logs) | empty until a model is used |
| `backend/` | Future API service | placeholder |
| `web/` | Future agentic UI | placeholder |
| `docker/` | Images and compose; protected inputs mounted read-only | placeholder |
| `tests/`, `tests/broken/`, `tests/broken_proposed/`, `tests/fixtures/` | Tests; frozen broken cases; cases awaiting human review; tiny AIGs | in use |
| `results/`, `runs/`, `ai/`, `ai/runs/` | Committed evidence; agent run outputs; AI logs; run logs | in use |
| `cells/`, `libs/`, `report/` | Option 1 cells, Option 2 Liberty files, reports | later |
| `docs/interface/` | Appendix A examples and JSON Schemas (frozen) | in use |
| `specs/001-agentic-cell-finder/` | Spec Kit spec, plan, research, contracts, tasks, verification | in use |
| `DesignSystemStudio/` (untracked) | The visual source: shadcn/Radix primitives, blocks, Graphite Cyan tokens | reference; ask before moving or committing |
| `Backend.md` (untracked) | Backend practice notes that drive the backend design | reference; ask before moving or committing |
| `references/` (ignored) | Upstream clones: ag-ui, langchain-skills | read-only |

## Open design questions (decide together before building the backend)
1. **Users and tenancy.** Who uses the platform: the group only, the course, or the public? This sets
   the auth method (httpOnly session cookies or access/refresh tokens, per Backend.md) and the RBAC
   roles (viewer, runner, admin?).
2. **Backend language and framework.** Backend.md describes TypeScript, Express/Knex, DI and DTOs.
   The core and the agent are Python, so the choice is between a TS API that calls a Python agent
   service and an all-Python API (FastAPI).
3. **Postgres.** What it holds: runs, run events (audit), artifacts metadata, users, rate-limit
   counters? Do we need migrations from day one, and cursor pagination?
4. **Vector database.** What is embedded: handouts, lecture notes, tool docs, past runs? pgvector
   inside Postgres or Pinecone? Chunk size (Backend.md: 300–800 tokens), and RBAC filtering of
   retrieved context in code.
5. **Long-running flows.** A job queue and worker (with an outbox and idempotency keys) versus
   in-process runs; how cancellation and approvals (LangGraph interrupts) map to API calls.
6. **Streaming.** AG-UI over SSE from the backend, or a websocket.
7. **Limits and safety.** Global, per-user and per-IP rate limits (Redis?); per-run token, cost and
   time budgets; prompt-injection handling for retrieved text; secrets management.
8. **Artifacts.** Local disk, or object storage plus a CDN for GDS/Liberty/results.
9. **Deployment.** Local docker compose only, or a cloud target (Backend.md mentions ECS/RDS).

## Option 1 agent

`make agent FUNC='...'` runs one headless graph (`agent/dd2_agent/graph.py`), with nobody intervening; the
web app runs the same graph. There is one graph with three model roles (implementation plan 8.2). `make fixed` is
the same tool and the same checks with no model.

```
 message or function
        |
   intent_parser ---- rule: forbidden requests refused, expressions parsed, no model
        |             model: Request Interpreter -> typed Intent (build, try, compare, explain, show, restore, unclear)
        v
 invoke_allowed_tool <----------------------+   tool: build_cell -> cellgen build -> report.json
        |                                   |   Magic, Netgen, ngspice, Icarus, KLayout, all in runs/<run>/
   assess_retry ---- rule: clean cell stops, no model; a limit stops
        |                                   |
   fetch_context                            |
        |                                   |
 plan_one_bounded_action ---- model: Engineering Diagnostician -> typed Decision, closed list
        |                                   |
   validate_action ---- rule: schema, evidence ids, numbers, nets; one retry with the reason
        +-----------------------------------+
        |
      finish ---- rule: verdict read from the best revision's check report -> ai/runs/<run>.checks.json
        |
 explain_evidence ---- model: Research Explainer -> page in OpenUI Lang, checked, or the fixed page
        |
     ai/runs/<run>.jsonl (one line per model or tool call; the last line is the verdict)
```

| Part | May read | May change |
|---|---|---|
| `build_cell` | PDK and `given/` | `runs/<run>/` only, checked by `policy.may_write` before each call |
| Each model role | The numbers and names in its facts block | Nothing: it returns JSON or a page, and a program checks both |
| `finish` | The check reports | `ai/runs/<run>.*` |

The model is GPT-5.6 Sol through Codex CLI, with `agent/dd2_agent/codex_cli.py` turning the CLI into a normal
chat API: `CodexCLI.complete` returns OpenAI-style JSON, `ChatCodexCLI` is a LangChain chat model, and the
server exposes `POST /v1/chat/completions`. The rules are in [guardrails.md](guardrails.md), and the limits in
`config/agent.toml`. Fixed choices (`agent/dd2_agent/fixed_choice.py`): the first ordering, hd sizing, default
routing, one build. The default search in `make o1-m2` is stronger than that baseline, and
`results/option1/m2/test_cells.csv` shows what it reaches with no model.

## From the agent to the screen

The transport is AG-UI, and the page language is OpenUI Lang. [web/README.md](../web/README.md) has the steps.
