"""Positive and deliberately broken mapping, using actual Yosys and ABC."""
import shutil
import pytest
from dd2 import designs,paths
from dd2m2 import evaluate


@pytest.mark.skipif(not shutil.which('yosys') or not shutil.which('yosys-abc'),reason='requires Yosys/ABC')
def test_mapping_proof_accepts_correct_and_rejects_wrong_logic(tmp_path):
    lib=paths.given()/'hd_reduced.lib'
    if not lib.exists():pytest.skip('course inputs not configured')
    src=tmp_path/'toy.v';src.write_text('module toy(input A,B,output Y); assign Y=A&B; endmodule\n')
    d=designs.Design('toy','toy',False)
    out=tmp_path/'mapping'
    evaluate.map_design(d,src,lib,'A',out)
    assert evaluate.verify_mapping(d,lib,out)['status']=='pass'
    (out/'mapped.v').write_text('module toy(input A,B,output Y); assign Y=A|B; endmodule\n')
    result=evaluate.verify_mapping(d,lib,out)
    assert result['status']=='fail' and result['abc_cec']=='fail'


@pytest.mark.skipif(not shutil.which('yosys') or not shutil.which('yosys-abc'),reason='requires Yosys/ABC')
def test_async_register_identity_survives_mapping(tmp_path):
    lib=paths.given()/'hd_reduced.lib'
    if not lib.exists():pytest.skip('course inputs not configured')
    src=tmp_path/'toy.v'
    src.write_text('module toy(input clk,rstn,A,B,output reg Q); always @(posedge clk or negedge rstn) if(!rstn) Q<=0; else Q<=A^B; endmodule\n')
    d=designs.Design('toy','toy',False);out=tmp_path/'mapping'
    evaluate.map_design(d,src,lib,'B',out)
    assert evaluate.verify_mapping(d,lib,out)['status']=='pass'
