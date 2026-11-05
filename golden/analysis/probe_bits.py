# -*- coding: utf-8 -*-
"""两错点位级复刻:对 RTL c=153(bf,im XOR)与 c=168(fh,sr_front 错读)
用 probe 信号逐位复刻 RTL 电路,与黄金期望对照,锁定 diverge 步骤。"""
import sys
sys.path.insert(0, 'golden')
from fft_model import Level, gen_twiddles, conv_round, cmult_gauss

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
seq += [(0, 0)] * N if False else [(0, 0)] * 64

DELAY = 10
prev = [(0, 0)] * M
l1info = []
srwr = []
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
            # 本拍 diff 路 y(bf 拍):从模型内重算——直接复制 step 逻辑取 y
            l1info.append((p_use, x_in, lv.raw_pipe.front, lv.diff_pipe.front,
                           lv.sr.front if lv.sr else None, y))
            srwr.append(lv.sr_wr_log[-1] if lv.sr_wr_log else None)
        newprev[li] = y if adv else prev[li]
        feed = prev[li]
    prev = newprev

probe = []
for line in open('sim/l1_probe.hex'):
    t2 = line.strip().split()
    if len(t2) >= 9:
        probe.append([int(v, 16) for v in t2[:9]])

def s16(v): return v - 0x10000 if v & 0x8000 else v
def s17(v): return v - 0x20000 if v & 0x10000 else v
def pack(re, im): return ((im & 0xFFFF) << 16) | (re & 0xFFFF)

# ---- 黄金侧:错点拍期望 ----
# 错点 A:黄金 j=154(bf):out = add_out = 0x12721F3E;RTL y@153 = 0x92721F3E
# 错点 B:黄金 j=170(fh):out = sr_f = 0xC9D767AD;RTL y@169 = 0xFAD3F16B
# sr_in 错:黄金 srwr[j?] ↔ RTL c=155:RTL 写 0xFAD3F16B,黄金写 0xC9D767AD
# 黄金 srwr[j] = diff_pipe.front@j = y_diff@(j-3)(bf 拍 y_diff = conv_round(cmult(d,W),18))

# 黄金 j=157 的写入应 = y_diff@154。重算黄金 y_diff@154:
lv1 = levels[1]
j = 154
# 重放取 d@154 与 W@154:重新单步重放太重——直接用黄金日志:diff_pipe 内容未记录。
# 改为:重放一遍记录 bf 拍 (d_re,d_im,tw) —— 用 lv.step 的中间量不可见,自行复刻 bf 拍组合:
# d = partner - x;partner = sr_f@bf 拍 = l1info[154][4];x = l1info[154][1]
p154, x154, raw154, diff154, srf154, out154 = l1info[154]
d_re = srf154[0] - x154[0]
d_im = srf154[1] - x154[1]
jj = p154 % 32 - 16
c_q, s_q = tw[1][jj]
y_re_g = conv_round(cmult_gauss(d_re, d_im, c_q, s_q)[0], 18)
y_im_g = conv_round(cmult_gauss(d_re, d_im, c_q, s_q)[1], 18)
print("黄金 j=154 bf: d=(%d,%d) j=%d W=(%d,%d) y_diff=(%d,%d) -> srwr@157" %
      (d_re, d_im, jj, c_q, s_q, y_re_g, y_im_g))
print("  srwr@154+3 = %s (期望 C9D767AD = %d,%d)" %
      (srwr[157], s16(0x67AD), s16(0xC9D7)))

# ---- RTL c=155 的 sr_in 复刻:diff_f@155 = cmult y@155 = conv_round(d@152 · W@152, 18) 截16 ----
# RTL d@152 = partner@152 - x@152(都是 L1 组合)—— probe 有 sr_front(c) 与 x(c)
# RTL x 对齐:RTL x@c ↔ 黄金 l1info x@j = c+2(x K=-2)
c = 155
p_rtl = probe[c][8] & 0x1F
x_r = probe[c][0]; sf_r = probe[c][3]
xr_re, xr_im = x_r & 0xFFFF, (x_r >> 16) & 0xFFFF
pr_re, pr_im = sf_r & 0xFFFF, (sf_r >> 16) & 0xFFFF
d_re_r = s16(pr_re) - s16(xr_re)
d_im_r = s16(pr_im) - s16(xr_im)
jj_r = p_rtl - 16
c_q2, s_q2 = tw[1][jj_r]
k = cmult_gauss(d_re_r, d_im_r, c_q2, s_q2)
y155 = (conv_round(k[0], 18), conv_round(k[1], 18))
print("\nRTL c=155: p=%d j=%d d=(%d,%d) W=(%d,%d) cmult_y=(%d,%d) 截16=(%d,%d)" %
      (p_rtl, jj_r, d_re_r, d_im_r, c_q2, s_q2, y155[0], y155[1],
       y155[0] & 0xFFFF, y155[1] & 0xFFFF))
print("  RTL 实写 sr_in@155 = %08X" % probe[c][4])

# 黄金 j=157 对齐拍(黄金 p@157 = 29?):黄金 srwr[157] vs y_diff@154
print("\n对照:黄金 j=157 写入 = %s;RTL c=155 写入 = %08X" %
      (srwr[157], probe[c][4]))

# ---- 错点 A:c=153 bf 拍 ad_im 复刻 ----
cA = 153
rowA = probe[cA]
pA = rowA[8] & 0x1F
xw = rowA[0]; sfw = rowA[3]
adw = rowA[7]
xr_re, xr_im = xw & 0xFFFF, (xw >> 16) & 0xFFFF
pr_re, pr_im = sfw & 0xFFFF, (sfw >> 16) & 0xFFFF
# 17 位符号扩展后相加(17 位截断)
s_re = (s16(xr_re) + s16(pr_re)) & 0x1FFFF
s_im = (s16(xr_im) + s16(pr_im)) & 0x1FFFF
def rtl_add(s17v):
    ext = ((s17v >> 16) & 1) << 17 | s17v
    sb = (ext + ((s17v >> 1) & 1)) & 0x3FFFF
    sat = ((sb >> 17) & 1) ^ ((sb >> 16) & 1)
    if sat:
        return 0x8000 if (sb >> 17) & 1 else 0x7FFF, True
    return (sb >> 1) & 0xFFFF, False
ad_re_r, satr = rtl_add(s_re)
ad_im_r, sati = rtl_add(s_im)
print("\nRTL c=153 bf: p=%d x=(%d,%d) partner=(%d,%d)" %
      (pA, s16(xr_re), s16(xr_im), s16(pr_re), s16(pr_im)))
print("  s_re=%d s_im=%d -> ad=(%d,%d) sat=(%d,%d)  实测 ad=%08X 期望(gold j=154) 12721F3E" %
      (s17(s_re), s17(s_im), s17(ad_re_r), s17(ad_im_r), satr, sati, adw))
# 黄金语义:sat16(conv_round(s,1))
g_re = max(-32768, min(32767, conv_round(s17(s_re), 1)))
g_im = max(-32768, min(32767, conv_round(s17(s_im), 1)))
print("  黄金 add=(%d,%d)  RTL add=(%d,%d)" % (g_re, g_im, s17(ad_re_r), s17(ad_im_r)))
