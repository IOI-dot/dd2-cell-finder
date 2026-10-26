# DD2 Project 1: student pack

CSCE 3304 Digital Design II - Fall 2026. Released Tuesday 20 October 2026; submission
Tuesday 10 November; interviews Wednesday 11 November. The handouts are given separately;
section 1.4 of the overview lists everything in this pack.

| Path | For | What it is |
|---|---|---|
| `given/plan_hd.json` | Option 1 | The HD cell frame, measured from the GDS of inv_1 and nand2_1. `frame` must not change; `reference` shows HD's own choices inside it |
| `given/hd_reduced.lib` | Both | The 189-cell reduced HD library (TT, 1.8 V, 25 C): Option 2's baseline, and what Option 1's round-trip test appends to |
| `given/hd_usable.lib` | Option 2 | The 307 usable HD cells that Table 1 of the Option 2 handout compares against |
| `given/designs/` | Option 2 | The twelve designs of the Option 2 handout's Table 2. Each keeps its licence notice; pic1826.v needs `-sv` |
| `given/scripts/map.sh` | Option 2 | The mapping commands of the Option 2 handout's section 2: `map.sh <design.v> <top> <liberty> <A or B> [-sv]` |
| `given/examples/new_cell_example.lib` | Both | The Liberty cell of the Option 2 handout's section 6, to append inside `hd_reduced.lib` |
| `container/` | Option 1 | The recipe for the `dd2-layout-tools` image (Magic 8.3.684, Netgen 1.5.133, ngspice 47 with the BSIM4 fix) and the stress test that `make check` runs. See `container/README.md` |
| `repo_template/` | Both | Copy into your GitHub repository on day one: the layout of overview section 5.1, the README template, an AGENTS.md outline, empty AI logs, a Makefile with the required targets, and the example request and response of Appendix A |

Keep this pack outside your repository; `make setup` links `given/` into it.
Given later: a cell generator, to three-student Option 2 groups during the project.
