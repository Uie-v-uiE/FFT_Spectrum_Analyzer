# -*- coding: utf-8 -*-
"""对全部 bf 拍复刻 RTL ad 电路(probe 本拍 x/partner),与 probe 本拍 ad(w7)对照;
y 流错点反查:got[c] = out_c@(c-1) = ad@(c-1)(bf 拍)→ 找出真 diverge 拍。
再对 c=152 错拍做黄金对照(黄金 bf 拍 = 相位同段拍)。"""
probe = []
for line in open('sim/l1_probe.hex'):
    t2 = line.strip().split()
    if len(t2) >= 9:
        probe.append([int(v, 16) for v in t2[:9]])

def s16(v): return v - 0x10000 if v & 0x8000 else v

def rtl_add(sv):
    ext = (((sv >> 16) & 1) << 17) | sv
    sb = (ext + ((sv >> 1) & 1)) & 0x3FFFF
    sat = ((sb >> 17) & 1) ^ ((sb >> 16) & 1)
    if sat:
        return (0x8000 if (sb >> 17) & 1 else 0x7FFF), True
    return (sb >> 1) & 0xFFFF, False

bad_ad = []
for c in range(len(probe)):
    row = probe[c]
    p = row[8] & 0x1F
    if p < 16:
        continue  # fh 拍 ad 无意义
    xw, sfw, adw = row[0], row[3], row[7]
    s_re = (s16(xw & 0xFFFF) + s16(sfw & 0xFFFF)) & 0x1FFFF
    s_im = (s16((xw >> 16) & 0xFFFF) + s16((sfw >> 16) & 0xFFFF)) & 0x1FFFF
    ar, _ = rtl_add(s_re)
    ai, _ = rtl_add(s_im)
    if (adw & 0xFFFF) != ar or ((adw >> 16) & 0xFFFF) != ai:
        bad_ad.append((c, p, "%08X" % adw, "%04X/%04X" % (ai, ar), "%04X/%04X" % ((adw >> 16) & 0xFFFF, adw & 0xFFFF)))
print("ad 复刻 vs probe w7(本拍)不吻合:%d" % len(bad_ad))
for b in bad_ad[:10]:
    print("  c=%d p=%d ad=%s 复刻=%s" % b)

# y 流错点反查:got_lvl1[c] = out_r@c = out_c@(c-1);bf 拍 out_c = ad
got = []
for line in open('sim/got_lvl1.hex'):
    t = line.strip().split()
    if t:
        got.append(int(t[-1], 16))
for c in (153, 169):
    row = probe[c - 1]
    p = row[8] & 0x1F
    print("\ny错点 got[%d]=%08X ← out_c@%d (p=%d %s) probe_ad@%d=%08X" %
          (c, got[c], c - 1, p, "bf" if p >= 16 else "fh", c - 1, row[7]))
    if p >= 16:
        xw, sfw = row[0], row[3]
        s_re = (s16(xw & 0xFFFF) + s16(sfw & 0xFFFF)) & 0x1FFFF
        s_im = (s16((xw >> 16) & 0xFFFF) + s16((sfw >> 16) & 0xFFFF)) & 0x1FFFF
        ar, sr_ = rtl_add(s_re)
        ai, si_ = rtl_add(s_im)
        print("  复刻 ad@%d = %04X%04X (sat %d%d)  vs out_c 实测 %08X" %
              (c - 1, ai, ar, si_, sr_, got[c]))
