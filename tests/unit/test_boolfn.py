from dd2 import boolfn as bf


def tt_of(f, n=4):
    return sum(1 << i for i in range(1 << n) if f(*[(i >> k) & 1 for k in range(n)]))


def test_var_tt_lsb_is_input0():
    assert bf.var_tt(0, 2) == 0b1010 and bf.var_tt(1, 2) == 0b1100


def test_appendix_a_vector():
    t = bf.eval_expr("!((C & D) | (A & B & (C | D)))", ["A", "B", "C", "D"])
    assert t == 0x077F and bf.to_hex(t, 4) == "0x077F"


def test_liberty_operators_and_precedence():
    names = ["A", "B", "C"]
    assert bf.eval_expr("A&B | C", names) == tt_of(lambda a, b, c: (a and b) or c, 3)
    assert bf.eval_expr("A ^ B & C", names) == tt_of(lambda a, b, c: a ^ (b and c), 3)
    assert bf.eval_expr("(A+B)*C'", names) == tt_of(lambda a, b, c: (a or b) and not c, 3)
    assert bf.eval_expr("!A !B", names) == tt_of(lambda a, b, c: not a and not b, 3)


def test_bad_expressions_raise():
    for bad in ["A & ", "A $ B", "(A", "E", "A B)"]:
        try:
            bf.eval_expr(bad, ["A", "B"])
        except ValueError:
            continue
        raise AssertionError(bad)


def test_permute_flip_negate_depends():
    t = tt_of(lambda a, b, c, d: a and not b)
    assert bf.permute(t, 4, (1, 0, 2, 3)) == tt_of(lambda a, b, c, d: b and not a)
    assert bf.flip_input(t, 4, 1) == tt_of(lambda a, b, c, d: a and b)
    assert bf.negate(t, 4) == tt_of(lambda a, b, c, d: not (a and not b))
    assert bf.depends_on(t, 4) == [0, 1]
    assert bf.shrink(t, 4, [0, 1]) == tt_of(lambda a, b: a and not b, 2)


def test_canonical_forms():
    and2 = tt_of(lambda a, b: a and b, 2)
    nand2 = bf.negate(and2, 2)
    a_nb = tt_of(lambda a, b: a and not b, 2)
    assert bf.canon_p(and2, 2) != bf.canon_p(nand2, 2)
    assert bf.canon_pn(and2, 2) == bf.canon_pn(nand2, 2)
    assert bf.canon_pn(and2, 2) != bf.canon_pn(a_nb, 2)
    assert bf.canon_npn(and2, 2) == bf.canon_npn(a_nb, 2)


def test_class_counts_known_values():
    # All 2-input functions: 12 P-classes, 6 PN-classes (A&!B pairs with !A|B), 4 NPN-classes.
    assert len({bf.canon_p(t, 2) for t in range(16)}) == 12
    assert len({bf.canon_pn(t, 2) for t in range(16)}) == 6
    assert len({bf.canon_npn(t, 2) for t in range(16)}) == 4
    # 4-input NPN classes: 222 (classical result).
    assert len({bf.canon_npn(t, 4) for t in range(1 << 16)}) == 222
