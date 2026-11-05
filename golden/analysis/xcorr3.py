# -*- coding: utf-8 -*-
"""真匹配率:仅在 gold[j] != 0 且 got[j+k] != 0 的位置统计。
输出每个 k 的 (n_data, full, re, im),并列出 k=-1 下不匹配点的位置分布。
"""
def load(p):
    vals = []
    for line in open(p):
        t = line.strip().split()
        if not t:
            continue
        vals.append(int(t[-1], 16))
    return vals

got = load('sim/got_lvl1.hex')
gold = load('sim/gold_5fccc31_lvl1.hex')

def fields(v): return v & 0xFFFF, (v >> 16) & 0xFFFF

print("k | n | full | re | im   (double-nonzero only)")
best = None
for k in range(-6, 7):
    n = cf = cr = ci = 0
    for j in range(len(gold)):
        gi = j + k
        if not (0 <= gi < len(got)):
            continue
        if gold[j] == 0 or got[gi] == 0:
            continue
        n += 1
        g = got[gi]; d = gold[j]
        gre, gim = fields(g); dre, dim = fields(d)
        cf += g == d; cr += gre == dre; ci += gim == dim
    tag = ""
    if best is None or cf > best[1]:
        best = (k, cf, n)
        tag = "  <-- best"
    print("%2d | %3d | %4d | %3d | %3d%s" % (k, n, cf, cr, ci, tag))

# k=-1 逐点明细:按帧分段统计 + 不匹配点列表
K = best[0]
print("\nk=%d detail: per-frame stats (frame f: gold [48+64f .. 111+64f])" % K)
for f in range(3):
    lo, hi = 48 + 64 * f, 111 + 64 * f
    n = cf = cr = ci = 0
    bad = []
    for j in range(lo, hi + 1):
        gi = j + K
        if gi >= len(got) or gold[j] == 0 or got[gi] == 0:
            continue
        g = got[gi]; d = gold[j]
        gre, gim = fields(g); dre, dim = fields(d)
        n += 1; cf += g == d; cr += gre == dre; ci += gim == dim
        if g != d:
            bad.append(j)
    print("frame%d [%d..%d]: n=%d full=%d re=%d im=%d bad=%d" % (f, lo, hi, n, cf, cr, ci, len(bad)))
    print("  bad idx:", bad[:40])

# 孤立点
print("\nisolated: got[255]=%x  gold tail: gold[241..255] last nonzero search" % got[255])
for j in range(241, 256):
    if gold[j]:
        print("  gold[%d]=%x (nonzero in tail!)" % (j, gold[j]))
