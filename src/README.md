# Option 2 source

- `dd2/` is the M1 and shared core. It reads AIG and Liberty, handles Boolean
  functions and cuts, checks redundancy and equivalence, and records provenance.
- `dd2m2/` is the M2 and M3 flow. It fits area, ranks candidates, writes requests,
  imports characterized Liberty, and runs A/B remapping and analysis.
  `final_flow.py` is the M3 and unseen-design entry point.

The existing package names preserve the command line and import paths.
