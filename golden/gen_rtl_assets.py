#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 RTL 资产:
1. tw_L0..L9.mem   —— N=4096 各非平凡级旋转因子表(级前缀复用:级 ℓ of N=2^M = 级 ℓ+12-M 的前缀,
   文件条目数恰为该级延迟深度 D);
2. all_N{N}_in/out.hex —— 每 N 拼接 6 种测试 × 3 帧,warm 模式(全部帧输出有效,
   供连续流 TB 使用;首帧对齐由 TB 搜索);
3. cmult_tv.hex —— 3-DSP 高斯复乘单元测试向量(与 rtl/fft_cmult3.v 逐位对拍)。
"""
import os, math, random
import numpy as np
from fft_model import (gen_twiddles, gen_frames, run_stream, pack_word,
                       DATA_W, DIN_MIN, DIN_MAX)

OUT = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))), "vectors")
os.makedirs(OUT, exist_ok=True)
TWQ = 1 << 17

# 1) 旋转因子表(N=4096,级 0..9)
MMAX = 12
tw = gen_twiddles(MMAX)
for l in range(MMAX - 2):
    with open(f"{OUT}/tw_L{l}.mem", "w") as fo:
        for c, s in tw[l]:
            fo.write(f"{(((s & 0x3FFFF) << 18) | (c & 0x3FFFF)):09X}\n")
print("tw_L0..L9.mem ok")

# 2) 拼接测试向量(warm:全部帧输出)
TESTS = ("tone", "twotone", "noise", "corner", "impulse", "dc")
NFRAMES = 4
for M in (6, 8, 10, 12):
    N = 1 << M
    frames = []
    seg = []
    t0 = 0
    for ti, test in enumerate(TESTS):
        fs = gen_frames(test, N, NFRAMES, seed=1234 + ti)
        frames += fs
        seg.append((ti, test, t0, t0 + NFRAMES))
        t0 += NFRAMES
    # 单核连续暖跑:与 RTL 的连续流一致(帧间状态延续)
    stream, _ = run_stream(M, frames, scale=True)
    # 契约:帧 0/1 为 warmup;帧 2 的输出块起点 = 2N + (N-1) = 3N-1
    off = 3 * N - 1
    with open(f"{OUT}/all_N{N}_in.hex", "w") as fi, open(f"{OUT}/all_N{N}_out.hex", "w") as fo, open(f"{OUT}/all_N{N}_info.txt", "w") as manifest:
        for fr in frames:
            for re, im in fr:
                fi.write(("%08X" + chr(10)) % pack_word(re, im, DATA_W))
        nout = (len(frames) - 2) * N                  # 帧滑窗错一格:导出帧 2..末帧(暖态)
        for yr, yi in stream[off: off + nout]:
            fo.write(("%08X" + chr(10)) % pack_word(yr, yi, DATA_W))
        manifest.write("tests: " + ", ".join(f"{ti}:{test}" for ti, test, _, _ in seg) + chr(10))
        manifest.write("total_frames %d; export = warm frames 2..3 per test" % len(frames))
print(f"all_N{N} ok: in {len(frames)*N} words, out {nout} words")

# 3) cmult 单元向量: a=diff(17bit signed), b=twiddle(18bit signed), y=conv_round(a*b,18)
def conv_round(x, s):
    q, r = divmod(x, 1 << s)
    half = 1 << (s - 1)
    if r > half or (r == half and (q & 1)):
        q += 1
    return q

rng = random.Random(42)
NCASE = 8192
with open(f"{OUT}/cmult_tv.hex", "w") as fo:
    fo.write("# each line: aaaaaaa bbbbbbb yyyyyyyy  (a:17b re/im packed? no — 见下)\n")
# 格式:每 case 3 行:a_re, a_im 打包 {im,re} 34b; b_re,b_im 打包 {im,re} 36b; y {im,re} 32b
with open(f"{OUT}/cmult_tv.hex", "w") as fo:
    for _ in range(NCASE):
        ar = rng.randint(-(1 << 16), (1 << 16) - 1)
        ai = rng.randint(-(1 << 16), (1 << 16) - 1)
        br = rng.randint(-TWQ, TWQ - 1)
        bi = rng.randint(-TWQ, TWQ - 1)
        k1 = br * (ar + ai); k2 = ai * (br + bi); k3 = bi * (ar - ai)
        pre = (k1 - k2, k2 + k3)
        y = (conv_round(pre[0], 18), conv_round(pre[1], 18))
        a_p = ((ai & 0x1FFFF) << 17) | (ar & 0x1FFFF)
        b_p = ((bi & 0x3FFFF) << 18) | (br & 0x3FFFF)
        y_p = ((y[1] & 0xFFFF) << 16) | (y[0] & 0xFFFF)
        fo.write(f"{a_p:08X} {b_p:09X} {y_p:08X}\n")
print("cmult_tv.hex ok")
