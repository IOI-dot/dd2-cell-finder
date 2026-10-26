# Phase 0 Research: DD2 Cell Finder

**Date**: 2026-10-26 · **Plan**: [plan.md](plan.md) · **Spec**: [spec.md](spec.md)

Every decision below is backed by a command that was run on this machine on 2026-10-26, or by a
quoted handout rule. Spike scripts and their raw output are in [`research/`](research/). They are
**research evidence only**. They are not report results: report numbers must come from
`results/` files that the real flow writes.

## Environment facts found

| Fact | Evidence | Consequence |
|---|---|---|
| The data volume has **376 MB free** (97–100% used). The earlier container build failed with 109 MB free. | `df -h /System/Volumes/Data` | **Blocker R-0.** The course container (Magic/Netgen/ngspice), Docker images and a full PDK cannot be built or installed. M1 itself fits in less than 200 MB. |
| `/usr/bin/python3` is **3.9.6**. Homebrew Python **3.14.6** and `uv` are installed. | `python3 --version`, `uv python list` | The course requires Python ≥ 3.11 (overview Table 1). Every command runs through `uv run` with `requires-python >=3.11`. Never use bare `python3`. |
| Host Yosys is **0.70+post**, Icarus 13.0. ABC is bundled as `yosys-abc`. | `yosys -V`, `iverilog -V` | 0.70 is newer than the handout's Table 1 baseline (Yosys 0.33). See D-2. |
| **OpenSTA (`sta`) is missing.** | `command -v sta` | Required from M2 onward (worst delay in Table 5). `make check` reports it explicitly. |
| `PDK_ROOT` is unset. `~/.ciel/sky130A` is a symlink to a ciel version `dd7771c…`. | `readlink ~/.ciel/sky130A` | `PDK_ROOT=~/.ciel`, and the PDK is at `$PDK_ROOT/sky130A`. The root `AGENTS.md` wrongly called `~/.ciel/sky130A` the `PDK_ROOT`; it is fixed. |
| The installed `sky130_fd_sc_hd` has only `lib/`, `techlef/` and `verilog/`. There is **no `spice/`, `gds/`, `lef/` or `cdl/`**. | `ls libs.ref/sky130_fd_sc_hd` | Enough for M1, which needs Liberty only. **Blocker R-1 for M2 and Option 1**: the area model needs HD transistor counts (SPICE), and Option 1 needs GDS, LEF and SPICE. Reinstall the full HD views once disk is freed. |
| The full HD Liberty `sky130_fd_sc_hd__tt_025C_1v80.lib` has 428 cells. 323 of them are single-output, combinational and not tri-state. | `research/table4_spike_output.txt` | This is the redundancy corpus (Option 2 §5). |
| `given/hd_reduced.lib` has 189 cell groups and `hd_usable.lib` has 307. | `grep -c 'cell ('` | These match the handout. |
| **Commit `e55f766` committed `DD2_Project1_student_pack/`, including `given/`, and it was pushed to `origin/main`.** | `git show --stat e55f766`, `git log origin/main` | **Rule violation R-2**: "Never commit … given files." See D-12. |

## Decisions

### D-1 Python runtime and packaging
- **Decision**: one `pyproject.toml` managed with `uv`, with `requires-python = ">=3.11"`. The M1 core
  (`src/dd2`) uses only the standard library. Tests use `pytest`. The agent and web dependencies
  are optional extras, so `make test` for the course needs no AI or web packages.
- **Rationale**: the course requires ≥ 3.11, and the host default is 3.9. A stdlib-only core keeps
  disk use small and lets a clean checkout run offline (Constitution II).
- **Alternatives**: system Python 3.9 (fails the course minimum); conda (too much disk).

