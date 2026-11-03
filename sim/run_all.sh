#!/bin/bash
VSIM=/d/Software/ModelSim/modelsim/win64/vsim.exe
run_case() {
  local m="$1" nat="$2" gap="$3" n="$4"
  cat > sim/_case.do <<EOD
vlib sim/work
vmap work sim/work
vlog rtl/fft_cmult3.v rtl/fft_stage.v rtl/fft_reorder.v rtl/fft_top.v tb/tb_fft_top.v
vsim -gM_P=$m -gNAT_P=$nat work.tb_fft_top +INFILE=vectors/all_N${n}_in.hex +OUTFILE=vectors/all_N${n}_out.hex ${gap}
run -all
quit -f
EOD
  $VSIM -c -do sim/_case.do 2>&1 | grep -E "FFT TOP|TB FAIL"
}
run_case 6  0 ""   64
run_case 6  0 "+GAP=1" 64
run_case 6  1 ""   64
run_case 8  0 ""   256
run_case 8  0 "+GAP=1" 256
run_case 10 0 ""   1024
run_case 12 0 ""   4096
