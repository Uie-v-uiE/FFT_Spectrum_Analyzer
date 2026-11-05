# -*- coding: utf-8 -*-
"""逐字段独立对齐对拍:每字段在 K∈[-4..2] 内搜最佳匹配(以内容锚定),
报告各字段对齐 K 与对齐后 mismatch 明细。"""
import sys
sys.path.insert(0, 'golden')
from fft_model import Level, gen_twiddles

M = 6
N = 1 << M
tw = gen_twiddles(M)
levels = [Level(M, l, tw, True) for l in range(M)]

seq = []
for ln in open('vectors/only_noise_in.hex'):
    ln = ln.strip()
    if not ln:
        continue
    w = int(ln, 16)
    re, im = w & 0xFFFF, (w >> 16) & 0xFFFF
    seq.append((re - 65536 if re >= 32768 else re, im - 65536 if im >= 32768 else im))
seq += [(0, 0)] * N

DELAY = 10
prev = [(0, 0)] * M
gold_streams = [[] for _ in range(M)]
srwr = []
l1info = []
for t in range(DELAY + len(seq)):
    adv = 1 if t >= DELAY else 0
    idx = t - DELAY
    x_new = seq[idx] if 0 <= idx < len(seq) else (0, 0)
    feed = x_new if adv else (0, 0)
    newprev = list(prev)
    for li, lv in enumerate(levels):
        x_in = feed
        p_use = lv.p
        y = lv.step(feed, adv)
        if li == 1 and adv:
            l1info.append((p_use, (p_use % 32) < 16, x_in,
                           lv.raw_pipe.front, lv.diff_pipe.front,
                           lv.sr.front if lv.sr else None, y))
            srwr.append(lv.sr_wr_log[-1] if lv.sr_wr_log else None)
        newprev[li] = y if adv else prev[li]
        feed = prev[li]
    prev = newprev
    if adv:
        for li in range(M):
            gold_streams[li].append(prev[li])

probe = []
for line in open('sim/l1_probe.hex'):
    t2 = line.strip().split()
    if len(t2) >= 9:
        probe.append([int(v, 16) for v in t2[:9]])

def pack(re, im): return ((im & 0xFFFF) << 16) | (re & 0xFFFF)

# 黄金字段表(黄金第 j 个有效拍):
gf = {
    "x":        [pack(r[2][0], r[2][1]) for r in l1info],
    "raw_f":    [pack(r[3][0], r[3][1]) for r in l1info],
    "diff_f":   [pack(r[4][0], r[4][1]) for r in l1info],
    "sr_front": [pack(r[5][0], r[5][1]) for r in l1info],
    "sr_in":    [pack(r[0] and 0 or 0, 0) for r in l1info],  # 占位,下面单独填
    "y":        [pack(r[6][0], r[6][1]) for r in l1info],
}
gf["sr_in"] = [pack((v or (0, 0))[0], (v or (0, 0))[1]) for v in srwr]

# RTL 字段
rf = {
    "x":        [r[0] for r in probe],
    "raw_f":    [r[1] for r in probe],
    "diff_f":   [r[2] for r in probe],
    "sr_front": [r[3] for r in probe],
    "sr_in":    [r[4] for r in probe],
    "y":        [r[6] for r in probe],
}

print("字段独立对齐(K: rtl[c] ↔ gold[c-K];负 K = RTL 早):")
for name in ["x", "raw_f", "diff_f", "sr_front", "sr_in", "y"]:
    g = gf[name]; r = rf[name]
    best = (-1, 0)
    for k in range(-4, 3):
        cf = sum(1 for j in range(len(g)) if 0 <= j + k < len(r) and r[j + k] == g[j])
        if cf > best[0]:
            best = (cf, k)
    cf, k = best
    n = sum(1 for j in range(len(g)) if 0 <= j + k < len(r))
    bad = [(j, j + k, "%08X" % g[j], "%08X" % r[j + k]) for j in range(len(g))
           if 0 <= j + k < len(r) and r[j + k] != g[j]]
    print("  %-9s K=%2d match=%d/%d  mism=%d %s" % (name, k, cf, n, len(bad), bad[:6]))
