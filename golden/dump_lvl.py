#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 RTL 的节拍重放模型:输入延迟 9 拍(复位期)、级间 1 拍寄存。
导出每级"寄存后输出"流(第 k 个有效输出 = RTL TB 的第 k 个采集字),逐索引对账。"""
import sys
sys.path.insert(0, '.')
from fft_model import Level, gen_twiddles, gen_frames

M = 6
N = 1 << M
tw = gen_twiddles(M)
levels = [Level(M, l, tw, True) for l in range(M)]

# 与 fft_noise.do 完全一致:直接读仿真实际输入向量(tdata={im,re})
seq = []
for ln in open('../vectors/only_noise_in.hex'):
    ln = ln.strip()
    if not ln:
        continue
    w = int(ln, 16)
    re, im = w & 0xFFFF, (w >> 16) & 0xFFFF
    seq.append((re - 65536 if re >= 32768 else re, im - 65536 if im >= 32768 else im))
seq += [(0, 0)] * N                            # 冲刷

DELAY = 10                                      # 复位期拍数(首个输入在周期 9)
prev = [(0, 0)] * M                            # 各级"寄存后输出"(级间 1 拍)
outstreams = [[] for _ in range(M)]

for t in range(DELAY + len(seq)):  # 冲刷帧已含在 seq 尾部
    adv = 1 if t >= DELAY else 0
    idx = t - DELAY
    x_new = seq[idx] if 0 <= idx < len(seq) else (0, 0)
    feed = x_new if adv else (0, 0)            # 级 0 组合直连 s_axis(RTL 无输入寄存)
    newprev = list(prev)
    for li, lv in enumerate(levels):
        y = lv.step(feed, adv)                 # 本拍组合结果(out_c)
        newprev[li] = y if adv else prev[li]   # 级间寄存(stall 冻结)
        feed = prev[li]                        # 下一级看上一拍的寄存输出
    prev = newprev
    if adv:
        if prev[0] != (0,0) and len(outstreams[0]) >= 32 and len(outstreams[0]) <= 34:
            lv0 = levels[0]
            print("DBG t=%d k=%d p=%d fh=%d srfront=%s raw_f=%s out=%s" % (
                t, len(outstreams[0]), lv0.p, lv0.fh_hist.front[0],
                lv0.sr.front if lv0.sr is not None else None,
                lv0.raw_pipe.front, prev[0]))
        for li in range(M):
            outstreams[li].append(prev[li])  # 第 k 个有效输出 ↔ TB 第 k 个采集字

lv = levels[1]
with open("../vectors/exp1_sr.hex", "w") as fo:
    for rd_v, wr_v in zip(lv.sr_rd_log, lv.sr_wr_log):
        fo.write(("%08X %08X" + chr(10)) % ((wr_v[1] & 0xFFFF) << 16 | (wr_v[0] & 0xFFFF),
                                            (rd_v[1] & 0xFFFF) << 16 | (rd_v[0] & 0xFFFF)))
for li in range(M):
    with open("../vectors/rtl_lvl%d.hex" % li, "w") as fo:
        for re, im in outstreams[li]:
            fo.write(("%04X%04X" + chr(10)) % (im & 0xFFFF, re & 0xFFFF))
print("rtl-timed per-level streams:", [len(v) for v in outstreams])
