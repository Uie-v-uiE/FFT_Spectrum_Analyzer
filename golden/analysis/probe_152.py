# -*- coding: utf-8 -*-
"""c=152 拍原始字段 vs 黄金对应拍(j=154,同相位 p=26)的 x/partner 对照。"""
import sys
sys.path.insert(0, 'golden')
from fft_model import Level, gen_twiddles

M = 6
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
seq += [(0, 0)] * 64

DELAY = 10
prev = [(0, 0)] * M
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
            l1info.append((p_use, x_in, lv.raw_pipe.front, lv.diff_pipe.front,
                           lv.sr.front if lv.sr else None, y))
        newprev[li] = y if adv else prev[li]
        feed = prev[li]
    prev = newprev

probe = []
for line in open('sim/l1_probe.hex'):
    t2 = line.strip().split()
    if len(t2) >= 9:
        probe.append([int(v, 16) for v in t2[:9]])

def s16(v): return v - 0x10000 if v & 0x8000 else v

c = 152
row = probe[c]
print("RTL c=152: p=%d fh_now=%d fh_sel=%d xv=%d" %
      (row[8] & 0x1F, (row[8] >> 5) & 1, (row[8] >> 6) & 1, (row[8] >> 7) & 1))
print("  x      = %08X  (re=%d im=%d)" % (row[0], s16(row[0] & 0xFFFF), s16((row[0] >> 16) & 0xFFFF)))
print("  raw_f  = %08X" % row[1])
print("  diff_f = %08X" % row[2])
print("  sr_frnt= %08X  (re=%d im=%d)" % (row[3], s16(row[3] & 0xFFFF), s16((row[3] >> 16) & 0xFFFF)))
print("  sr_in  = %08X" % row[4])
print("  fr     = %08X" % row[5])
print("  y      = %08X" % row[6])
print("  ad     = %08X" % row[7])

# 黄金侧:找黄金 p=26 的拍(相位对齐):黄金 p@j = j mod 32 → j = 154, 186, 218, 122, 90, 58, 26
for j in (154, 186, 122, 90):
    r = l1info[j]
    print("黄金 j=%d p=%d: x=(%d,%d) sr_f=(%d,%d) raw=(%d,%d) diff=(%d,%d) out=(%d,%d)" %
          (j, r[0] % 32, r[1][0], r[1][1], r[4][0], r[4][1],
           r[2][0], r[2][1], r[3][0], r[3][1], r[5][0], r[5][1]))

# RTL 相邻拍 x 序列(验证 x 流:RTL x@c ↔ 黄金 x@j=c+2)
print("\nRTL x@c=150..156 vs 黄金 x@j=c+2:")
for cc in range(150, 157):
    rr = probe[cc]
    print("  c=%d p=%2d x=%08X | 黄金 j=%d x=(%d,%d) %s" %
          (cc, rr[8] & 0x1F, rr[0], cc + 2,
           l1info[cc + 2][1][0], l1info[cc + 2][1][1],
           "OK" if rr[0] == ((l1info[cc + 2][1][1] & 0xFFFF) << 16 | (l1info[cc + 2][1][0] & 0xFFFF)) else "XX"))
