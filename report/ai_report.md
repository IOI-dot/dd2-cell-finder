# AI Use Report

**GB4 · CSCE 3304 Digital Design II · Option 2, Finding Cells Worth Adding**

November 2026 · Course overview §4.4

## Role of AI in the submission

The group used AI as a development aid under §4.1. We worked interactively with assistants to plan, draft code and commands, review logs, and write documentation. The submitted Option 2 command-line workflow performs cut discovery, ranking, mapping and checks using deterministic programs. It makes no model calls and requires no API key. The earlier Option 1 and 3 generator, agent and studio experiments are retained separately under `others/`.

## Work divided by milestone

**M1 · Discover functions and establish the reference.** Assistants helped translate the handout into a plan and implement the AIG, cut and Liberty utilities. The team supplied the course files, ran the checks, and reviewed discrepancies against the handout. The reference Table 1 run used the separate Linux Yosys 0.33 toolchain. The cut truth-table and redundancy checks, plus ABC equivalence results, were the evidence for accepting the outputs.

**M2 · Rank candidates with an area model.** Codex helped structure transistor and stage costing, fit the HD area model, rank mapped cuts, write cell requests and estimated Liberty, and prepare the A/B experiment. The team ran the WSL workflow on the supplied benchmarks and took the evidence to the TA. The group recorded the Table 4 disposition separately, preserving the six measured witnesses alongside the handout's count of five.

**M3 · Replace estimates with characterized cells.** Codex helped implement the greedy comparisons, prepare the CellWeaver retries, wrap the outputs as Appendix A responses, and diagnose remapping failures. The team ran the long sweep and characterization, recovered from a disk interruption, and supplied the completed remapping data. The mapping, verification and timing tools produced the evidence. AI summarized it and helped organize the repository and this report.

## Evidence used

The original AI records are `ai/use_log.md` and `ai/mistakes_log.md`. Technical evidence comes from `results/m1/`, `results/m2/` and `results/m3/`. The October records describe an earlier project scope. The M3 records describe the submitted Option 2 work.

\newpage

# Tools and verification

## Models, settings and cost

The early use log identifies Codex / GPT-5 and Claude Code / Claude Opus 5.5. These names reproduce the session labels written in the log. The later Option 2 work used interactive ChatGPT/Codex sessions. ChatGPT Plus cost **EGP 999.99 per month**, as shown by the October 16, 2026 payment in the account's billing history. The subscription covered general use. The portion attributable to DD2, any separate per-task charges, exact later model identifiers, model settings and token counts were not recorded. The submitted workflow incurs no model-call cost when executed.

Yosys and ABC synthesized, mapped and checked equivalence. OpenSTA measured delay, Icarus Verilog ran the tutorial simulations, and CellWeaver used the physical and SPICE toolchain to produce characterized Liberty. These tools supplied measurements and verdicts independently of the assistant.

## How we specified and checked tasks

We asked for work against a particular handout section, file, milestone or log. For M3, the task was to compare the same selected requests and benchmark inputs in the estimated and characterized runs. We gave the assistant the saved request IDs, paths, command output and version information. The assistant proposed changes, and the team ran them against the actual files. We judged a proposed fix by its tool output and by whether it preserved the experiment's inputs.

## Applying the course rules

**Independent verdicts and measurements.** The cut checker evaluates Boolean truth tables. ABC CEC checks equivalence. The Table 5 CSVs, OpenSTA logs and CellWeaver reports supply the numbers and verdicts. The real run compares each regenerated baseline with the saved area, input hashes and Yosys version before the comparison proceeds.

**Negative cases and protected files.** The suite exercises a wrong truth table, an installed HD function that must classify as Exists, malformed Liberty, and a nonequivalent AIG. We retain the frozen cases and checksum file. The older mistakes log records that the assistant authored frozen cases and restored PDK views during earlier work (M-016 and M-024). Those are historical process violations recorded by the team. Human review and checksum comparison are the controls for protecting those paths.

**Explainability.** Group members need to be able to trace one cut through its truth table, redundancy classification, area estimate, request and remap, then explain what each saved check establishes. The interactive assistant is a development aid throughout that process.

\newpage

# Five mistakes we caught

## 1 · The Liberty reader silently skipped a pin function

The first reader expected a `function` attribute at the start of a line. A one-line pin group could therefore be missed. The malformed Liberty fixture was unexpectedly accepted and exposed the gap. The parser accounting was corrected and the fixture retained. A weaker check using only conventional formatting in the full HD library would have missed this case.

**Evidence:** `ai/mistakes_log.md`, M-008, and `tests/broken/invalid_function.lib`.

## 2 · The AIG reader lost outputs after restructuring

