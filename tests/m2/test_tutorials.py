import json
import shutil

import pytest

from dd2 import paths
from dd2m2 import evaluate, tutorials
from dd2m2 import flow


def test_simulation_requires_marker_exit_code_and_no_error():
    marker='PASS: example'
    assert tutorials.simulation_passed(0, marker, marker)
    assert not tutorials.simulation_passed(0, 'finished', marker)
    assert not tutorials.simulation_passed(1, marker, marker)
    for bad in ['ERROR: wrong output', 'FAIL: 2 errors', 'FATAL: stop', 'MISMATCH: output']:
        assert not tutorials.simulation_passed(0, marker+'\n'+bad, marker)


def test_missing_inputs_cannot_be_claimed_supplied(tmp_path,monkeypatch):
    monkeypatch.setattr(paths,'ROOT',tmp_path)
    assert not tutorials.supplied('spm')
    with pytest.raises(ValueError,match='missing original tutorial'):
        tutorials.resolve('spm')


def test_readiness_requires_tutorial_proofs_and_keeps_reference_disagreement(tmp_path):
    names=['cpu8','dsp8','arlet6502','uart_apb','risc8','fir10']
    rows=[dict(baseline_equivalence='pass',extended_equivalence='pass',
               baseline_timing_status='pass',extended_timing_status='pass')]
    env={'overview_versions':{'supported':True}}
    tutorial_results={n:{'rtl_supplied':True,'mapping_and_gate_simulation_verified':True}
                      for n in tutorials.SPECS}
    data=flow.summary(tmp_path,names,rows,[],{'status':'match'},env,tutorial_results)
    assert data['checkpoint_ready']
    data=flow.summary(tmp_path,names,rows,[],{'status':'unresolved reference disagreement'},env,tutorial_results)
    assert not data['checkpoint_ready'] and not data['checks']['reference_table4_agrees']
    assert data['experimental_flow_status']=='pass'
    tutorial_results['spm']['mapping_and_gate_simulation_verified']=False
    data=flow.summary(tmp_path,names,rows,[],{'status':'match'},env,tutorial_results)
    assert not data['checkpoint_ready'] and data['experimental_flow_status']=='fail'


@pytest.mark.skipif(not shutil.which('iverilog') or not shutil.which('yosys'),reason='Yosys and Icarus required')
def test_wrong_gate_function_fails_original_multiplier_testbench(tmp_path):
    if not tutorials.supplied('multiplier'):pytest.skip('external tutorial inputs required')
    wrong=tmp_path/'wrong.v'
    wrong.write_text('module mul(input [7:0] mp,mc, output [15:0] p); assign p=0; endmodule\n')
    result=tutorials.simulate('multiplier',[wrong],tmp_path/'bad')
    assert result['status']=='fail'
    assert 'MISMATCH' in (tmp_path/'bad/simulation.log').read_text()


@pytest.mark.parametrize('name',list(tutorials.SPECS))
@pytest.mark.skipif(not shutil.which('iverilog') or not shutil.which('yosys'),reason='Yosys and Icarus required')
def test_real_tutorial_rtl_and_both_script_gate_simulations(name,tmp_path):
    if not tutorials.supplied(name):pytest.skip('external tutorial inputs required')
    d,src=tutorials.resolve(name)
    assert tutorials.simulate(name,[src],tmp_path/'rtl')['status']=='pass'
    lib=paths.given()/'hd_reduced.lib'
    for script in ['A','B']:
        dest=tmp_path/'mapping'/script
        evaluate.map_design(d,src,lib,script,dest)
        assert evaluate.verify_mapping(d,lib,dest)['status']=='pass'
        assert tutorials.simulate(name,[dest/'mapped.v'],tmp_path/'gls'/script,lib)['status']=='pass'
        saved=json.loads((tmp_path/'gls'/script/'simulation.json').read_text())
        assert saved['inputs'] and saved['scope'].startswith('zero-delay')
