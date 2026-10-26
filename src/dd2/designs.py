"""The designs of Option 2 Table 2, and the handout's reference numbers (labelled as such)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Design:
    name: str
    top: str
    required: bool
    sv: bool = False
    handout_ffs: int | None = None
    handout_ands: int | None = None


ALL = (
    Design("cpu8", "cpu8", True, handout_ffs=82, handout_ands=1265),
    Design("dsp8", "dsp8", True, handout_ffs=72, handout_ands=1973),
    Design("arlet6502", "cpu", True, handout_ffs=143, handout_ands=3221),
    Design("uart_apb", "uart_apb_master", True, handout_ffs=330, handout_ands=4673),
    Design("risc8", "cpu", True, handout_ffs=696, handout_ands=7750),
    Design("fir10", "fir10", True, handout_ffs=176, handout_ands=8795),
    Design("p16c5x", "P16C5x", False, handout_ffs=747, handout_ands=8167),
    Design("pic16", "PIC16C5x", False, handout_ffs=765, handout_ands=8276),
    Design("x18", "x18", False, handout_ffs=831, handout_ands=10151),
    Design("pic1826", "cpu", False, sv=True, handout_ffs=1181, handout_ands=12457),
    Design("xfir", "xfir", False, handout_ffs=176, handout_ands=15955),
    Design("chacha", "chacha", False, handout_ffs=1940, handout_ands=38658),
)

# Option 2 handout Table 1 (Yosys 0.33), um^2. Reference values only: never reported as ours.
HANDOUT_TABLE1 = {
    name: {("usable", "A"): ua, ("reduced", "A"): ra, ("usable", "B"): ub, ("reduced", "B"): rb}
    for name, ua, ra, ub, rb in (
        ("cpu8", 4186.5, 4186.5, 4367.9, 4359.2),
        ("dsp8", 5928.2, 5928.2, 6217.2, 6214.7),
        ("arlet6502", 9654.3, 9701.8, 9954.5, 9995.8),
        ("uart_apb", 12948.7, 12948.7, 13180.1, 13180.1),
        ("risc8", 28265.9, 28263.4, 27501.4, 27511.4),
        ("fir10", 25968.7, 25968.7, 29055.4, 29055.4),
    )
}
HANDOUT_YOSYS = "0.33"


def required():
    return [d for d in ALL if d.required]


def get(name: str) -> Design:
    for d in ALL:
        if d.name == name:
            return d
    raise KeyError(f"unknown design {name!r}; known: {', '.join(d.name for d in ALL)}")
