# GB4 - Finding Cells Worth Adding

## 1. Group

CSCE 3304 Digital Design II, Project 1, **Option 2**. Team GB4 includes
Omar Abdel Motalb (900232118), Noor Elshahidi (900230000), and
Mohamed Azouz (900225230). AI was a development aid under overview §4.1.
The submitted flow runs without a model or API key.

## 2. Quick start

Use Ubuntu or WSL, Python 3.11+, OpenSTA 3.1.0 on PATH, and the external
course and tutorial inputs. Use Linux Yosys 0.33 with its ABC to reproduce
Table 1. Use the pinned OSS CAD Suite for M2/M3, which recorded Yosys
0.70+240 and Icarus Verilog 14.0 in the WSL run.

```bash
git clone https://github.com/IOI-dot/dd2-cell-finder.git
cd dd2-cell-finder
export PATH="$HOME/.local/bin:$PATH"
make setup GIVEN=/absolute/path/to/student_pack/given \
  PDK_ROOT=/absolute/path/to/pdk_parent TUTORIALS=/absolute/path/to/tutorials
make check
make test
```

The TA runs `make check` and `make test` from a clean checkout after setup.
Allow a few minutes for setup and dependency installation. The toolchain
check is quick, and the saved WSL test run took about a minute.

`PDK_ROOT` contains `sky130A/`. `TUTORIALS` contains the original
`spm/{SPM.v,CSADD.v,TCMP.v,SPM_tb.v}` and
`multiplier/{mul.v,mul_exhaustive_tb.v}`. Setup creates symlinks to those inputs.
If the pinned suite is absent, run
`.venv/bin/python tools/install_course_tools.py` after setup. The installer
verifies the release checksum and writes an ignored local tools configuration.
The Makefile also recognizes the existing suite at
`~/dd2-tools/oss-2026-10-27/bin`. Set `REFERENCE_YOSYS` and `REFERENCE_ABC`
for M1 if its reference executables are outside `/usr/bin`.

`make reproduce` validates the published selection and the supplied
characterized cells, and reruns the real remaps, equivalence, timing,
tutorial simulations, area curve and sensitivity test in
`build/m3/reproduced-real/`. Published evidence stays under `results/`.
`make all` runs M1, M2, and a fresh best-of-all M3 search before the
real run. Allow hours for the full search. The published run evaluated
7,735 trial libraries. The real step requires generator responses that
match the reselected requests.

## 3. What the tool does

The tool extracts synthesized and ABC-restructured AIGs, checks small cut
truth tables, and classifies functions against the full SKY130 HD library.
It fits an area model to HD cells, ranks candidate functions, writes Appendix A
requests and estimated Liberty, and measures the effects of extending the
reduced library. The best-of-all sweep selects up to ten cells by the sum of
best-of-A/B areas over the six required benchmarks. M3 replaces estimated cells
with characterized Liberty for the same requests and verifies the baseline,
mapped designs, and timing. SPM, multiplier, pic16, and p16c5x are shown
separately from that aggregate.

## 4. Commands

| Command | Purpose and output |
|---|---|
| `make setup`, `make check`, `make test` | Link inputs, check the environment, and run Option 2 tests with the frozen fixture hashes. |
| `make m1` | Reproduce the reference mapping, AIG/cut, class, and redundancy evidence under `results/m1/`. |
| `make m2` | Fit, rank and evaluate the first estimated library in `results/m2/`. |
| `make ta`, `make readiness` | Regenerate the M2 review folder or print its checkpoint record. |
| `make m3-estimated-best` | Run or resume the best-of-all greedy search under `build/m3/reselected/`. Override `SWEEP_OUT` for a different output directory. |
| `make m3-real`, `make reproduce` | Reproduce the real experiment. Defaults to `ESTIMATED_DIR=results/m3/estimated-best` and `RESPONSES=libs/cellweaver`. |
| `make all` | Run the full Option 2 M1 through M3 workflow. |
| `make demo IN=/path/to/design.v` | Run the Option 2 flow for an unseen design. Use `TOP=module` when needed and `SV=1` for SystemVerilog. |
| `make demo-final IN=cpu8 OPEN=1` | Map one benchmark or Verilog file with the saved M3 library, then open its dashboard. Use `IN=all` for all ten M3 designs. |
| `make clean` | Remove generated work under `build/`. |

