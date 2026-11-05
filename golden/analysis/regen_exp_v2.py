# -*- coding: utf-8 -*-
"""v2 期望向量生成:FftCore(纯级联 = 真 DFT)。
闸门:
  all_N 系 —— 与 all_N*_out_old.hex(独立审计已 numpy 穷举裁决为真 DFT)逐位比对;
  only_noise —— 相对误差 SQNR 裁决(峰值信号容差界)。
窗口:all_N [3N-1, +22N);only_noise 3 帧 + 2 冲刷帧,窗口 [2N-1, +192)。
"""
import sys
import numpy as np
sys.path.insert(0, 'golden')
from fft_model import FftCore

def load_hex(p):
    vals = []
    for line in open(p):
        t = line.strip().split()
        if t:
            vals.append(int(t[-1], 16))
    return vals

def s16(v): return v - 65536 if v & 0x8000 else v

def run_core_frames(M, frames_list):
    """FftCore 连续流:frames_list 逐帧 + 2 帧冲刷,返回 L 流(32 位打包)"""
    N = 1 << M
    core = FftCore(M, True)
    out = []
    for fr in list(frames_list) + [None] * 2:
        for i in range(N):
            x = (0, 0) if fr is None else (int(fr[i][0]), int(fr[i][1]))
            y = core.step(x, True)
            r, im = y
            out.append(((im & 0xFFFF) << 16) | (r & 0xFFFF))
    return out

# ============ all_N 系(6 测试 × 4 帧 = 24 帧)============
NF = 24
for M in (6, 8, 10, 12):
    N = 1 << M
    in_words = load_hex('vectors/all_N%d_in.hex' % N)
    assert len(in_words) == NF * N
    frames = []
    for f in range(NF):
        seg = in_words[f * N:(f + 1) * N]
        frames.append([(s16(w & 0xFFFF), s16((w >> 16) & 0xFFFF)) for w in seg])
    stream = run_core_frames(M, frames)
    off = 3 * N - 1
    nout = (NF - 2) * N
    exp = stream[off:off + nout]
    oldf = load_hex('vectors/all_N%d_out_old.hex' % N)
    same = sum(1 for a, b in zip(exp, oldf) if a == b)
    print("[all_N%d] vs 审计确认的真DFT文件: %d/%d %s" %
          (N, same, nout, "OK" if same == nout else "*** FAIL ***"))
    assert same == nout, "与真 DFT 参考不一致!"
    with open('vectors/all_N%d_out.hex' % N, 'w') as fo:
        for w in exp:
            fo.write("%08X\n" % w)
    print("  写 vectors/all_N%d_out.hex (%d 行)" % (N, nout))

# ============ only_noise(3 帧,窗口 [N-1, +192))============
# 黄金流输出延迟 = N-1(各级 SR 深度之和);帧 f 的位倒序变换块 = [fN+N-1, fN+2N-1)
M = 6; N = 64
in_words = load_hex('vectors/only_noise_in.hex')
assert len(in_words) == 3 * N
frames = []
for f in range(3):
    seg = in_words[f * N:(f + 1) * N]
    frames.append([(s16(w & 0xFFFF), s16((w >> 16) & 0xFFFF)) for w in seg])
stream = run_core_frames(M, frames)
off = N - 1
nout = 3 * N
exp = stream[off:off + nout]

# SQNR 式裁决:exp vs numpy 真 DFT(相对误差)
def sqnr_gate(exp_words, in_words, M, nout):
    N = 1 << M
    PI = []
    for j in range(N):
        b = 0
        for mm in range(M):
            b = (b << 1) | ((j >> mm) & 1)
        PI.append(b)
    sig_p = 0.0
    err_p = 0.0
    for f in range(nout // N):
        seg = in_words[f * N:(f + 1) * N]
        re = np.array([s16(w & 0xFFFF) for w in seg], dtype=np.float64)
        im = np.array([s16((w >> 16) & 0xFFFF) for w in seg], dtype=np.float64)
        F = np.fft.fft(re + 1j * im) / float(2 ** M)     # 黄金每级 >>1,总缩放 2^-M
        for j in range(N):
            w = exp_words[f * N + j]
            yr = float(s16(w & 0xFFFF)); yi = float(s16((w >> 16) & 0xFFFF))
            ref_r = F[PI[j]].real; ref_i = F[PI[j]].imag
            sig_p += ref_r * ref_r + ref_i * ref_i
            err_p += (yr - ref_r) ** 2 + (yi - ref_i) ** 2
    sqnr = 10 * np.log10(sig_p / max(err_p, 1e-9))
    print("[only_noise] SQNR vs numpy = %.1f dB %s" % (sqnr, "OK" if sqnr > 40 else "*** FAIL ***"))
    assert sqnr > 40, "exp 不是真 DFT!"

sqnr_gate(exp, in_words, M, nout)
with open('vectors/only_noise_out.hex', 'w') as fo:
    for w in exp:
        fo.write("%08X\n" % w)
print("  写 vectors/only_noise_out.hex (%d 行)" % nout)
print("ALL EXP REGENERATED (FftCore + gates)")
