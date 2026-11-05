vlib sim/work
vmap work sim/work
vlog rtl/fft_cmult3.v rtl/fft_stage.v rtl/fft_reorder.v rtl/fft_top.v tb/tb_fft_top.v
vsim -gM_P=6  -gNAT_P=0 -gFV_START=187 work.tb_fft_top +INFILE=vectors/all_N64_in.hex  +OUTFILE=vectors/all_N64_out.hex
run -all
vsim -gM_P=6  -gNAT_P=0 -gFV_START=187 work.tb_fft_top +INFILE=vectors/all_N64_in.hex  +OUTFILE=vectors/all_N64_out.hex  +GAP=1
run -all
vsim -gM_P=6  -gNAT_P=1 -gFV_START=187 work.tb_fft_top +INFILE=vectors/all_N64_in.hex  +OUTFILE=vectors/all_N64_out.hex
run -all
vsim -gM_P=8  -gNAT_P=0 -gFV_START=761 work.tb_fft_top +INFILE=vectors/all_N256_in.hex +OUTFILE=vectors/all_N256_out.hex
run -all
vsim -gM_P=8  -gNAT_P=0 -gFV_START=761 work.tb_fft_top +INFILE=vectors/all_N256_in.hex +OUTFILE=vectors/all_N256_out.hex +GAP=1
run -all
vsim -gM_P=10 -gNAT_P=0 -gFV_START=3063 work.tb_fft_top +INFILE=vectors/all_N1024_in.hex +OUTFILE=vectors/all_N1024_out.hex
run -all
vsim -gM_P=12 -gNAT_P=0 -gFV_START=12277 work.tb_fft_top +INFILE=vectors/all_N4096_in.hex +OUTFILE=vectors/all_N4096_out.hex
run -all
quit -f
