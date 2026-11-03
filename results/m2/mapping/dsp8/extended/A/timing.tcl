read_liberty {/home/hank2b/dd2-cell-finder/results/m2/hd_extended_estimated.lib}
read_verilog {/home/hank2b/dd2-cell-finder/results/m2/mapping/dsp8/extended/A/mapped.v}
link_design dsp8
set clock_ports {}
set clock_names {}
foreach p [all_inputs] {
  set name [get_full_name $p]
  if {[regexp -nocase {^(clk|clock|i_clk|pclk|clk_i|sys_clk)$} $name]} {
    create_clock -name $name -period 100 $p
    lappend clock_ports $p
    lappend clock_names $name
  }
}
if {[llength $clock_ports] == 0} {create_clock -name virtual -period 100}
set data_inputs {}
foreach p [all_inputs] {
  if {[lsearch -exact $clock_names [get_full_name $p]] < 0} {lappend data_inputs $p}
}
if {[llength $data_inputs] > 0} {
  set_input_transition 0.1 $data_inputs
  set_input_delay 0 -clock [lindex [all_clocks] 0] $data_inputs
}
set_clock_transition 0.1 [all_clocks]
set_load 0.01 [all_outputs]
set_output_delay 0 -clock [lindex [all_clocks] 0] [all_outputs]
report_checks -path_delay max -group_path_count 5 -digits 6
set worst -1
# One max path per endpoint, enough group slots to cover the data endpoints.
set endpoint_limit [expr {[llength [all_registers -data_pins]] + [llength [all_outputs]]}]
if {$endpoint_limit < 1} {set endpoint_limit 1}
foreach p [find_timing_paths -path_delay max -group_path_count $endpoint_limit -endpoint_path_count 1] {
  set points [get_property $p points]
  if {[llength $points] == 0} {error "timing path has no points"}
  set endpoint_point [lindex $points end]
  set a [get_property $endpoint_point arrival]
  if {$a > $worst} {set worst $a}
}
puts "DD2_WORST_ARRIVAL_NS=$worst"
exit
