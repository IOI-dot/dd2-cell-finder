"""Our mapping commands must be exactly those of given/scripts/map.sh (handout section 2)."""
import re

from dd2 import mapping, paths


def map_sh():
    return (paths.given() / "scripts" / "map.sh").read_text()


def test_scripts_identical():
    sh = map_sh()
    assert mapping.SCRIPTS["A"] == re.search(r"A\) SCRIPT='([^']+)'", sh).group(1)
    assert mapping.SCRIPTS["B"] == re.search(r"B\) SCRIPT='([^']+)'", sh).group(1)


def test_command_sequence_identical():
    sh = map_sh()
    template = re.search(r'yosys -q -p "([^"]+)"', sh).group(1)
    for script in "AB":
        for sv in ("", "-sv"):
            expected = (template.replace("$SV", sv).replace("$V", "D.v").replace("$TOP", "T")
                        .replace("$LIB", "L.lib").replace("$SCRIPT", mapping.SCRIPTS[script]))
            expected = expected.replace("tee -o /dev/stdout stat -liberty L.lib", "").rstrip("; ")
            ours = mapping.yosys_script("D.v", "T", "L.lib", script, sv=bool(sv))
            # Ours = the handout commands, then only extra stat outputs written to files.
            assert ours.startswith(expected + "; "), (ours, expected)
            assert all(c.strip().startswith("tee ") for c in ours[len(expected) + 2:].split("; "))


def test_parse_stat_json():
    stat = {"modules": {"\\cpu8": {"area": 4195.2736, "num_cells": 552,
                                   "num_cells_by_type": {"sky130_fd_sc_hd__inv_1": 3}}}}
    assert mapping.parse_stat(stat, "cpu8") == (4195.2736, 552, {"sky130_fd_sc_hd__inv_1": 3})
