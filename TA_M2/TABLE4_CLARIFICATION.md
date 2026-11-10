# Table 4 clarification for GB4

The checker reproduces the Exists, Exists-with-inverter, Contained and New counts,
and the nine one-stage and eight read-once classes. The limited one-stage row
gives six classes where the handout gives five. The reference number remains unchanged.

| Truth table | Expression | Transistors | NMOS series | PMOS series |
|---|---|---:|---:|---:|
| 0x0017 | `!((D\|((A\|B)&(C\|(A&B)))))` | 12 | 3 | 3 |
| 0x011F | `!(((C&D)\|((A\|B)&(C\|D))))` | 12 | 2 | 3 |
| 0x013F | `!(((B\|D)&(C\|(D&(A\|B)))))` | 12 | 3 | 3 |
| 0x037F | `!(((B&D)\|(C&(D\|(A&B)))))` | 12 | 3 | 3 |
| 0x077F | `!(((C\|D)&((A&B)\|(C&D))))` | 12 | 3 | 2 |
| 0x17FF | `!((D&((A&B)\|(C&(A\|B)))))` | 12 | 3 | 3 |

Each row has a verified 16-row truth table and uses six literal occurrences,
giving six NMOS plus six PMOS transistors in complementary series/parallel networks.
Input A is the least significant truth-table variable.

TA accepted GB4's six-versus-five result as submitted, per the team.
