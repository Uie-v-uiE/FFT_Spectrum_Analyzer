# -*- coding: utf-8 -*-
"""黄金重放逐拍中间量 ↔ RTL l1_probe.hex 逐字段对拍。
RTL probe 行 = L1 第 c 个 y_valid 拍的沿前组合值:x raw diff srfront srin fr y ad ctrl
黄金第 j 拍 step() 的组合读/算 ↔ probe 行 c = j + K(K=-1 包络)。
对每字段统计 mismatch,并列出首个 diverge 明细。"""
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
l1info = []      # (p, fh_now, x, raw_f, diff_f, sr_f, sr_wr, out)
srwr = []
for t in range(DELAY + len(seq)):
    adv = 1 if t >= DELAY else 0
    idx = t - DELAY
    x_new = seq[idx] if 0 <= idx < len(seq) else (0, 0)
    feed = x_new if adv else (0, 0)
    newprev = list(prev)
    for li, lv in enumerate(levels):
        x_in = feed
        y = lv.step(feed, adv)
        if li == 1 and adv:
            l1info.append((lv.p - 1 if adv else lv.p, (lv.p - 1) % 32 < 16, x_in,
                           lv.raw_pipe.front, lv.diff_pipe.front,
                           lv.sr.front if lv.sr else None, None, y))
            srwr.append(lv.sr_wr_log[-1] if lv.sr_wr_log else None)
        newprev[li] = y if adv else prev[li]
        feed = prev[li]
    prev = newprev
    if adv:
        for li in range(M):
            gold_streams[li].append(prev[li])

gold = gold_streams[1]
print("gold len=%d l1info=%d" % (len(gold), len(l1info)))

probe = []
for line in open('sim/l1_probe.hex'):
    t2 = line.strip().split()
    if len(t2) >= 9:
        probe.append([int(v, 16) for v in t2[:9]])
print("probe lines=%d" % len(probe))

K = -1
def pack(re, im): return ((im & 0xFFFF) << 16) | (re & 0xFFFF)
def fields(v): return v & 0xFFFF, (v >> 16) & 0xFFFF

# 字段对拍:x(w0) raw(w1) diff(w2) srfront(w3) srin(w4) y(w6) ad(w7)
names = ["x", "raw_f", "diff_f", "sr_front", "sr_in", "fr", "y", "ad"]
mis = {n2: [] for n2 in names}
for j in range(256):
    c = j + K
    if not (0 <= c < len(probe)):
        continue
    p_post, fh_now, x_g, raw_g, diff_g, srf_g, _, out_g = l1info[j]
    # 黄金 sr_wr:该拍 push 的值 = fh_sel(早3拍fh) ? raw_f : diff_f —— 从模型日志取
    wr_g = srwr[j] if srwr[j] is not None else (0, 0)
    row = probe[c]
    w0, w1, w2, w3, w4, w5, w6, w7, w8 = row
    rt_p = w8 & 0x1F
    rt_fhsel = (w8 >> 5) & 1
    rt_fhnow = (w8 >> 6) & 1
    g_p = p_post          # probe 抓的是沿前 p = 本拍使用值;黄金 p_post = 自增后 → 黄金本拍 p = p_post-1? 
    # 黄金 l1info 的 p 是 step 后的 lv.p;step 内使用 p 前值 = (p_post-1) mod R? 模型 p 自增在末尾
    # 用 fh_now 字段校验相位一致性即可
    cmp_pairs = [
        ("x", w0, pack(x_g[0], x_g[1])),
        ("raw_f", w1, pack(raw_g[0], raw_g[1])),
        ("diff_f", w2, pack(diff_g[0], diff_g[1])),
        ("sr_front", w3, pack(srf_g[0], srf_g[1])),
        ("sr_in", w4, pack(wr_g[0], wr_g[1])),
        ("y", w6, pack(out_g[0], out_g[1])),
    ]
    for n2, rv, gv in cmp_pairs:
        if rv != (gv & 0xFFFFFFFF):
            mis[n2].append((j, c, gv, rv, rt_p, rt_fhnow))
    # ad 只在 bf 拍有意义(fh 拍 out=sr_f,ad 不输出)
    if not fh_now:
        ad_g = pack(out_g[0], out_g[1])     # out = add_out
        if w7 != ad_g:
            mis["ad"].append((j, c, ad_g, w7, rt_p, rt_fhnow))

print("\n字段 mismatch 计数(共 %d 拍对齐):" % min(len(probe), 256 + K))
for n2 in names:
    v = mis[n2]
    print("  %-9s %3d  %s" % (n2, len(v), v[:6]))

# 相位一致性:黄金 fh_now vs RTL fh_now
phm = []
for j in range(256):
    c = j + K
    if not (0 <= c < len(probe)):
        continue
    p_post, fh_now = l1info[j][0], l1info[j][1]
    if ((probe[c][8] >> 6) & 1) != (1 if fh_now else 0):
        phm.append((j, c, l1info[j][0], probe[c][8] & 0x1F, probe[c][8]))
print("\n相位 mismatch:%d %s" % (len(phm), phm[:8]))
