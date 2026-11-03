vlib sim/work
vmap work sim/work
vlog rtl/fft_cmult3.v tb/tb_dbg_cmult.v
vsim -c work.tb_dbg_cmult -do "run -all; quit -f"
