# -*- coding: utf-8 -*-
"""re/im 分字段互相关:量化 got 流与黄金流的 re/im 相位不对称。
got: sim/got_lvl1.hex(32 位打包 {im16,re16});gold: sim/gold_5fccc31_lvl1.hex
对每个 shift k 统计:全 32 位匹配数 / 仅 re 匹配 / 仅 im 匹配。
"""
import sys

def load(p, n):
    vals = []
    for line in open(p):
        t = line.strip().split()
        if not t:
            continue
        vals.append(int(t[-1], 16))
    return vals[:n]

def s16(v): return v - 0x10000 if v & 0x8000 else v

got = load('sim/got_lvl1.hex', 256)
gold = load('sim/gold_5fccc31_lvl1.hex', 256)
print("got lines used=%d  gold lines used=%d" % (len(got), len(gold)))

def fields(v):
    return v & 0xFFFF, (v >> 16) & 0xFFFF   # re16, im16

# 掩码模式:全 32 / 仅 re / 仅 im
best = {'full': (0, None), 're': (0, None), 'im': (0, None)}
print("shift | full | re_only | im_only   (match counts out of 256)")
for k in range(-10, 11):
    cf = cr = ci = 0
    for j in range(256):
        gi = j + k
        if not (0 <= gi < len(got)):
            continue
        g = got[gi]; d = gold[j]
        gre, gim = fields(g); dre, dim = fields(d)
        mf = (g == d); mr = (gre == dre); mi = (gim == dim)
        cf += mf; cr += mr; ci += mi
    print("%5d | %4d | %7d | %7d" % (k, cf, cr, ci))
    if cf > best['full'][0]: best['full'] = (cf, k)
    if cr > best['re'][0]: best['re'] = (cr, k)
    if ci > best['im'][0]: best['im'] = (ci, k)
print("best full=%d@%d  re=%d@%d  im=%d@%d" %
      (best['full'][0], best['full'][1], best['re'][0], best['re'][1],
       best['im'][0], best['im'][1]))