### D-2 Yosys version for Table 1 reproduction (**open; verification task T004**)
- **Measured**: the supplied `map.sh` on host Yosys 0.70 ([research/table1_yosys070_spike.txt](research/table1_yosys070_spike.txt)):

  | Design | A reduced (handout 0.33 → 0.70) | Δ | B reduced (0.33 → 0.70) | Δ | Reduced vs usable, A, on 0.70 |
  |---|---|---|---|---|---|
  | cpu8 | 4186.5 → 4195.3 | +0.2% | 4359.2 → 4321.6 | −0.9% | +0.6% |
  | dsp8 | 5928.2 → 5794.3 | −2.3% | 6214.7 → 6102.1 | −1.8% | +0.4% |
  | arlet6502 | 9701.8 → 9320.2 | −3.9% | 9995.8 → 9546.7 | −4.5% | +0.4% |
  | uart_apb | 12948.7 → 12817.3 | −1.0% | 13180.1 → 13030.0 | −1.1% | +1.4% |
  | risc8 | 28263.4 → 28187.0 | −0.3% | 27511.4 → 28109.5 | +2.2% | +1.5% |
  | fir10 | 25968.7 → 26322.7 | +1.4% | 29055.4 → 28935.3 | −0.4% | **+3.0%** |

  On 0.70 the reduced library costs up to 3.0% over the usable one. The handout states that it costs
  at most 0.5%. So the version changes the conclusion of Table 1, not only its digits.
- **Decision**: the canonical baseline runs on **Yosys 0.33**, pinned as
  `yowasp-yosys==0.33.0.0.post574`. That is a 6.9 MB pure-Python/WASM wheel on PyPI, so it is
  small enough for the current disk. It sits behind a `YOSYS` Make variable. Host 0.70 stays
  available as a second recorded run, `make m1-baseline YOSYS=yosys`, so the report can explain the
  version effect from saved files.
- **Status 2026-10-26 (M1 delivered on 0.70)**: `results/m1/table1.csv` is measured with host Yosys 0.70 and
  shows the handout values beside it. T004 is still open.
- **Unverified**: the install was blocked in this session by a permission rule, so it has **not** been
  shown that YoWASP 0.33 reproduces Table 1 exactly. Task T004 runs it on cpu8 first. If cpu8/A/reduced
  ≠ 4186.5 µm², fall back to building tag `yosys-0.33` in `docker/flow.Dockerfile` (this needs disk; see
  R-0).
- **Also verify in T004**: whether the YoWASP wheel exposes a standalone ABC entry point. If it does
  not, the restructured AIG (D-4) uses ABC through Yosys's `abc` pass, or host `yosys-abc`, and the
  ABC build is recorded in the manifest.
- **Alternatives**: accept 0.70 and explain the differences (it does not reproduce the 0.5% claim);
  OSS CAD Suite 2023 tarball (about 1 GB, does not fit).

### D-3 Parse `stat` with `-json`, not with `map.sh`'s grep
- **Finding**: under 0.70, `map.sh`'s `grep "Number of cells"` printed nothing, because the stat text
  format changed. Only `Chip area` matched.
- **Decision**: the flow runs the identical command sequence of handout §2 but appends
  `tee -o <run>/stat.json stat -json -liberty <lib>`, and parses JSON for area and cell counts. The raw
  text log is kept too. `given/scripts/map.sh` is never edited; a test checks that our command string
  equals its command string (the scripts and step order) for both A and B.

### D-4 AIG extraction and the restructured variant
- **Verified on cpu8 (0.70)**: `write_aiger` fails after a plain `synth -flatten` with
  `Unsupported cell type: $_SDFFE_PP0P_`. With `async2sync; dffunmap; aigmap` it succeeds.
- **Decision (synth variant)**: `read_verilog [-sv] <v>; synth -flatten -top <top>; async2sync; dffunmap; aigmap; write_aiger <out>.aig`.
  **Measured (T013, 2026-10-26)**: plain `write_aiger` gives latches = flip-flops after `synth` on all six
  designs (82, 72, 143, 330, 696, 176), the same as the handout's flip-flop column. `-zinit` adds one input
  and initialisation logic per flip-flop, plus one extra latch. So the flow uses plain `write_aiger` and
  records the `-zinit` AND count in `results/m1/aigs/compare.csv`. The `-zinit` AND counts (1178 … 8745) sit
  much closer to the handout's AND column (1265 … 8795) than the plain ones (932 … 8217), which suggests the
  handout counted with `-zinit` on Yosys 0.33. This is reported, not hidden.
