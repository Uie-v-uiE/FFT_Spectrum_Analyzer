#!/usr/bin/env python3
"""导出与 RTL 对齐的 L4 输出流(18 帧 + 冲刷,周期精确)。"""
import numpy as np, sys
sys.path.insert(0, '.')
from fft_model import Level, gen_twiddles, gen_frames, conv_round, DIN_MIN, DIN_MAX

M = 6
N = 1 << M
tw = gen_twiddles(M)
levels = [Level(M, l, tw, True) for l in range(M)]
frames = []
for ti, test in enumerate(("tone", "twotone", "noise", "corner", "impulse", "dc")):
    frames += [f for f in gen_frames(test, N, 3, seed=1234 + ti)]
seq = [(int(fr[i][0]), int(fr[i][1])) for fr in frames for i in range(N)]
seq += [(0, 0)] * N  # 冲刷帧
allv = [[] for _ in range(M)]
for t, x in enumerate(seq):
    y = x
    for li, lv in enumerate(levels):
        y = lv.step(y, 1)
        allv[li].append(y)
print("MODEL L5 first 16:", [("".join("%04X%04X" % (v[1] & 0xFFFF, v[0] & 0xFFFF))) for v in allv[5][:16]])
for li in range(M):
    with open("../vectors/exp_lvl%d.hex" % li, "w") as fo:
        for re, im in allv[li]:
            fo.write(("%04X%04X" + chr(10)) % (im & 0xFFFF, re & 0xFFFF))
print("per-level dumps:", [len(v) for v in allv])
