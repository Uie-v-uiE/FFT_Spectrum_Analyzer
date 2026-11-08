# LEARNING — FFT Accelerator: Architecture Deep Dive & Knowledge Guide

This document explains the architecture, the "why" behind every design decision, and the domain knowledge needed to understand and extend this project.

---

## 1. FFT Fundamentals

### 1.1 What is the DFT?

The Discrete Fourier Transform converts N time-domain samples into N frequency-domain bins:

```
X[k] = Σ(n=0..N-1) x[n] · e^(-j2πkn/N)
```

Direct computation requires O(N²) complex multiply-adds. The FFT reduces this to O(N log N) by exploiting symmetry and periodicity of the twiddle factors e^(-j2πkn/N).

### 1.2 Why Radix-2 DIF (Decimation in Frequency)?

DIF splits the input into even/odd indexed samples at each stage:

```
X[k]     = Σ_even x[n]·W^(nk) + W^k · Σ_odd x[n]·W^(nk)
X[k+N/2] = Σ_even x[n]·W^(nk) - W^k · Σ_odd x[n]·W^(nk)
```

This produces a "butterfly": (a+b, a−b) with a twiddle multiplication on the difference path.

**Why SDF (Single-path Delay Feedback)?**
- Only ONE complex multiplier per stage (vs. radix-4 needing 3, or DIT needing separate butterflies)
- Uses shift-register feedback (SR) instead of separate FIFOs — maps to BRAM/SRL efficiently
- Natural-order input, bit-reversed output (or vice versa)
- Throughput: 1 sample/clock, fully pipelined

### 1.3 Stage structure

Each stage ℓ (0-indexed, ℓ=0 is first) processes N/2^(ℓ+1) butterflies:

```
         ┌───── SR (depth D−Lc) ─────┐
x_in ──┬─┤  (first half: store raw)   ├─┬── first half: output SR contents
       │ └── (second half: store diff)─┘ │
       │         ↓ SR_out = x delayed D  │
       └──→ BF2: (a+b, a−b) ────────────┴─→ second half: a+b output
                │
                └→ a−b → ×W → >>1 rounding → back to SR
```

- D = N/2^(ℓ+1) = butterfly half-length
- LC = twiddle multiplier pipeline latency (3 for non-trivial, 1 for trivial)
- S = D − LC = SR depth (feedback delay)
- R = N/2^ℓ = block length per stage

**Timing invariant**: any sample entering the stage takes exactly D cycles to emerge from the SR and be paired with its butterfly partner.

### 1.4 Trivial twiddle stages

The last two stages (ℓ = M−2 and M−1) have twiddle factors W = {1, −j} and W = {1}:
- Multiplying by 1 or ±j requires only wire swapping and sign inversion
- No DSP needed — pure routing
- Pipeline latency reduced to LC = 1

### 1.5 Bit-reversed output

DIF radix-2 produces output in bit-reversed natural-order. For N=8:
```
Natural order: X[0] X[1] X[2] X[3] X[4] X[5] X[6] X[7]
Bit-reversed:  X[0] X[4] X[2] X[6] X[1] X[5] X[3] X[7]
```

The `fft_reorder.v` module uses a ping-pong buffer to convert back to natural order (adds N cycles latency).

---

## 2. Fixed-Point Arithmetic

### 2.1 Why fixed-point?

FPGA DSP48E2 blocks have 27×18-bit signed multipliers with 48-bit accumulators. Fixed-point maps naturally to this hardware. Floating-point would require ~10× more LUTs and run at half the clock rate.

### 2.2 Number format

All data is signed two's complement:
- Input/Output: 16-bit (range −32768 to +32767)
- Internal inter-stage: 18-bit fields (range −131072 to +131071)
- Twiddle factors: 18-bit (2^17 quantization, range −131072 to +131071)

