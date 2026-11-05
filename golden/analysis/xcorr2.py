# -*- coding: utf-8 -*-
"""不等长全窗口互相关:got(387) vs gold(256),re/im 分字段。
另统计两流零值分布与首/尾非零位置。
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
print("len got=%d gold=%d" % (len(got), len(gold)))
for nm, a in (("got", got), ("gold", gold)):
    z = [i for i, v in enumerate(a) if v == 0]
    nz = [i for i, v in enumerate(a) if v != 0]
    print("%s: zeros=%d first_nonzero=%s last_nonzero=%s" %
          (nm, len(z), nz[0] if nz else None, nz[-1] if nz else None))
    # 零值段打印
    segs = []
    if z:
        s = z[0]; p = z[0]
        for i in z[1:]:
            if i != p + 1:
                segs.append((s, p)); s = i
            p = i
        segs.append((s, p))
        print("  zero segs:", segs[:10])

def fields(v): return v & 0xFFFF, (v >> 16) & 0xFFFF

print("shift | full | re | im  (overlap-normalized)")
res = []
for k in range(-140, 141):
    cf = cr = ci = cn = 0
    for j in range(len(gold)):
        gi = j + k
        if 0 <= gi < len(got):
            cn += 1
            g = got[gi]; d = gold[j]
            gre, gim = fields(g); dre, dim = fields(d)
            cf += g == d; cr += gre == dre; ci += gim == dim
    res.append((k, cf, cr, ci, cn))
# 只打印局部峰值区
for k, cf, cr, ci, cn in res:
    if cf + cr + ci > 90 and cf < 250:
        print("%5d | %4d | %4d | %4d  (n=%d)" % (k, cf, cr, ci, cn))
bf = max(res, key=lambda r: r[1]); br = max(res, key=lambda r: r[2]); bi = max(res, key=lambda r: r[3])
print("best full=%d@%d  re=%d@%d  im=%d@%d" % (bf[1], bf[0], br[2], br[0], bi[3], bi[0]))
