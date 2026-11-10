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
MCON = Rule(0.17, "ct.1", "li1 to met1 contact size")
MET1_W = Rule(0.23, "ct.4", "met1 wire: the contact plus 0.03 on each side (ct.4)")
MET1_END = Rule(0.06, "ct.4", "met1 enclosure of a contact on two opposite sides")
MET1_SP = Rule(0.14, "m1.2", "met1 to met1 spacing")
LI_LOW = Rule(0.255, "li.3", "lowest non-rail li1: the rail strip's top (0.085) + li.3")
LI_HIGH = Rule(2.465, "li.3", "highest non-rail li1: the rail strip's bottom (2.635) - li.3")
LI_EDGE = Rule(0.17, "li.3", "wire centre from the cell edge: li.1/2 + li.3/2, so neighbours keep li.3")
SEED_N = Rule(0.295, "licon.5c", "first NMOS contact, bottom: diffusion 0.235 + 0.06")
SEED_N_Y = Rule(0.335, "li.5", "the same with li1 over and under it: LI_LOW + 0.08")
SEED_P = Rule(2.255, "licon.5c", "first PMOS contact, bottom: diffusion 2.485 - 0.06 - licon.1")
SEED_P_Y = Rule(2.215, "li.5", "the same with li1 over and under it: LI_HIGH - 0.08 - licon.1")
MIN_DEVICE_W = Rule(0.25, "licon.5a", "narrowest device with a contact: licon.1 + 2 * 0.04")
PAD_OUT = Rule(0.065, "licon.8", "pad contact outside its stripe: leaves li.3 + li.1 + li.3 at a splay, as HD's nand3_1")
PAD_ON = Rule(-0.10, "licon.8", "pad contact 0.05 inside the stripe's edge, overlapping it; the pad then needs only 0.27 of poly")
CROSS_GAP = Rule(0.51, "li.3", "room for a wire between two pads: li.3 + li.1 + li.3")
MET1_LOW = Rule(0.495, "m1.2", "lowest met1 wire centre: the rail's top (0.24) + m1.2 + half a wire")
MET1_HIGH = Rule(2.225, "m1.2", "highest met1 wire centre: the rail's bottom (2.48) - m1.2 - half a wire")
SITE = Rule(0.46, "unithd", "placement site width (plan_hd.json)")

ALL = [v for v in dict(globals()).values() if isinstance(v, Rule)]


def snap(x: float) -> float:
    """Round to the manufacturing grid."""
    return round(round(x / GRID.value) * GRID.value, 3)
