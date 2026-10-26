"""The two transient rules of Option 1 handout 4.2, each with a synthetic broken waveform."""
from cellgen import simulate

INPUTS, TT = ["A", "B"], 0x7            # nand2
SLOT = simulate.SLOT_NS * 1e-9


def ideal(glitch_slot=None, late_slot=None):
    """Y sampled every 10 ps: settles to the right rail early in each slot."""
    seq = simulate.sequence(len(INPUTS))
    times, ys = [], []
    for i, state in enumerate(seq):
        want = simulate.VDD * ((TT >> state) & 1)
        for s in range(int(SLOT / 10e-12)):
            t = i * SLOT + s * 10e-12
            y = want
            if i == glitch_slot and 50 <= s < 60:
                y = simulate.VDD - want            # a pulse to the wrong side while Y should hold
            if i == late_slot:
                y = simulate.VDD - want            # never reaches the new value in this slot
            times.append(t)
            ys.append(y)
    return times, ys


def test_ideal_waveform_passes():
    assert simulate.check_waveform(*ideal(), INPUTS, TT) == []


def test_glitch_while_holding_is_caught():
    seq = simulate.sequence(len(INPUTS))
    hold = next(i for i in range(1, len(seq)) if (TT >> seq[i - 1]) & 1 == (TT >> seq[i]) & 1)
    errs = simulate.check_waveform(*ideal(glitch_slot=hold), INPUTS, TT)
    assert any("crossed VDD/2" in e for e in errs)


def test_late_settling_is_caught():
    errs = simulate.check_waveform(*ideal(late_slot=3), INPUTS, TT)
    assert any("before the next edge" in e for e in errs)


def test_sequence_toggles_each_input_from_every_state():
    seq = simulate.sequence(2)
    pairs = {(seq[i], seq[i + 1]) for i in range(0, len(seq), 2)}
    assert pairs == {(s, s ^ (1 << k)) for s in range(4) for k in range(2)}
