# -*- coding: utf-8 -*-
"""I-08:34 位域(RTL)vs 黄金 Level(17 位全精度)的全字段对拍。"""
import sys, re
sys.path.insert(0, 'golden')
from fft_model import Level, gen_twiddles, cmult_gauss

M = 6
twl = gen_twiddles(M)

seq = []
for ln in open('vectors/only_noise_in.hex'):
    ln = ln.strip()
    if not ln: continue
    w = int(ln, 16)
    re_, im_ = w & 0xFFFF, (w >> 16) & 0xFFFF
    seq.append((re_ - 65536 if re_ >= 32768 else re_, im_ - 65536 if im_ >= 32768 else im_))
seq += [(0,0)]*64

lv0 = Level(M, 0, twl, True)
l0_comb = []
for t in range(len(seq)):
    adv = t >= 10
    x = seq[t-10] if 0 <= t-10 < len(seq) else (0,0)
    y0 = lv0.step(x if adv else (0,0), 1 if adv else 0)
    l0_comb.append(y0 if adv else (0,0))
in1 = [(0,0)] + l0_comb[:-1]
stream1 = in1[10:]

lv1g = Level(M, 1, twl, True)
g_log = []; gold = []
for x in stream1:
    pr_im_g = lv1g.sr.front[1] if lv1g.sr is not None else lv1g.raw_pipe.front[1]
    g_log.append((x[1], pr_im_g, x[1] + pr_im_g))
    gold.append(lv1g.step(x, 1))

rtl = []
pat = re.compile(r'# L1ST k=(\d+) x_im=(-?\d+) pr_im=(-?\d+) s_im=(-?\d+) simsa=(\d) out=([0-9a-f]+)')
for ln in open('sim/noise_out.log', errors='ignore'):
    m = pat.match(ln)
    if m:
        rtl.append(dict(k=int(m.group(1)), x_im=int(m.group(2)), pr_im=int(m.group(3)),
                        s_im=int(m.group(4)), sat=int(m.group(5)), out=m.group(6)))
print("RTL rows:", len(rtl))

offs = {}
for r in rtl:
    if r['x_im'] == 0 and r['s_im'] == 0: continue
    for j in range(len(g_log)):
        if g_log[j][0] == r['x_im']:
            offs[j - r['k']] = offs.get(j - r['k'], 0) + 1
            break
top = sorted(offs.items(), key=lambda kv: -kv[1])[:3]
print("x_im 对齐直方 top3:", top)
off = top[0][0]

bad = {'x_im': [], 'pr_im': [], 's_im': [], 'out': []}
for r in rtl:
    j = r['k'] + off
    if not (0 <= j < len(g_log)): continue
    for f_, gi in (('x_im', 0), ('pr_im', 1), ('s_im', 2)):
        if r[f_] != g_log[j][gi]:
            bad[f_].append((r['k'], j, r[f_], g_log[j][gi]))
    g = gold[j]
    gv = "%08x" % (((g[1]&0xFFFF)<<16)|(g[0]&0xFFFF))
    if r['out'] != gv and r['out'] != '00000000' and g != (0,0):
        bad['out'].append((r['k'], r['out'], gv))
for f_ in bad:
    print("%s 错 %d,首 3: %s" % (f_, len(bad[f_]), bad[f_][:3]))
