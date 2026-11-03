"""The data behind the studio's step views: real outputs turned into tables, never estimates."""
import subprocess

import pytest

from cellgen import euler, network, stepdata

NAND = """.subckt c A B Y VGND VPWR VPB VNB
X0 Y A VPWR VPB sky130_fd_pr__pfet_01v8_hvt ad=0.2 pd=1 as=0.2 ps=1 w=1 l=0.15
X1 Y B VPWR VPB sky130_fd_pr__pfet_01v8_hvt ad=0.2 pd=1 as=0.2 ps=1 w=1 l=0.15
X2 Y A a_1_1# VNB sky130_fd_pr__nfet_01v8 ad=0.1 pd=1 as=0.1 ps=1 w=0.65 l=0.15
X3 a_1_1# B VGND VNB sky130_fd_pr__nfet_01v8 ad=0.1 pd=1 as=0.1 ps=1 w=0.65 l=0.15
.ends
"""
LVS = """
Circuit 1: c                     |Circuit 2: c
-------------------------------------------|-------------------------------------------
sky130_fd_pr__pfet_01v8_hvt (2)            |sky130_fd_pr__pfet_01v8_hvt (2)
sky130_fd_pr__nfet_01v8 (2)                |sky130_fd_pr__nfet_01v8 (2)
Number of devices: 4                       |Number of devices: 4
Number of nets: 6                          |Number of nets: 5
---------------------------------------------------------------------------------------
Circuits match uniquely.
"""
RC = """R0 VGND VGND.n0 200.5
R1 VGND.n0 VGND.t1 32.5
R2 Y.n1 Y 10
C0 VGND C 0.5f
C1 VPB Y 1.5f
C2 Y.n1 VGND 0.25f
"""


def net_of(tt=0b0111, inputs=("A", "B")):
    return network.size(network.synthesize(tt, list(inputs)), "hd", 0.65, 1.0), tt


def test_switch_rows_list_every_input_row_with_its_conducting_network():
    net, tt = net_of()
    rows = stepdata.switch_rows(net, tt)
    assert [r["row"] for r in rows] == [0, 1, 2, 3]
    assert [r["expected"] for r in rows] == [1, 1, 1, 0]
    assert rows[3] | {"inputs": None} == {"row": 3, "inputs": None, "up": False, "down": True, "y": 0, "expected": 0}
    assert rows[0]["up"] and not rows[0]["down"] and rows[0]["y"] == 1


def test_switch_rows_show_a_wrong_network_as_wrong():
    net, _ = net_of()
    wrong = stepdata.switch_rows(net, 0b1000)
    assert [r["y"] == r["expected"] for r in wrong] == [False, False, False, False]


def test_orders_give_each_slot_with_its_nets():
    net, _ = net_of()
    orders = euler.candidates(net)
    out = stepdata.orders(orders)
    assert len(out) == len(orders)
    first = out[0]
    assert first["gates"] == list(orders[0].gates) and first["breaks"] == orders[0].breaks
    assert len(first["p"]) == len(first["n"]) == len(first["gates"])
    assert set(first["n"][0]) == {"left", "right"}


def test_devices_read_an_extracted_netlist():
    d = stepdata.devices(NAND)
    assert len(d) == 4
    assert d[2] == {"name": "X2", "type": "n", "gate": "A", "drain": "Y", "source": "a_1_1#", "w": 0.65, "l": 0.15}
    assert d[0]["type"] == "p"


def test_lvs_counts_come_from_both_columns():
    c = stepdata.lvs_counts(LVS)
    assert c == {"layout": {"devices": 4, "nets": 6}, "schematic": {"devices": 4, "nets": 5}}
    assert stepdata.lvs_counts("no table") == {}


def test_rc_stats_sum_by_real_net():
    r = stepdata.rc_stats(RC)
    assert r["resistors"] == 3 and r["capacitors"] == 3
    by = {x["net"]: x for x in r["nets"]}
    assert by["VGND"]["ohms"] == pytest.approx(233.0)
    assert by["Y"]["ohms"] == pytest.approx(10)
    assert by["Y"]["ff"] == pytest.approx(1.75)
    assert by["VGND"]["ff"] == pytest.approx(0.75)


def test_icarus_rows_rerun_the_compiled_model(tmp_path):
    src = tmp_path / "m.v"
    src.write_text('module tb; initial begin $display("ROW 0 1"); $display("ROW 1 0"); end endmodule\n')
    subprocess.run(["iverilog", "-o", str(tmp_path / "model_sim"), str(src)], check=True)
    assert stepdata.icarus_rows(tmp_path) == {0: "1", 1: "0"}


def test_icarus_rows_are_empty_without_a_compiled_model(tmp_path):
    assert stepdata.icarus_rows(tmp_path) == {}
