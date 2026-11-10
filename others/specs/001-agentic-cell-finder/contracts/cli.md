# Contract: Make targets and the `dd2` CLI

The exit code is the verdict: 0 = pass, 1 = check failed, 2 = usage or missing input. Every step that
writes evidence also writes a RunRecord ([data-model.md](../data-model.md)).

## Make targets (overview §5.1 requires the first six)

| Target | Inputs | Writes | M1? |
|---|---|---|---|
| `make setup` | `PDK_ROOT` (default `~/.ciel`), `GIVEN` (default `../DD2_Project1_student_pack/given`) | symlinks `pdk → $PDK_ROOT/sky130A` and `given → $GIVEN`; `uv sync`; `results/m1/setup.json` | ✅ |
| `make check` | links, tools | `results/m1/environment.json`. Fails if: Python < 3.11, Yosys missing or the wrong pinned version, `given/hd_reduced.lib` or `hd_usable.lib` or the full HD lib missing, Yosys `read_liberty -lib` does not print `Imported 189` / `Imported 307`. **Reports** OpenSTA and the `dd2-layout-tools` ngspice stress test as `missing (required from M2 / Option 1)`. | ✅ |
| `make test` | `tests/`, `tests/broken/` | pytest report `build/test-report.xml`. Fails if any test fails **or** any broken case is accepted. | ✅ |
| `make all` | given designs | M1: same as `make m1`. Later: the full Option 2 flow | ✅ |
| `make demo IN=<design.v> [TOP=<top>] [SV=-sv]` | one design | `build/demo/<name>/`: baseline A/B areas, both AIGs, cut summary, class histogram, redundancy of its classes. Never touches `results/m1`. | ✅ |
| `make clean` | n/a | removes `build/` only | ✅ |
| `make m1` | n/a | `m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy`, then `results/m1/summary.md` | ✅ |
| `make m1-baseline [YOSYS=…]` | 6 designs × {usable, reduced} × {A, B} | `results/m1/baseline/**`, `table1.csv` | ✅ |
| `make m1-aigs` | 6 designs | `results/m1/aigs/**`, `manifest.json` (12 entries) | ✅ |
| `make m1-cuts` | 12 AIGs | `results/m1/cuts/**` | ✅ |
| `make m1-hdclasses` | full HD lib, reduced lib | `results/m1/hd_classes.{json,csv}` | ✅ |
| `make m1-redundancy` | full HD lib | `results/m1/redundancy/{self_test.json,four_input_counts.json}` | ✅ |
| `make agent IN=<design>` / `make fixed IN=<design>` | design | `ai/runs/<run>.jsonl`, `runs/<run>/…` | US4 |
| `make web` / `make up` | n/a | dev server / docker compose | US4 |

## CLI (`uv run python -m dd2 <cmd>`)

```
dd2 baseline  --design NAME --library {reduced,usable} --script {A,B} --out DIR [--yosys BIN]
dd2 aig       --design NAME --variant {synth,restructured} --out DIR
dd2 cuts      --aig FILE --k 4 --out DIR [--sample-rate 0.01]
dd2 cutcheck  --cuts FILE.jsonl[.gz] --aig FILE           # exit 1 on any mismatch
dd2 hdclasses --liberty FULL.lib --reduced REDUCED.lib --out DIR
dd2 classify  --tt HEX --arity N --liberty FULL.lib         # prints a RedundancyMatch JSON
dd2 selftest  --liberty FULL.lib --out DIR                  # exit 1 unless SelfTestReport.pass
dd2 env       --out FILE
```
The mapping command string is **exactly** the one in handout §2 (`read_verilog [-sv]; synth -flatten
-top; dfflibmap -liberty; abc -liberty -script <A|B>; opt_clean -purge; stat -liberty`), plus a trailing
`tee -o stat.json stat -json -liberty` (research D-3). A contract test compares it with `given/scripts/map.sh`.
