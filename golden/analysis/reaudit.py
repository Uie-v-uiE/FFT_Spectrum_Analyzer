# -*- coding: utf-8 -*-
"""全级重对账:got_lvl{0..5}(新仿真) vs 黄金重放流(vectors/rtl_lvl*.hex)。
每级:包络对齐搜索 + 双非零/全量错误统计 + 错点明细。顶层单独对。"""
def load(p):
    vals = []
    for line in open(p):
        t = line.strip().split()
        if t:
            vals.append(int(t[-1], 16))
    return vals

# RTL 36 位流(9 hex)↔ 黄金 16 位流文件:模 2^16 字段比较
def w36(v):
    # RTL 36 位字 {im18[35:18], re18[17:0]}:模 2^16 截断两字段
    return (v & 0x3FFFF & 0xFFFF, ((v >> 18) & 0x3FFFF) & 0xFFFF)   # (re16, im16)
def wg(v):
    # 黄金 16 位文件:re = 低 16, im = 高 16(dump_lvl 打包 im<<16|re)
    return (v & 0xFFFF, (v >> 16) & 0xFFFF)

for L in range(6):
    got = load('sim/got_lvl%d.hex' % L)
    gold = load('vectors/rtl_lvl%d.hex' % L)
    best = (-1, 0, 0)
    for k in range(-6, 5):
        n = cf = 0
        for j in range(len(gold)):
            gi = j + k
            if 0 <= gi < len(got):
                n += 1
                cf += w36(got[gi]) == wg(gold[j])
        if cf > best[0]:
            best = (cf, k, n)
    cf, k, n = best
    bad = []
    for j in range(len(gold)):
        gi = j + k
        if 0 <= gi < len(got) and w36(got[gi]) != wg(gold[j]):
            bad.append((j, gi, gold[j], got[gi]))
    print("L%d: len got=%d gold=%d  best full=%d/%d @k=%d  mismatches=%d" %
          (L, len(got), len(gold), cf, n, k, len(bad)))
    for b in bad[:8]:
        print("   j=%d gi=%d gold(re=%04X im=%04X) got(re=%04X im=%04X)" %
              (b[0], b[1], b[2] & 0xFFFF, (b[2] >> 16) & 0xFFFF,
               b[3] & 0xFFFF, (b[3] >> 16) & 0xFFFF))

# 顶层
got = load('sim/got_dump.hex')
exp = load('vectors/only_noise_out.hex')
print("\ntop: len got=%d exp=%d" % (len(got), len(exp)))
bad = [j for j in range(min(len(got), len(exp))) if got[j] != exp[j]]
print("top mismatches (k=0): %d" % len(bad))
for j in bad[:8]:
    print("   j=%d exp=%08X got=%08X" % (j, exp[j], got[j]))