The FFT gain grows by 2× per stage (each butterfly can double the amplitude). With M stages, the total gain is 2^M. Each stage divides by 2 (via >>1 rounding) to prevent overflow, keeping the internal representation bounded.

### 2.3 Convergent rounding

The critical rounding function (matching the Python golden model bit-for-bit):
```
conv_round(x, s) = (x + (1 << (s-1)) - 1 + ((x >> s) & 1)) >> s
```

This is "round half to even" (banker's rounding), which avoids DC bias accumulation across stages. The RTL implements this as:
```
sb = sign_extend(x) + x[s]     // add convergent bit
y   = sb[s+1 : s]              // shift right by s
```

### 2.4 Why 18-bit internal?

This was the hardest-won lesson (21 rounds of debugging). The diff-path output after twiddle multiply and >>18 shift has values up to ±131071 (18-bit range). Using 16 bits caused wraparound that corrupted the entire downstream.

**The proof that 18 bits suffices:**
- Input x: 16-bit (±32767)
- Partner (from SR): 18-bit (±131071)
- d = partner − x: 19-bit (±196607)
- After twiddle (|W| ≤ 2^17) and >>18: ±262142 → saturates to 18-bit
- After >>1 rounding: ±131071 → fits exactly in 18 bits
- Cascade bound: |SR| ≤ 2·131071 × 131071 / 2^18 + 1 ≈ 131071 → 18-bit is the fixed point

### 2.5 Saturation

The add path (a+b) can overflow 16 bits when both inputs are near full-scale. The RTL detects overflow via the top 4 bits of the 20-bit intermediate `sb` and clamps to ±32767/−32768.

---

## 3. DSP48E2 Complex Multiplication

### 3.1 Naive vs. Gaussian

A naive complex multiply (a+bi)(c+di) = (ac−bd) + (ad+bc)i needs 4 multipliers. The Gaussian (Karatsuba-like) approach uses 3:

```
k1 = br × (ar + ai)     // DSP pre-adder: A+D
k2 = ai × (br + bi)     // DSP pre-adder: B+D  
k3 = bi × (ar − ai)     // DSP pre-adder: A−D

re = k1 − k2 = br·ar + br·ai − ai·br − ai·bi = ar·br − ai·bi  ✓
im = k2 + k3 = ai·br + ai·bi + bi·ar − bi·ai = ai·br + bi·ar  ✓
```

### 3.2 Pipeline stages

Each DSP48E2 has: A1/B1 register → A2/B2 register → M register → P register. The 3-stage pipeline (Lc=3) maps:
- Stage 1: input registers (ar1, ai1, br1, bi1)
- Stage 2: pre-add and multiply (k1, k2, k3)
- Stage 3: sum (sre = k1−k2, sim = k2+k3) + convergent rounding bias

The twiddle factor ROM address is pipelined to match, so the correct W arrives at the same clock as the correct d value.

### 3.3 Twiddle factor ROM

Twiddle factors are computed at N=4096 resolution and stored as 18-bit signed values in `tw_L{level}.mem`. The "level prefix reuse" trick: stage ℓ of an N=2^M FFT uses the same twiddle factors as stage ℓ+(12−M) of the N=4096 FFT, so only one set of ROMs is needed for all FFT sizes.

---

## 4. AXI4-Stream Interface

### 4.1 Slave (input)

```
s_axis_tdata[31:0] — {im[15:0], re[15:0]}
s_axis_tvalid      — data valid
s_axis_tready      — output (tied to m_axis_tready, no internal buffering)
```

No TUSER on input. Frame boundaries are detected internally by sample counting.

### 4.2 Master (output)

```
m_axis_tdata[31:0] — {im[15:0], re[15:0]}
m_axis_tvalid      — data valid (gated by warmup counter)
m_axis_tuser       — frame first sample
m_axis_tlast       — frame last sample
m_axis_tready      — input from downstream
```

The `warmup` counter suppresses output until the first N samples have fully propagated (FIRST_VALID = 3N−1+1 in the bit-reversed output stream).

### 4.3 Backpressure

`en = s_axis_tvalid & m_axis_tready` is the global clock enable. When either side stalls, ALL pipeline registers freeze (no data loss, no bubble insertion). This is verified by the stall-invariance test in the golden model.

---

## 5. Board-Level Integration

### 5.1 Clock architecture

```
200 MHz differential (T24/T23) → IBUFDS → (optional MMCM) → 100 MHz logic clock
```

The synthesis target is 333 MHz (OOC), but the board demo runs at 200 MHz direct from the differential input for simplicity. Timing at 200 MHz has +2.250 ns slack.

### 5.2 Demo architecture

```
ROM (64-word dual-tone frame) → FFT (N=64) → Peak detector → LED[2:0]
                                                      ↓
                                               Activity LED[3]
```

The ROM contains a 64-point frame with sinusoids at bins 5 and 20. After bit-reversal, these appear at output indices 10 and 40. The peak detector scans for max |I|+|Q| and displays the index on LEDs.

### 5.3 Reset strategy

Reset is released only after:
1. MMCM reports LOCKED
2. An additional 128-cycle counter expires

This ensures all logic starts from a clean state with a stable clock.

---

## 6. Debugging Lessons Learned

### 6.1 The 21-round I-08 saga

The FFT worked in simulation (bit-exact vs Python model) but had residual errors on certain input patterns. The debugging history covers:

- **Rounds 1-10**: Assumed the bug was in the RTL (rounding, SR addressing, X-propagation)
- **Rounds 11-15**: Discovered the SR bit-width issue (18-bit required)
- **Rounds 16-19**: Found the golden model itself had issues (self-consistency)
- **Round 20**: A "fix" was actually circular verification (golden model was RTL's mirror)
- **Round 21**: An independent audit found the REAL root cause: phase compensation missing at each stage

**Key lesson**: Always verify your reference model against an independent standard (numpy), not just against the RTL. A model that agrees with broken RTL is not evidence of correctness.

### 6.2 Golden model pitfalls

- The golden model must be **independently derived** (from the algorithm definition, not from the RTL)
- The golden model's timing model must match the RTL's **register-by-register** behavior, not just functionally
- Any "correction" to the golden model to match RTL behavior should be treated as a red flag

### 6.3 ILA debugging methodology

- Use `mark_debug` attributes in RTL, then netlist-insert ILA after synthesis
- Set trigger on a "signature" event (e.g., first output byte, state transition)
- Export via `write_hw_ila_data` — the CSV is actually a ZIP containing waveform.vcd
- Probe deep hierarchical signals using `-hierarchical` search and full paths

---

## 7. Extending This Project

### Adding a new FFT size

1. Add the size to `gen_all_mem()` in `golden/fft_model.py`
2. Regenerate twiddle ROMs and test vectors
3. The RTL is parameterized — just change M at instantiation

### Changing data width

The internal width (18-bit) is hardcoded as `SW` in `fft_stage.v`. Changing it requires:
1. Verify the fixed-point cascade bound still holds
2. Update the saturation logic width
3. Regenerate the golden model with matching precision

### Adding windowing (Hanning, Hamming, etc.)

Insert a window multiplier between input and the FFT. This reduces spectral leakage for non-coherent sampling. The window coefficients can share the twiddle ROM infrastructure.

---

## 8. Further Reading

- *Digital Signal Processing Using MATLAB* — Ingle & Proakis (FFT theory)
- *VLSI Digital Signal Processing Systems* — Parhi (SDF architecture, Ch. 15)
- Xilinx PG150 — DSP48E2 User Guide (pre-adder, pipeline stages)
- Xilinx UG908 — Vivado Debug (ILA insertion flow)
- *Floating to Fixed Point Conversion* — Xilinx WP486 (fixed-point analysis)
