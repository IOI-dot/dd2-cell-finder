from dd2 import boolfn as bf
from dd2m2.cost import implementation


def test_four_input_nand_and_nor_use_small_valid_multistage_realizations():
    for expr in ['!(A&B&C&D)','!(A|B|C|D)']:
        tt=bf.eval_expr(expr,list('ABCD'))
        cost=implementation(tt,4)
        assert cost['max_series']<=3
        assert cost['transistors']<=12
        assert bf.eval_expr(cost['expression'],list('ABCD'))==tt


def test_hd_calibration_can_describe_native_four_stack_cells():
    for expr in ['!(A&B&C&D)','!(A|B|C|D)']:
        tt=bf.eval_expr(expr,list('ABCD'))
        native=implementation(tt,4,max_series=4)
        assert native['transistors']==8 and native['stages']==1
        assert native['max_series']==4
        assert implementation(tt,4)['max_series']<=3
