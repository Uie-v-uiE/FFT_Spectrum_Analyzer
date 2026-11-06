# FFT 板级演示一键构建:synth + impl + bit(xcku5p-ffvb676-2-i,200 MHz)
set part xcku5p-ffvb676-2-i
set out results
file mkdir $out
create_project -force fft_board build/fft_board -part $part
add_files rtl/fft_cmult3.v
add_files rtl/fft_stage.v
add_files rtl/fft_reorder.v
add_files rtl/fft_top.v
add_files rtl/fft_demo_board.v
add_files vectors/fft_demo_frame.mem
set_property file_type {Memory File} [get_files vectors/fft_demo_frame.mem]
add_files -fileset constrs_1 constr/fft_demo_board.xdc
set_property top fft_demo_board [current_fileset]
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] != "100%"} { puts "SYNTH FAIL"; exit 1 }
launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
set bit [glob -nocomplain build/fft_board/fft_board.runs/impl_1/*.bit]
if {[llength $bit] == 0} { puts "IMPL FAIL"; exit 1 }
open_run impl_1
report_timing_summary -file $out/fft_board_timing.rpt
report_utilization -file $out/fft_board_util.rpt
puts "FFT-BOARD BIT: [lindex $bit 0]"
puts "FFT-BOARD DONE"
