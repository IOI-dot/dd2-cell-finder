# GB4 Option 2 report preparation

Use the final measurements before exporting the two required PDFs. Deadline
Tuesday 10 November 2026. The clean-checkout demo and individual oral exam
are Wednesday 11 November.

## Technical report, up to 12 pages

1. Title, members and IDs, Option 2, AI development aid, and the submission revision.
2. Describe the finder, the AIG/cut flow, PN and NPN classes, redundancy classes,
   CMOS costs and the HD x1 area fit.
3. Use the measured records in `results/m1/`, `results/m2/` and `results/m3/`
   for class counts, fit errors and examples. State that the TA accepted GB4's
   recorded Table 4 result of six where the handout lists five.
4. List the verification checks and the deliberately broken case for each.
   Document the CEC and functional tutorial GLS scope.
5. Include final estimated and real Table 5, per-design OpenSTA delay,
   same-script and best-of-A/B reductions, the greedy curve, and the 30% test.
6. Compare `risc8`, `pic16` and `p16c5x`. Explain one frequent function that
   did not save area, based on actual mappings. Discuss differences between
   the scripts, estimated and real cells, and limits of the model.
7. Confirm each member's contributions and tool versions. Cite the generated
   files that support every reported number.

## AI report, 4 to 8 pages

Use the AI-use and mistakes logs as the source. Separate the team's decisions
from the AI's implementation work. Record the tools, models and costs the
team can substantiate. Describe how requests were specified and checked.
Use five logged mistakes with the corresponding checks and why a weaker
check would or would not have caught each one. Explain time saved and spent,
one decision kept with a human, and what the team would delegate next time.
Confirm individual contributions, missing log commit references, and
AI-assisted commit trailers against Git history.

Before tagging, confirm the PDF filenames are `report.pdf` and
`ai_report.pdf`, put their sources next to them, and rehearse
`make demo IN=...` on an unseen design in a clean checkout.