- **Finding**: `strash; dch` leaves **323 choice nodes** in the AIG (cpu8: 2131 ANDs "with choices"),
  which inflates the AND count and adds equivalence structure that cut enumeration must not see.
- **Decision (restructured variant)**: `read <synth>.aig; strash; dch -f; strash; write_aiger <out>.aig`.
  The final `strash` gives a choice-free graph (cpu8: 1130 → 1103 ANDs). `dch -f` matches script A.
  The command goes in the manifest.
- **Alternatives**: `strash; dc2` (1105 ANDs; also valid, but not the handout's example);
  `&get -n; &dch -f; &put; strash` (identical result, 1103).

### D-5 Cut enumeration and the independent check
- **Decision**: the textbook bottom-up k-feasible cut enumeration (references 10 and 11) with k = 4. A
  node's cuts are the trivial cut plus the merges of its two fanins' cut sets with |leaves| ≤ 4, with
  dominated cuts removed. Combinational inputs (PIs and latch outputs) are leaves only. The truth table
  is computed **bit-parallel** while merging (16-bit masks, input 0 = LSB, Appendix A order).
- **The independent check** is a separate code path: for each saved cut it walks the cone from root to
  leaves and **simulates it one input assignment at a time**, over all 2^k assignments, then compares
  the result with the stored table. It shares no truth-table code with the enumerator.
- **Volume**: full 4-cut sets reach about 10^5–10^6 cuts on the larger designs. Full cut lists are
  written gzipped to `build/` (git-ignored). `results/m1/cuts/` commits per-variant counts, class
  histograms, the validation summary (cuts checked / failed) and a deterministic 1% sample. This keeps
  the repository under the 50 MB rule.
- **Broken case**: `tests/broken/wrong_truth_table.json` is a real cut with one flipped bit, and the
  check must reject it (Option 2 §9.1).

### D-6 Boolean canonical forms
- **Decision**: truth tables are Python ints with input k = bit k of the index (Appendix A). There are
  three canonical forms, each the minimum integer over its group:
  - **P** (input permutation): used by Table 4 ("up to input order") and by `Exists`.
  - **PN** (permutation + output inversion): the handout's "classes" (§4 step 3), and the count that
    matters for CMOS.
  - **NPN** (also input inversions): counted separately, as the handout requires.
  
  With n ≤ 4 there are 24 permutations, so exhaustive canonicalization is cheap. A 65,536-entry
  lookup table is built once per run.

### D-7 Redundancy classes: exact definitions (**verified against Table 4**)
The spike [`research/table4_spike.py`](research/table4_spike.py) reproduces Table 4 on the full HD
Liberty. These definitions are therefore the contract, checked in this order (first match wins):

1. **Exists**: the P-class of the candidate equals the P-class of an HD cell with the same number of
   essential inputs.
2. **Exists with an inverter**: inverting the output, **or** exactly one input, gives an `Exists`
   function.
3. **Contained**: the candidate's table equals some HD cell (any arity, up to 6 inputs) with **each HD
   input tied to one candidate input or to 0/1**. Several HD inputs may share a candidate input.
4. **New**: none of the above.

Results over all P-classes that depend on all 4 inputs (3,904 classes):

| Table 4 row | Handout | Spike | Status |
|---|---|---|---|
| Exists | 24 | 24 | ✅ |
| Exists with an inverter | 20 | 20 | ✅ |
| Contained | 38 | 38 | ✅ |
| New | 3,822 | 3,822 | ✅ |
| New, one static CMOS stage (Y negative unate) | 9 | 9 | ✅ |
| New, one stage, ≤3 in series, ≤12 transistors | **5** | **6** | ⚠️ **open (Q-1)** |
| One stage, every input once (and ≤3 series) | 8 = 6 Exist + 2 Contained | 8 = 6 + 2 | ✅ |
| Every HD cell fed back → Exists | all | 323/323 | ✅ |

- **One-stage costing model** (used for rows 5–7 and reused in M2): a single stage realises Y = !F with F
  positive unate, built as a series-parallel formula over positive literals (literals may repeat).
  Transistors = 2 × literals. NMOS series depth: AND adds, OR takes the max. PMOS (the dual): AND takes
  the max, OR adds. A DP over formulas of up to 8 literals keeps the (literals, n-series, p-series)
  points for every function.
- **Q-1 (open)**: with "some formula has ≤6 literals and ≤3 series in both networks", six classes
  qualify: Y = `0x0017, 0x011F, 0x013F, 0x037F, 0x077F, 0x17FF` (the handout's own example
  `0x077F` is among them). The handout says 5. Its unstated rule may fix one factored form per
  function, for example the first minimum-literal form found, instead of searching all of them. Four of
  the six have a minimum-literal form with 4 in series as well as one with 3. **Action**: ask the TA in
  the cp1 meeting. **Dual-pair argument (verified 2026-10-26):** the six form three dual pairs,
  Y^d(x) = !Y(!x): 0x0017↔0x17FF, 0x011F↔0x077F, 0x013F↔0x037F. Taking the dual swaps the NMOS and
  PMOS series depths and keeps the literal count ((6,2,3)↔(6,3,2)). So any definition that treats the
  two networks alike gives an even count, never 5. An independent review found that 5 comes only from
  testing the first minimum-literal form an enumerator happens to find, which depends on the
  enumeration order. Until the TA answers, the self-test asserts rows 1–5 and 7 exactly, records row 6 as
  `measured: 6, handout: 5, status: definition-open` with the six witnesses, and the report says so.
  The count is not tuned to match.

### D-8 Liberty reading
- **Decision**: a small brace-matching reader. It takes `cell` → `pin` groups and keeps a cell when it
  has exactly one output pin with a `function`, at least one input, no `ff`/`latch`/`statetable`, and
  no `three_state`. Only the pin-level `function` attribute is used: the full HD lib also contains
  `power_down_function : "(!VPWR + VGND)"`, which must be ignored. Functions are parsed with a
  recursive-descent parser over `! ' & * | + ^ ( ) 0 1` (precedence ! > & > ^ > |). Any unknown token
  raises an error and is never skipped (FR-010, broken case `tests/broken/invalid_function.lib`).
- **Alternative**: the `liberty-parser` PyPI package (extra dependency, slow on the 10 MB `hd_usable.lib`).

### D-9 What "class table of HD" contains
One row per single-output combinational HD cell: name, inputs, arity, hex truth table, P, PN and NPN
canonical forms, whether it is in the reduced library, and its area. A second table groups by PN-class:
class → member cells, smallest area, and whether the reduced library has a member. The output is
`results/m1/hd_classes.{json,csv}`.

### D-10 Agentic stack (planned for US4/M2, after M1)
- **Decision**: **LangGraph** (`langgraph>=1.0,<2`) for the orchestrator graph. **LangChain**
  (`langchain>=1.2`) `create_agent` plus middleware (HumanInTheLoop, a custom budget and audit
  middleware) for the tool-calling sub-agent. **AG-UI** via `ag-ui-langgraph` (0.0.47, MIT,
  `requires-python >=3.10,<3.15`) with `add_langgraph_fastapi_endpoint` to stream events to the UI.
  Human approval uses LangGraph `interrupt()` with a checkpointer. In AG-UI this is
  `emit_interrupt_outcome=True` with `RunAgentInput.resume[]`. Sources are in
  `references/ag-ui/integrations/langgraph/python/README.md` and
  `references/langchain-skills/config/skills/{langgraph-fundamentals,langgraph-human-in-the-loop,langgraph-persistence,langchain-middleware}`.
- **Course constraints that override framework defaults** (overview §4.2, Appendix B, Constitution IV):
  - It runs from one command, `make agent IN=<design>`, headless. The UI is optional.
  - Every model and tool call writes one JSONL line in Appendix B format to `ai/runs/<run>.jsonl`.
  - Tools are typed Pydantic schemas that wrap the deterministic `dd2` CLI steps. Path authorisation
    is enforced in tool code, and protected paths are mounted read-only in Docker.
  - Limits on iterations, wall time, tokens, cost and input size are enforced in a middleware, not in
    the prompt.
  - Prompts are versioned files `prompts/*.md`, referenced as `path@git-short-hash`.
  - A **fixed-choice pipeline** (`make fixed IN=…`) makes the same decisions with deterministic rules,
    for the required comparison.
  - The agent never decides pass or fail. It reads check outputs.
- **Model provider**: the instructor announces the allowed providers and the budget (overview §4.2).
  The setting goes through `init_chat_model("<provider:model>")` from `config/agent.toml`, and the
  provider stays open until the instructor confirms it (Q-2).
- **What the agent decides** (so it adds something over the fixed pipeline, which is the only part
  that is graded): which candidates to send to Option 1 next, how to react to a failed cell response
  (retry with `stack` sizing or drop it), and when the greedy selection should stop early under the
  budget.
- **Alternatives**: a hand-written tool loop (the pattern in Backend.md). It is simpler, but the user
  asked for LangGraph, and LangGraph supplies interrupts and checkpointing. Deep Agents was rejected
  as too much autonomy for a graded, auditable flow.

### D-11 Frontend (planned for US4, after M1)
- **Decision**: `web/` is a Vite + React 19 + TypeScript app built from the
  **`DesignSystemStudio/`** primitives (shadcn/Radix translation: sidebar, card, table, chart,
  badge, sonner, dialog, `message`/`message-scroller` for the run transcript) and themed with the
  **Graphite Cyan** tokens in `DesignSystemStudio/GraphiteCyan/catalyst-design-system-v2-graphite-cyan.css`
  (dark-first graphite surfaces, cyan/electric-blue accents, coral reserved for destructive or alert
  states). The AG-UI client is `@ag-ui/client` `HttpAgent`, pointed at the FastAPI endpoint.
  Components are copied into `web/src/components/ui/` as needed, not imported across folders
  (Backend.md: "no 2 folders communicate in code").
- **Screens**: Runs list · Run detail (lifecycle timeline, tool-call cards with argument and result
  links, budget meters, approval dialog for interrupts) · Evidence browser (Table 1, Table 5, the HD
  class table, cut summaries, read from `results/` through a read-only API) · Fixed-vs-agent
  comparison.
  Verified evidence and AI text are styled differently, with labels and not only colour (FR-015,
  SC-008).
- **Constraint**: `DesignSystemStudio/node_modules` (593 MB) is ignored and is not reused. The web
  app has its own lockfile, installed only when disk allows.

### D-12 Repository hygiene fixes for findings from the earlier session
- **R-2, student pack committed**: in the plan, `git rm -r --cached DD2_Project1_student_pack`, move
  the pack **outside** the repository (for example `../DD2_Project1_student_pack`, which the template
  `GIVEN` default expects), and add it to `.gitignore`. Removing it from history needs a force-push to
  the shared group repository. **That is the group's decision**, so ask first. It must be settled
  before `cp1` is tagged, because a tag that contains the given files is permanent evidence.
- `references/` (105 MB, third-party clones with their own `.git`) and the three handout PDFs must
  also be git-ignored. Neither is the group's work, and the PDFs are course material.

### D-13 Docker
- `docker/flow.Dockerfile`: python:3.12-slim + uv + the pinned YoWASP Yosys 0.33 + Icarus + OpenSTA
  (built from source, multi-stage). It runs `make check test m1` with `given/` and the PDK mounted
  **read-only**.
- `docker/agent.Dockerfile`: the flow image plus `[agent]` extras. FastAPI and AG-UI on port 8000.
  Secrets come from the environment at run time, never baked in (Backend.md).
- `docker/web.Dockerfile`: a Node 22 build, then static files served by nginx.
- `docker/compose.yml`: agent + web. `tests/broken/`, `given/` and the PDK are mounted `:ro`, which is
  the enforcement that overview §4.3 rule 4 requires.
- The course `dd2-layout-tools` image is built from the student pack's `container/` as supplied,
  never copied or edited.
- **All builds wait for R-0.** The Dockerfiles can be written and statically checked (`docker build
  --check`) now, but not built.

### D-14 Option 3 checkpoint scope (**risk**)
For a five-student group, cp1 is graded on **both** options' rows: Option 1 must also show `inv_1` and
`nand2_1` regenerated at 2.72 µm and passing every check next to HD cells (overview §3). The user scoped
this session to Option 2 M1, so the Option 1 cp1 work is **not** planned in detail here. Because of
R-0 and R-1 it also cannot start on this machine. The Option 1 owners must be told today.

### D-15 Checkpoint 1 rows that the plan initially missed (found in overview Figure 2)
The schedule figure lists week-1 rows that the text of the Option 2 handout does not:
**Agentic system** (if chosen): "Tools wrapped · Checks read-only · Runs logged", and **Option 3**:
"Request format fixed (Appendix A)". Both were added to M1. The first is `agent/dd2_agent/`
(typed tools over the dd2 CLI, a deterministic policy, a protected-file digest checked around every
call, and Appendix B JSONL logs; `make agent-check`). The second is `docs/interface/*.schema.json`
plus `src/dd2/interface.py`.

### D-16 Handout integrity check (prompt injection)
All three PDFs were checked on 2026-10-26:
- metadata: Word → macOS Quartz, no JavaScript, forms or attachments;
- every text run with its font colour, size and position: no white, near-white, tiny or off-page text;
- grep for instructions aimed at AI tools: only the course's own AI-use rules;
- the three embedded figures, viewed: only the diagrams.

Nothing hidden or suspicious was found.

### D-17 Course lectures 9–10 (SCL and synthesis): what they change in the plan
- **Library views.** A cell is shipped as Verilog, SPICE/CDL, Liberty, LEF and GDS. Our PDK has
  only Liberty, Verilog and techlef for HD (R-1). Option 1 needs SPICE, GDS and LEF, and the M2
  area model needs SPICE transistor counts.
- **NLDM.** Delay and output slew are tables of input slew and output load. Input capacitance comes
  from the Liberty. M2's placeholder timing (logical effort, Option 2 §6) stays a placeholder.
  Option 1 must index by the 20–80% slew, the lecture's "input transition".
- **Technology mapping.** The flow is RTL to generic logic, then an AIG (NAND2/INV), then
  minimum-cost covering, with cell area as the cost. That is exactly why a new cell only helps if
  ABC can cover AIG cuts with it. It also explains why the AIG's structure limits which cuts exist
  (reference 12), and why script A (structural amap) never uses cells with repeated inputs while
  script B (&nf, cut functions) does.
- **Constraints.** The clock constrains reg-to-reg paths. Boundary paths need input/output delay,
  output load and input transition. For M2's OpenSTA worst delay, use one SDC template per design
  (clock period, `set_input_delay`, `set_output_delay`, `set_load`, `set_input_transition`), the
  same for the baseline and the extended library, so delay changes come only from the new cells.

## Open questions

| ID | Question | Who answers | Blocks |
|---|---|---|---|
| Q-1 | Table 4 row 6: what definition gives 5 rather than 6? | TA at cp1 | Nothing (the result is recorded honestly) |
| Q-2 | Which AI providers and what budget are allowed? | Instructor | US4 runs (not M1) |
| Q-3 | The group number for the `dd2_g<N>__` prefix | Group | M2 requests |
| Q-4 | Rewrite history to remove the committed student pack? | Group | Tagging cp1 |
| Q-5 | Who frees disk (target ≥ 15 GB) and reinstalls the full HD views? | Machine owner | M2, Option 1, Docker |
