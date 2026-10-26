"""Every number the layout generator uses, with the SKY130 rule that sets it (um).

Option 1 handout, section 3.2: "every number in your plan must name the design rule that sets
it". The frame (bands, rails, implants) is not here: it is read from given/plan_hd.json and never
changed. Values were checked against Magic's sky130A DRC deck (drc(full)) on the generated cells;
`make o1-rules` writes this table to results/option1/rules.csv. The frame values come from
plan_hd.json, and Magic drc(full) confirms the result on every generated cell.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    value: float
    rule: str
    meaning: str


GRID = Rule(0.005, "x.2", "manufacturing grid")
POLY_W = Rule(0.15, "poly.1a", "minimum poly width = gate length L")
POLY_SP = Rule(0.21, "poly.2", "poly to poly spacing")
POLY_ENDCAP = Rule(0.13, "poly.8", "poly extension beyond diffusion (endcap)")
POLY_DIFF_SP = Rule(0.075, "poly.4", "poly (not gate) to diffusion spacing")
DIFF_W = Rule(0.15, "difftap.1", "minimum diffusion width")
DIFF_SP = Rule(0.27, "difftap.3", "diffusion to diffusion spacing; half of it is the cell margin")
SD_EXT = Rule(0.25, "poly.7", "diffusion extension beyond the gate (source/drain)")
LICON = Rule(0.17, "licon.1", "contact size")
LICON_SP = Rule(0.17, "licon.2", "contact to contact spacing")
LICON_DIFF_ENC = Rule(0.04, "licon.5a", "diffusion enclosure of a contact")
LICON_DIFF_ENC2 = Rule(0.06, "licon.5c", "diffusion enclosure of a contact on two opposite sides")
LICON_GATE_SP = Rule(0.05, "licon.11a", "diffusion contact to gate spacing (HD 0.15 um devices)")
LICON_POLY_ENC = Rule(0.05, "licon.8", "poly enclosure of a poly contact")
LICON_POLY_ENC2 = Rule(0.08, "licon.8a", "poly enclosure of a poly contact on two opposite sides")
LICON_POLY_DIFF_SP = Rule(0.19, "licon.14", "poly contact to diffusion spacing")
NPC_ENC = Rule(0.10, "licon.15", "npc enclosure of a poly contact")
LI_W = Rule(0.17, "li.1", "li1 width")
LI_SP = Rule(0.17, "li.3", "li1 spacing")
LI_ENC2 = Rule(0.08, "li.5", "li1 enclosure of a contact on two opposite sides")
SITE = Rule(0.46, "unithd", "placement site width (plan_hd.json)")

ALL = [v for v in dict(globals()).values() if isinstance(v, Rule)]


def snap(x: float) -> float:
    """Round to the manufacturing grid."""
    return round(round(x / GRID.value) * GRID.value, 3)
