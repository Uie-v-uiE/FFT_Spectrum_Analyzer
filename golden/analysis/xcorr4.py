# -*- coding: utf-8 -*-
"""k=-1(包络对齐)逐点明细:193 点的 re/im 匹配位置分布 + 差值模式。"""
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
def s16(v): return v - 0x10000 if v & 0x8000 else v

K = -1
rows = []
for j in range(len(gold)):
    gi = j + K
    if not (0 <= gi < len(got)):
        continue
    if gold[j] == 0 or got[gi] == 0:
        continue
    g = got[gi]; d = gold[j]
    gre, gim = fields(g); dre, dim = fields(d)
    rows.append((j, gi, dre, gre, dim, gim))

re_ok = [r[0] for r in rows if r[2] == r[3]]
im_ok = [r[0] for r in rows if r[4] == r[5]]
print("n=%d  re_ok=%d at %s" % (len(rows), len(re_ok), re_ok))
print("im_ok=%d at %s" % (len(im_ok), im_ok))

# re 差值模式:错误点的 re 差分
from collections import Counter
dc = Counter()
for j, gi, dre, gre, dim, gim in rows:
    if dre != gre:
        dc[(s16(gre) - s16(dre))] += 1
print("\nre diff top10:", dc.most_common(10))
dc2 = Counter()
for j, gi, dre, gre, dim, gim in rows:
    if dim != gim:
        dc2[(s16(gim) - s16(dim))] += 1
print("im diff top10:", dc2.most_common(10))

# 逐点打印前 40 个(帧 0 全部)和 re 匹配段的边界
print("\nfirst 50 rows (j, gi, gold_re, got_re, gold_im, got_im):")
for r in rows[:50]:
    mark = ""
    if r[2] == r[3]: mark += "R"
    if r[4] == r[5]: mark += "I"
    print("  j=%3d gi=%3d re %6d -> %6d  im %6d -> %6d %s" %
          (r[0], r[1], s16(r[2]), s16(r[3]), s16(r[4]), s16(r[5]), mark))
