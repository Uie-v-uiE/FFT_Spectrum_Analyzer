# -*- coding: utf-8 -*-
"""L1 重放分解:每拍记录 (p, fh_now, sr_f, raw_f, diff_f, out) 并与 got 对拍。
按拍相位 p 与段类型分组统计 re/im 错误模式(XOR0x8000 / ±1 / 其他)。"""
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
outstreams = [[] for _ in range(M)]
l1info = []          # L1 每拍 (p, fh_now, sr_f, raw_f, diff_f, out)

for t in range(DELAY + len(seq)):
    adv = 1 if t >= DELAY else 0
    idx = t - DELAY
    x_new = seq[idx] if 0 <= idx < len(seq) else (0, 0)
    feed = x_new if adv else (0, 0)
    newprev = list(prev)
    for li, lv in enumerate(levels):
        y = lv.step(feed, adv)
        newprev[li] = y if adv else prev[li]
        feed = prev[li]
        if li == 1 and adv:
            l1info.append((lv.p, lv.fh_hist.front[0], lv.sr.front if lv.sr else None,
                           lv.raw_pipe.front, lv.diff_pipe.front, y))
    prev = newprev
    if adv:
        for li in range(M):
            outstreams[li].append(prev[li])

gold = outstreams[1]
assert len(gold) == 256 and len(l1info) == 256

got = []
for line in open('sim/got_lvl1.hex'):
    t2 = line.strip().split()
    if t2:
        got.append(int(t2[-1], 16))
K = -1

def fields(v):
    if isinstance(v, tuple):
        return v[0] & 0xFFFF, v[1] & 0xFFFF   # 黄金元组 (re, im)
    return v & 0xFFFF, (v >> 16) & 0xFFFF
def sgn(x): return x - 0x10000 if x & 0x8000 else x

# 按 p 分组:p = l1info[j][0](黄金第 j 拍的相位)——注意重放 l1info 在 step 后采集
# lv.p 在 step 末尾已 +1,所以该拍实际相位 = (lv.p - 1) mod R;为稳妥直接用 step 前 p。
# 修正:重放里先记 lv.p 再 step?这里 l1info 在 step 后,含 self.p 已自增。改为对齐 fh_hist.front 等即可。
from collections import Counter
groups = Counter()
mis_by_type = Counter()
rows = []
for j in range(256):
    gi = j + K
    if not (0 <= gi < len(got)):
        continue
    p_post, fh_f, sr_f, raw_f, diff_f, out = l1info[j]
    p = (p_post - 1) % 32          # 该拍相位(step 后已自增)
    fh_now = 1 if p < 16 else 0
    g = got[gi]; d = gold[j]
    gre, gim = fields(g); dre, dim = fields(d)
    typ = "fh" if fh_now else "bf"
    st = ""
    if gre == dre and gim == dim: st = "OK"
    else:
        rs = "Rok" if gre == dre else ("Rxor" if gre == (dre ^ 0x8000) else "Rbad")
        is_ = "Iok" if gim == dim else ("Ixor" if gim == (dim ^ 0x8000) else "Ibad")
        st = rs + "/" + is_
        groups[(typ, rs, is_)] += 1
    rows.append((j, gi, p, typ, dre, gre, dim, gim, st))

print("错误分组 (段, re态, im态):")
for k2, v in sorted(groups.items(), key=lambda kv: -kv[1]):
    print("  %s: %d" % (k2, v))

# 按相位 p 统计
byp = Counter()
for r in rows:
    if r[8] != "OK":
        byp[(r[2], r[3])] += 1
print("\n错拍相位分布 p:(fh/bf)计数 —— 0..31")
line1 = " ".join("%d:%d" % (p, byp.get((p, 'fh'), 0)) for p in range(32))
line2 = " ".join("%d:%d" % (p, byp.get((p, 'bf'), 0)) for p in range(32))
print("fh:", line1)
print("bf:", line2)

# 逐段打印典型错点(每段前 8 个)
print("\n典型错点(前 24):")
for r in rows[:24]:
    print("  j=%3d gi=%3d p=%2d %s re %6d->%6d im %6d->%6d %s" %
          (r[0], r[1], r[2], r[3], sgn(r[4]), sgn(r[5]), sgn(r[6]), sgn(r[7]), r[8]))
# Rbad 且非 XOR 的点示例
bad2 = [r for r in rows if r[8].startswith("Rbad")][:16]
print("\nRbad(非 XOR 非 plain)示例 16 个:")
for r in bad2:
    print("  j=%3d p=%2d %s re %6d->%6d im %6d->%6d" %
          (r[0], r[2], r[3], sgn(r[4]), sgn(r[5]), sgn(r[6]), sgn(r[7])))
