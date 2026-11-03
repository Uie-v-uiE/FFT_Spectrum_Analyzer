vlib sim/work
vmap work sim/work
vlog rtl/fft_cmult3.v tb/tb_fft_cmult3.v
vsim -c work.tb_fft_cmult3 -do "run -all; quit -f"
