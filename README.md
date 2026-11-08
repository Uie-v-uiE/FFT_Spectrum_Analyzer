# k5p-fft-accelerator

Radix-2 SDF (Single-path Delay Feedback) pipeline FFT processor for Kintex UltraScale+ (RK-XCKU5P-F).

## Key specs

| Spec | Value |
|---|---|
| Transform length | N = 64 / 256 / 1024 / 4096 (M = 6..12, parameterized) |
| Throughput | 1 complex sample/clock; 333 MSPS @ 333 MHz (verified), 400 MHz target |
| Data width | Input 16-bit signed I/Q; internal 18-bit fields (36-bit inter-stage word); output 16-bit |
| Twiddle | 18-bit signed, 2^-17 quantization |
| Architecture | DIF radix-2 SDF, natural-order input, bit-reversed output |
| Complex multiply | 3-DSP Gaussian (pre-adder), convergent rounding |
| Interface | AXI4-Stream |
| Resource | 50 DSP48E2 (2.74%), 11 RAMB36 |

## Verification

- **Bit-exact golden model** (`golden/fft_model.py`): L0–L5 per-level trace, all 0 errors
- **Top-level regression**: 8/8 PASS (N64 gap0/gap1/NAT, N256 gap0/gap1, N1024, N4096, noise)
- **Board demo**: LED shows peak bin (dual-tone frame), verified on KU5P
- **Timing**: 333 MHz closed (WNS +0.027), 200 MHz board demo WNS +2.250

## Board demo (KU5P)

Burn `fft_demo_board.bit` via JTAG. Dual-tone frame (bins 5+20) loops through FFT.
LED[2:0] shows peak frequency bin (stable = correct). LED[3] blinks (clock alive).

## Project layout

```
rtl/          — fft_top.v, fft_stage.v, fft_cmult3.v, fft_reorder.v, fft_demo_board.v
tb/           — tb_fft_top.v (AXI-S end-to-end), tb_fft_cmult3.v (unit test)
golden/       — fft_model.py (bit-exact Python reference), dump_lvl.py (per-level replay)
golden/analysis/ — per-level audit, cross-correlation, vector regeneration tools
vectors/      — test vectors (tone/noise/corner/impulse/twotone/dc × N64..N4096) + twiddle ROMs
constr/       — XDC constraints
scripts/      — synth_ooc.tcl, impl_ooc.tcl, build_board.tcl
docs/         — DESIGN.md, LOG.md, ISSUES.md (21 rounds of debugging history)
sim/          — ModelSim .do files
```

## Reproduce

```bash
# ModelSim simulation
cd sim && vsim -c -do do fft_noise.do       # noise end-to-end
vsim -c -do do fft_all.do                    # full regression

# Per-level audit (Python)
python golden/dump_lvl.py                    # generates golden streams
python golden/analysis/reaudit.py            # L0-L5 vs RTL comparison

# Vivado synthesis + implementation
vivado -mode batch -source scripts/impl_ooc_po.tcl   # OOC + timing
vivado -mode batch -source scripts/build_board.tcl    # board bitstream
```

## Docs

- `docs/DESIGN.md` — architecture, spec, gate audit
- `docs/LOG.md` — chronology of all debugging rounds
- `docs/ISSUES.md` — 21 rounds of I-08 debugging (SR bit-width, phase compensation, etc.)
- `../docs/BRINGUP.md` — board bring-up guide (all 4 projects)
