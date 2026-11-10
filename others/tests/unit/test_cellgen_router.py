import pytest
from cellgen import router


def spacing(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return max(dx, dy) if min(dx, dy) == 0 else (dx * dx + dy * dy) ** 0.5


def test_straight_connection():
    w = router.connect([[(0.0, 0.0, 0.17, 0.17)], [(0.0, 1.0, 0.17, 1.17)]], (0.0, 0.0, 2.0, 2.0), [])
    assert w and all(abs((r[2] - r[0]) - 0.17) < 1e-9 or abs((r[3] - r[1]) - 0.17) < 1e-9 for r in w)


def test_detour_keeps_li_spacing():
    obstacle = (0.0, 0.5, 0.6, 0.7)              # another net between the two terminals
    w = router.connect([[(0.1, 0.0, 0.27, 0.17)], [(0.1, 1.2, 0.27, 1.37)]], (0.085, 0.085, 1.3, 1.3), [obstacle])
    assert w and all(spacing(r, obstacle) >= 0.17 - 1e-9 for r in w)


def test_impossible_route_returns_none():
    wall = (0.0, 0.5, 2.0, 0.7)
    assert router.connect([[(0.1, 0.0, 0.27, 0.17)], [(0.1, 1.2, 0.27, 1.37)]], (0.085, 0.085, 1.3, 1.3), [wall]) is None


def test_drc_parser_keeps_every_reason():
    from cellgen import eda
    log = ("DRC_BBOX 0 0 276 544\nDRC_COUNT 3\nDRC_WHY {Diffusion spacing < 0.27um (diff/tap.3)} {{1 2 3 4}} "
           "{All nwells must contain metal-connected N+ taps (nwell.4)} {{5 6 7 8}} {Some rule without a tag} {{9 9 9 9}}\n")
    d = eda.parse_drc(log)
    assert d["rules"] == sorted(["diff/tap.3", "nwell.4", "Some rule without a tag"]), d


def test_drc_count_cannot_hide_listed_errors():
    from cellgen import eda
    d = eda.parse_drc("DRC_COUNT 0\nDRC_WHY {Local interconnect spacing < 0.17um (li.3)} {{1 2 3 4} {5 6 7 8}}\n")
    assert d["errors"] == 2 and d["rules"] == ["li.3"]


def test_standalone_drc_with_unparsed_errors_fails():
    pytest.importorskip("klayout", reason="Option 1 needs KLayout/GDSfactory")
    from cellgen import flow
    assert not flow.standalone_ok({"errors": 2, "rules": []})
    assert flow.standalone_ok({"errors": 3, "rules": ["LU.2", "LU.3", "nwell.4"]})
    assert flow.standalone_ok({"errors": 0, "rules": []})
    assert not flow.standalone_ok({"errors": None, "rules": []})
