# OOC 实现(synth + opt + place + route)fft_top (M=6),333 MHz,布线后时序/资源报告
set part xcku5p-ffvb676-2-i
set outdir results
create_project -force fft_ooc_impl $outdir/ooc_impl_prj -part $part -in_memory
add_files rtl/fft_cmult3.v
add_files rtl/fft_stage.v
add_files rtl/fft_reorder.v
add_files rtl/fft_top.v
set_property top fft_top [current_fileset]
set_property file_type {Verilog Header} [glob rtl/*.v] -quiet
synth_design -top fft_top -mode out_of_context -flatten_hierarchy rebuilt
create_clock -period 3.000 -name clk [get_ports clk]
set_input_delay 0.2 -clock clk [all_inputs]
set_output_delay 0.2 -clock clk [all_outputs]
opt_design
place_design
route_design
report_timing_summary -file $outdir/timing_routed_m6_333.rpt
report_utilization -file $outdir/util_routed_m6_333.rpt
report_control_sets -verbose -file $outdir/ctrlsets_routed_m6_333.rpt
report_drc -file $outdir/drc_routed_m6_333.rpt
write_checkpoint -force $outdir/fft_ooc_m6_routed.dcp
puts "IMPL-M6-333 DONE"
