# FPGA FFT Spectrum Analyzer

Radix-2 SDF (Single-path Delay Feedback) pipeline FFT processor for Kintex UltraScale+ (RK-XCKU5P-F), with board-level spectrum demo.

[![Verification](https://img.shields.io/badge/verification-bit--exact-brightgreen)]() [![Timing](https://img.shields.io/badge/timing-333MHz%20closed-blue)]() [![Board](https://img.shields.io/badge/board-KU5P%20verified-orange)]()

## What this does

A parameterized FFT engine (N = 64 to 4096 points) that processes complex I/Q samples through a radix-2 SDF pipeline, producing bit-reversed frequency-domain output. The board-level demo feeds a dual-tone signal through the FFT and displays the peak frequency bin on LEDs — verified working on real hardware.

## Key specifications

| Spec | Value |
|---|---|
| Transform length | N = 64 / 256 / 1024 / 4096 (M = 6..12, parameterized) |
| Throughput | 1 complex sample/clock; 333 MSPS @ 333 MHz (verified) |
| Data width | Input 16-bit signed I/Q; internal 18-bit; output 16-bit |
| Architecture | DIF radix-2 SDF, natural-order input, bit-reversed output |
| Complex multiply | 3-DSP Gaussian (DSP48E2 pre-adder), convergent rounding |
| Resource | 50 DSP48E2 (2.74%), 11 RAMB36 |
| Timing | 333 MHz closed (WNS +0.027); 200 MHz board demo WNS +2.250 |
| Verification | Bit-exact vs Python golden model, L0–L5 all levels, 8/8 top-level regressions |

## Verification methodology

The golden model (`golden/fft_model.py`) is a cycle-accurate Python implementation that mirrors the RTL at the bit level — every register, every handshake, every rounding operation. The per-level audit tool (`golden/analysis/reaudit.py`) captures each pipeline stage's output stream and compares it against the model's stream, aligned by machine-learned offsets. The top-level regression runs 8 test cases (3 image types × 3 timing modes + 2 extra sizes) through the full AXI-Stream interface.

Debugging history: 21 rounds of issue tracking documented in `docs/ISSUES.md`, covering SR bit-width overflow, inter-stage phase misalignment, golden model self-consistency, and board-level bring-up.

## Project structure

```
rtl/
  fft_top.v          — AXI4-Stream top level, warmup gating, bit-reverse reorder
  fft_stage.v        — Single radix-2 SDF stage (SR + butterfly + twiddle ROM)
  fft_cmult3.v       — 3-DSP Gaussian complex multiplier (k1=br(a+ai), k2=ai(br+bi), k3=bi(ar−ai))
  fft_reorder.v      — Ping-pong natural-order reorder buffer
  fft_demo_board.v   — Board-level demo (ROM signal → FFT → peak bin → LED)
tb/
  tb_fft_top.v       — End-to-end AXI-Stream testbench (gap/NAT/sweep modes)
  tb_fft_cmult3.v    — Complex multiplier unit test (8192 cases, bit-exact)
golden/
  fft_model.py       — Cycle-accurate Python golden model (bit-exact)
  dump_lvl.py        — Per-level stream replay for cross-level audit
  gen_rtl_assets.py  — Test vector + twiddle ROM generator
  analysis/
    reaudit.py       — L0–L5 per-level audit tool
    regen_exp_v2.py  — Expected vector regeneration with numpy gate
    xcorr*.py        — Cross-correlation alignment tools
    ila_*.tcl        — ILA debug scripts
vectors/
  all_N{64..4096}_in/out.hex  — Full regression vectors (6 tests × 4 frames)
  tw_L{0..9}.mem              — Twiddle factor ROMs (N=4096, level prefix reuse)
  fft_demo_frame.mem          — Board demo dual-tone frame
constr/
  fft_demo_board.xdc          — KU5P pin constraints
scripts/
  synth_ooc.tcl               — OOC synthesis + timing
  impl_ooc_po.tcl             — Implementation + phys_opt
  build_board.tcl             — Board bitstream build
docs/
  DESIGN.md                   — Architecture and design decisions
  LOG.md                      — Chronological engineering log
  ISSUES.md                   — 21 rounds of I-08 debugging (full history)
```

## Reproduce

```bash
# Simulation (ModelSim 2020.4)
cd sim
vsim -c -do do fft_noise.do          # Single noise frame, end-to-end
vsim -c -do do fft_all.do            # Full 8-case regression

# Per-level golden model audit
python golden/dump_lvl.py            # Generate golden streams
python golden/analysis/reaudit.py    # Compare L0–L5

# Vivado synthesis + timing closure
vivado -mode batch -source scripts/impl_ooc_po.tcl

# Board bitstream (KU5P)
vivado -mode batch -source scripts/build_board.tcl
```

## Hardware results

| Metric | Value |
|---|---|
| OOC synthesis (333 MHz) | WNS +0.027, TNS 0 |
| Board implementation (200 MHz) | WNS +2.250, TNS 0 |
| DSP48E2 usage | 50 / 1824 (2.74%) |
| BRAM36 usage | 11 |
| Board verification | LED peak bin = 000 (bin 5, dual-tone) — PASS |
| Board clock | 200 MHz differential → MMCM → 100 MHz logic |

## Key design decisions

1. **18-bit internal fields (36-bit inter-stage word)**: The diff-path `conv_round(d·W, 18)` output has an 18-bit value range (proven: |y| ≤ 131071, fixed-point cascade bounded). Using 16 bits caused wraparound corruption that took 21 debugging rounds to isolate.

2. **Phase compensation (K=ℓ)**: Each pipeline stage consumes data one cycle late (inter-stage register). The PINIT counter must be offset by ℓ to align butterfly pairing with the data stream. Without this, the cascade is not a valid FFT.

3. **3-DSP Gaussian complex multiply**: Exploits DSP48E2 pre-adders to compute (a+ai)·br, ai·(br+bi), bi·(ar−ai) in 3 DSPs instead of 4, saving 25% DSP resources.

4. **Convergent rounding**: (x + 2^(s−1) − 1 + ((x>>s)&1)) >> s, matching the Python golden model bit-for-bit at every stage.
