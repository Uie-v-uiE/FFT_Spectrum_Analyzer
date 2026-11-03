vlib sim/work
vmap work sim/work
vlog rtl/fft_cmult3.v rtl/fft_stage.v rtl/fft_reorder.v rtl/fft_top.v tb/tb_fft_top.v
vsim -gM_P=12 -gNAT_P=0 work.tb_fft_top +INFILE=vectors/all_N4096_in.hex +OUTFILE=vectors/all_N4096_out.hex 
run -all
quit -f
