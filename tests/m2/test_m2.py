import math
from pathlib import Path

from dd2 import boolfn as bf, liberty
from dd2m2.cost import implementation, fit_model, predict_area
from dd2m2.library import write_library
from dd2m2.cones import mapped_cuts


def test_cost_implementations_are_functionally_correct_and_obey_stack_limit():
    for n, tables in [(1, [1, 2]), (2, range(16)),
                      (3, [0xE8, 0xCA, 0x96, 0x69, 0x07]),
                      (4, [0x0017, 0x011F, 0x013F, 0x037F, 0x077F, 0x17FF, 0x6996, 0x8000])]:
        for tt in tables:
            c = implementation(tt, n)
            assert bf.eval_expr(c['expression'], list('ABCD'[:n])) == tt
            assert c['transistors'] >= 0 and c['max_series'] <= 3
            assert c['verified_truth_table'] == bf.to_hex(tt, n)


def test_model_quantizes_area_and_reports_held_out_errors():
    rows = [dict(name=str(i), transistors=2*i, stages=1+i%2,
                 inverters=i%2, area_um2=1.2512*(i+2)) for i in range(1,9)]
    model, records = fit_model(rows)
    assert len(records) == len(rows)
    assert all('loo_error_pct' in r for r in records)
    area = predict_area(model, dict(transistors=12, stages=2, inverters=1))
    assert area > 0 and math.isclose(area/1.2512, round(area/1.2512))


def test_library_round_trip_and_timing_arcs(tmp_path):
    base = tmp_path/'base.lib'
    base.write_text('library (test) { time_unit : "1ns"; capacitive_load_unit (1,pf); }')
    out = tmp_path/'extended.lib'
    cells = [dict(request_id='test', sizing='hd', name='dd2_g1__test_1', inputs=list('ABCD'), output='Y',
                  expression='!((C&D)|(A&B&(C|D)))', truth_table='0x077F',
                  estimated_area_um2=8.7584)]
    write_library(base, out, cells)
    parsed = liberty.read_cells(out)
    assert len(parsed) == 1 and parsed[0].tt == 0x077F
    assert out.read_text().count('related_pin') == 4


def test_shared_internal_gate_is_not_counted_as_removed():
    cell=liberty.LibCell('NAND2',['A','B'],'Y','!(A&B)',7,4.)
    def gate(a,b,y):return dict(type='NAND2',port_directions={'A':'input','B':'input','Y':'output'},
                              connections={'A':[a],'B':[b],'Y':[y]})
    mod={'cells':{'inner':gate(1,2,4),'outer':gate(4,3,5)},
         'ports':{'Y':{'direction':'output','bits':[5]},'shared':{'direction':'output','bits':[4]}}}
    rows=list(mapped_cuts({'modules':{'top':mod}},'top',[cell]))
    r=next(r for r in rows if r['root']==5 and r['leaves']==[1,2,3])
    assert r['replaced_area_um2']==4. and r['removed_cells']==['outer']
    assert r['shared_cells_retained']==1
    del mod['ports']['shared']
    r=next(r for r in mapped_cuts({'modules':{'top':mod}},'top',[cell]) if r['root']==5 and r['leaves']==[1,2,3])
    assert r['replaced_area_um2']==8. and set(r['removed_cells'])=={'inner','outer'}