Individual workflow steps and development targets are listed in the Makefile. The independent
Liberty, truth-table and equivalence check implementations are in `src/`.

### Clean-checkout rehearsal

Run `make check`, `make test`, and `make reproduce` after setup in a fresh
checkout with the pinned tools. Compare the reproduced tables with the
published CSVs. To rehearse the unseen-design command using a supplied design,
run `make demo IN=given/designs/dsp8.v TOP=dsp8`. The demo saves its evidence
in `build/demo/` and also maps with the published real library when available.
For a live mapping comparison, run `make demo-final IN=dsp8 OPEN=1`. A new
test case can be a synthesizable Verilog or SystemVerilog file. The top module
is detected automatically, with `TOP=module` available to override it.
The demo uses the library and cell manifest in `results/m3/real/` and runs
four mappings per design. Each run prints the path to a browser dashboard
with area, worst arrival, equivalence, GB4 cell usage and matched AIG output
cones before and after ABC restructuring. It also plots area and timing changes
by script, and AND-node and cut counts before and after restructuring. The
full AIGs and CSVs are linked.
`make demo-final IN=all OPEN=1` runs all ten M3 designs, including the two
tutorials from the linked course inputs, and opens an index of the results.

## 5. Layout

| Path | Contents |
|---|---|
| [src/](src/README.md) | Option 2 core and M2/M3 workflows. |
| `tests/`, `docs/interface/`, `cells/` | Option 2 checks, Appendix A contracts and the archived importer fixture. |
| `results/`, `TA_M2/` | M1 through M3 measurements, netlists and verification evidence. |
| `libs/cellweaver/` | Ten Appendix A responses, characterized Liberty and verification files. |
| `report/`, `ai/` | Report PDFs and sources, plus AI use and mistakes logs. |
| [others/](others/README.md) | Historical Option 1, Option 3 and interactive agent/studio material. |

The WSL evidence can be imported again with
`python3 tools/import_m3_evidence.py /path/to/original/checkout`. The argument
may also be the extracted full evidence directory containing `results/m3/`.

## 6. Results

- **Reports** · [Technical report](report/report.pdf) and [AI report](report/ai_report.pdf).
- **M1** · [Reference table and cut summary](results/m1/summary.md).
- **M2** · [Area model, ranking, mapping, and Table 4 review](TA_M2/README.md).
- **M3** · [Evidence index](results/m3/README.md),
  [estimated Table 5](results/m3/estimated-best/table5_estimated.csv),
  [real Table 5](results/m3/real/table5_real.csv),
  [area curve](results/m3/real/cell_curve.png), and
  [sensitivity result](results/m3/real/sensitivity.json).

For the six required benchmarks, the estimated run saved **0.457%** area and
the real run saved **0.174%**. The characterized-library mappings used **zero**
new cell instances. The real saving reflects a change in how ABC mapped
existing HD gates. Source rows are in the estimated and real best-of-A/B CSVs.

## 7. Tests

`make test` checks cut truth tables, classification, contract validation,
the area model, greedy selection, Liberty import, A/B mapping, ABC equivalence,
and timing. The negative cases include a wrong truth table, an HD function
that must classify as Exists, invalid Liberty, and a nonequivalent AIG.
The two proposed mapping fixtures are exercised by the default suite.
The original frozen fixture files and their checksums are preserved.
The Git hygiene test allows the two required report PDFs,
`report/report.pdf` and `report/ai_report.pdf`, and rejects other tracked PDFs.
The published curves are PNG files.

## 8. AI use

See [AGENTS.md](AGENTS.md), [use log](ai/use_log.md),
[mistakes log](ai/mistakes_log.md), and [AI report](report/ai_report.pdf).
The AI report records the available model labels and the gaps in billing
and model metadata.

## 9. Limitations

The estimates are used for candidate selection. The generated physical
cells can be much larger, and the real run chose existing HD gates. OpenSTA
reports comparison delay under the flow's declared constraints. Tutorial
gate simulations use zero-delay functional models. The M2 Table 4 evidence
preserves the six measured witnesses and the reference value of five.

## 10. Third-party inputs

The course student pack and tutorial files are used from external paths.
The SKY130 PDK, Yosys/ABC, OpenSTA, Icarus Verilog, and OSS CAD Suite keep
their upstream licenses. The CellWeaver response artifacts record the
generator version and original reports. The pinned tool installer keeps
the tool binaries outside the repository.