The first reader skipped AIGER bad-state records that ABC used to represent outputs in the restructured artifacts. A verifier noticed that the output count had fallen to zero even though the other counts looked plausible. Comparing the effective outputs with the synthesized AIG and checking equivalence addressed the issue. A test limited to AND and latch counts would have passed.

**Evidence:** `ai/mistakes_log.md`, M-012, and the M1 AIG/CEC artifacts in `results/m1/aigs/`.

## 3 · The detached restart could not import CellWeaver

The first restart command ran a saved script in a nested build directory without adding the CellWeaver source root to Python's import path. Docker returned a container ID, then the script exited with `ModuleNotFoundError`. The team checked the retry log and added `PYTHONPATH` to the launch. The resumed run reached the same cell and reused saved work. A check that stopped at a container ID would have treated the launch as successful.

**Evidence:** November 10 WSL troubleshooting, summarized in `ai/mistakes_log.md`. The generated cells used in the final run are recorded in `results/m3/real/generator_cells.json`.

\newpage

# Mistakes and result interpretation

## 4 · A quoted statistics path broke the baseline run

The generated Yosys script quoted the output filename passed to `tee -o`. On the system Yosys 0.33 used during troubleshooting, ABC completed, but the command could not create `stat.json`. Removing the quiet flag in a diagnostic run exposed the exact write error. The working filename form restored baseline execution. Checking only that ABC printed its mapping summary would have missed the missing output file.

**Evidence:** November 10 WSL mapping and debug logs, summarized in `ai/mistakes_log.md`; the successful remap is in `results/m3/real-run.log`.

## 5 · The first real remap picked a different Yosys build

After the WSL restart, the assistant's command resolved system Yosys 0.33. That build mapped the designs successfully and passed equivalence, but the baseline areas differed from the estimated sweep, which used the pinned OSS CAD Suite. The baseline comparison stopped the run. The team explicitly selected the original Yosys and ABC and checked the input hashes. Equivalence alone would have accepted both baselines and hidden the invalid area comparison.

**Evidence:** `results/m3/estimated-best/baseline_mappings.json`, `results/m3/real/baseline_mappings.json`, and `results/m3/real-run.log`.

## A decision the team keeps

The team decides whether the characterized cells are worth adding. We compared the ten requests from the larger best-of-all greedy sweep (`estimated-best`) with the same ten cells in characterized CellWeaver Liberty, using matched baselines. The earlier first-improvement sweep was exploratory.

Best-of-A/B area savings over the six required benchmarks fell from **0.457% estimated** to **0.174% with characterized Liberty**. All ten measured cell areas exceeded their estimates. Across all 20 mapping rows, new-cell instances fell from **214 to zero**. The real saving came from ABC remapping existing HD gates. The team checked the netlists before attributing any saving to the new cells.

**Evidence.** `results/m3/estimated-best/` and `results/m3/real/` contain the Table 5 and best-of-A/B CSVs. The real run records cell areas in `generator_cells.json`.

\newpage

# What we would change next time

## Where AI saved time

It helped convert the handout into concrete steps, identify the relevant source and log files, and draft repeatable commands for the two mapping scripts. It also helped connect the CellWeaver output to the existing Appendix A importer and summarize the differences between the estimated and real results. Packaging was faster once the request IDs, response hashes, table names and required logs were listed explicitly.

## Where AI cost time

Several commands were tried before the execution environment was pinned. The detached launcher needed an import-path fix, the Yosys statistics step needed a diagnostic run, and the first real remap had to stop after finding a mismatched baseline. The WSL storage interruption also made preserving intermediate state important. These examples favor a short preflight that tests imports, verifies executable versions and checks free space before a long run.

## What we would delegate

We would use an assistant again for drafting orchestration, documenting file formats, suggesting diagnostic commands, and preparing summaries from saved records. We would ask for one reproducible test case and the expected evidence before adopting a change. For a long characterization job, we would require a dry launch with an explicit Python path and a small storage check first.

## What the team would own

The group would continue to choose the final candidate set, approve any change to verification fixtures, interpret performance tradeoffs, and approve the submitted commit. For reproducibility, we would record the complete tool selection and command before any run that produces report data. For the AI record itself, we would capture model labels, costs where available, and links to the saved evidence while working.

## Evidence index

- Course overview §§4.1, 4.3 and 4.4 and the Option 2 handout §§7 and 9.
- `AGENTS.md`, `ai/use_log.md` and `ai/mistakes_log.md` for scope and human review.
- `results/m1/`, `results/m2/` and `results/m3/` for measured outputs and verification.
- `results/m3/real/generator_cells.json` for characterized responses, request IDs and Liberty hashes.
