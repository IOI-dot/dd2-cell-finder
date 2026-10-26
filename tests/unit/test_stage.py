from dd2 import boolfn as bf, stage

N = 4
V = [bf.var_tt(k, N) for k in range(N)]
FULL = bf.mask(N)


def test_known_points():
    assert (2, 2, 1) in stage.points(V[0] & V[1], N)                      # nand2
    assert (3, 1, 3) in stage.points(V[0] | V[1] | V[2], N)               # nor3
    assert (3, 2, 2) in stage.points((V[0] & V[1]) | V[2], N)             # a21oi
    assert (6, 3, 2) in stage.points(0x077F ^ FULL, N)                    # maj4n, Appendix A


def test_one_stage():
    assert stage.one_stage(0x077F, N)                                    # negative unate
    assert not stage.one_stage(V[0] & V[1], N)                           # and2: positive unate
    assert not stage.one_stage(V[0] ^ V[1], N)                           # xor: binate


def test_best_respects_limits():
    assert stage.best(0x077F, N) == (6, 3, 2)
    nand4 = (V[0] & V[1] & V[2] & V[3]) ^ FULL
    assert stage.best(nand4, N) is None                                   # 4 NMOS in series
    assert stage.best(nand4, N, max_series=4) == (4, 4, 1)
