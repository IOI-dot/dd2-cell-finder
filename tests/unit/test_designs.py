from dd2 import designs


def test_catalog():
    req = designs.required()
    assert [d.name for d in req] == ["cpu8", "dsp8", "arlet6502", "uart_apb", "risc8", "fir10"]
    assert [d.top for d in req] == ["cpu8", "dsp8", "cpu", "uart_apb_master", "cpu", "fir10"]
    assert len(designs.ALL) == 12
    assert [d.name for d in designs.ALL if d.sv] == ["pic1826"]
    assert designs.get("risc8").top == "cpu"
    assert designs.HANDOUT_TABLE1["cpu8"] == {("usable", "A"): 4186.5, ("reduced", "A"): 4186.5,
                                              ("usable", "B"): 4367.9, ("reduced", "B"): 4359.2}
