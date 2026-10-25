# Instructions for the AI assistant

## Project
Option 2: find repeated Boolean functions in synthesized circuits,
identify functions missing from SKY130 HD, and measure custom-cell savings.
Use Python, Yosys/ABC and OpenSTA.

## Verification
make check checks the environment.
make test runs correctness checks and deliberately broken cases.
These targets must be implemented; the supplied template is incomplete.

## Rules
- Pass or fail comes from check scripts.
- Report numbers must come from saved flow outputs.
- Never change check scripts, broken cases or the PDK.
- Never invent results or claim unrun tests passed.
- Never move checkpoint tags after their deadlines.
- Never commit the PDK, given files, build trees or files over 50 MB.
- Save report evidence in results/.
- Record AI use and mistakes in ai/.
- Add an AI-assisted trailer to AI-assisted commits.
