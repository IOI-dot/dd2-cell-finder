# Contract: committed evidence under `results/m1/`

The TA's cp1 meeting is answered from these files. Every path below is written by the flow.

```text
results/m1/
├── setup.json, environment.json          # links, tool versions + sha256 of binaries, PDK ciel hash
├── baseline/<design>/<reduced|usable>/<A|B>/{result.json, yosys.log, stat.json}
├── table1.csv                             # 24 measured cells + handout column + delta %
├── aigs/manifest.json                     # 12 entries: header counts, FFs, sha256, commands
├── aigs/<design>/{synth,restructured}.{aig,json,log}
├── aigs/compare.csv                       # per design: ANDs/levels before vs after restructuring
├── cuts/<design>/<variant>.summary.json   # CutValidation
├── cuts/<design>/<variant>.sample.jsonl   # deterministic 1% sample
├── cuts/summary.csv                       # design, variant, ANDs, cuts, PN classes, NPN classes, failures
├── hd_classes.json, hd_classes.csv, hd_pn_classes.csv
├── redundancy/self_test.json              # SelfTestReport
├── redundancy/four_input_counts.json      # all 3,904 P-classes with their class and witness
└── summary.md                             # generated M1 index: each requirement → file → status
```

Size rules: an `.aig` file is under 1 MB; full cut lists go to `build/` only; a test fails if any
file under `results/` exceeds 50 MB (overview §5.1).

`summary.md` is **generated**. Its status cells are copied from each record's `run.status`, never typed.
