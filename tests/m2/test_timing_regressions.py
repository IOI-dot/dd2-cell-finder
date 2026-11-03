"""Execute generated Tcl against the documented path/point object interface.
The real OpenSTA integration test below runs wherever sta is installed.
"""
import ctypes
import ctypes.util
import os
import shutil
import pytest
from dd2 import designs,paths
from dd2m2 import evaluate


def test_tcl_uses_endpoint_point_arrival_and_excludes_clock_input():
    libpath=os.environ.get('DD2_TCL_LIBRARY') or ctypes.util.find_library('tcl8.6')
    if not libpath:pytest.skip('Tcl shared library unavailable')
    tcl=ctypes.CDLL(libpath)
    tcl.Tcl_CreateInterp.restype=ctypes.c_void_p
    tcl.Tcl_Eval.argtypes=[ctypes.c_void_p,ctypes.c_char_p];tcl.Tcl_Eval.restype=ctypes.c_int
    tcl.Tcl_GetStringResult.argtypes=[ctypes.c_void_p];tcl.Tcl_GetStringResult.restype=ctypes.c_char_p
    tcl.Tcl_DeleteInterp.argtypes=[ctypes.c_void_p]
    interp=tcl.Tcl_CreateInterp()
    def run(script):
        code=tcl.Tcl_Eval(interp,script.encode());result=tcl.Tcl_GetStringResult(interp).decode()
        assert code==0,result
        return result
    try:
        run('''
proc read_liberty {args} {}
proc read_verilog {args} {}
proc link_design {args} {}
proc all_inputs {} {return {clock_port data_port}}
proc all_outputs {} {return {out_port}}
proc all_registers {args} {return {reg0 reg1}}
proc get_ports {args} {return {clock_port data_port out_port}}
proc get_full_name {p} {if {$p eq "clock_port"} {return clk}; return $p}
proc create_clock {args} {}
proc all_clocks {} {return {clk}}
proc set_input_transition {args} {}
proc set_clock_transition {args} {}
proc set_load {args} {}
proc set_input_delay {args} {
  set ::recorded_inputs [lindex $args end]
  if {[lsearch -exact $::recorded_inputs clock_port] >= 0} {error "input delay applied to clock"}
}
proc set_output_delay {args} {}
proc report_checks {args} {}
proc find_timing_paths {args} {return {path0 path1}}
proc get_property {object prop} {
  if {$object eq "path0" && $prop eq "points"} {return {point0 point1}}
  if {$object eq "path1" && $prop eq "points"} {return {point2 point3}}
  if {$object eq "point1" && $prop eq "arrival"} {return 4.2668}
  if {$object eq "point3" && $prop eq "arrival"} {return 5.125}
  error "unsupported property $prop on object $object"
}
proc exit {args} {}
''')
        script=evaluate.timing_script(designs.Design('toy','toy',False),'library.lib','out')
        run(script)
        assert float(run('set worst'))==5.125
        assert run('set recorded_inputs')=='data_port'
    finally:tcl.Tcl_DeleteInterp(interp)


def test_tool_error_cannot_be_hidden_by_a_numeric_marker(tmp_path,monkeypatch):
    def broken_run(argv,log,**kwargs):
        log.write_text('Error 123: deliberately invalid timing input\nDD2_WORST_ARRIVAL_NS=5\n')
        return 0,0.
    monkeypatch.setattr(evaluate.tools,'run',broken_run)
    result=evaluate.timing(designs.Design('toy','toy',False),'library.lib',tmp_path)
    assert result['status']=='fail'


@pytest.mark.skipif(not shutil.which('sta') or not shutil.which('yosys'),reason='needs actual OpenSTA/Yosys')
def test_real_opensta_timing_of_mapped_logic(tmp_path):
    lib=paths.given()/'hd_reduced.lib'
    if not lib.is_file():pytest.skip('course library not configured')
    src=tmp_path/'toy.v';src.write_text('module toy(input A,B,output Y); assign Y=A&B; endmodule\n')
    d=designs.Design('toy','toy',False);out=tmp_path/'mapped'
    evaluate.map_design(d,src,lib,'A',out)
    result=evaluate.timing(d,lib,out)
    assert result['status']=='pass',(out/'timing.log').read_text()
    assert result['worst_arrival_ns']>0
