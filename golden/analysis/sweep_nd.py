#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""I-08 下会话首任务:镜像扫参定管深(纯 Python 秒级)。
用法: python sweep_nd.py
扫 ND(管深)× Sd(SR 深)× pinit,找 L1 非零错=0 的组合,
然后按同参数修 RTL(fft_stage.v 的 rp/f 管级数与 SR 深)。"""
import sys
sys.path.insert(0, 'golden')
from fft_model import Level, gen_twiddles, cmult_gauss

M = 6
twl = gen_twiddles(M)
def conv_r(v, s):
    return (v + (1 << (s-1)) - 1 + ((v >> s) & 1)) >> s

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
gold = ["%08x" % (((y[1]&0xFFFF)<<16)|(y[0]&0xFFFF)) for y in (lv1g.step(x,1) for x in stream1)]

def mirror_run(pinit, ND, Sd):
    R = 32; D = 16; S = Sd; HALF = 16
    tw1 = twl[1]
    p = pinit
    rp = [(0,0)]*ND; f = [0]*ND
    sr = [(0,0)]*S; wptr = 0; fr = (0,0)
    d_hist = []; tw_hist = []
    out = []
    for x in stream1:
        fh_now = p < HALF
        p_j = (p - HALF) % D
        tw_now = tw1[p_j]
        raw_f = rp[0]; fh_sel = f[0]
        d = (fr[0] - x[0], fr[1] - x[1]); s_ = (x[0]+fr[0], x[1]+fr[1])
        cr = lambda v: max(-32768, min(32767, conv_r(v, 1)))
        add_out = (cr(s_[0]), cr(s_[1]))
        n_h = len(d_hist)
        if n_h >= ND:
            din = d_hist[n_h-ND]; tq = tw_hist[n_h-ND]
            pre, pim = cmult_gauss(din[0], din[1], tq[0], tq[1])
            cm_out = (conv_r(pre, 18), conv_r(pim, 18))
        else:
            cm_out = (0, 0)
        sr_in = raw_f if fh_sel else cm_out
        out.append(fr if fh_now else add_out)
        rp = rp[1:] + [x if fh_now else (0, 0)]
        f = f[1:] + [1 if fh_now else 0]
        d_hist.append(d); tw_hist.append(tw_now)
        sr[wptr] = sr_in
        wptr = 0 if wptr == S - 1 else wptr + 1
        fr = sr[wptr]
        p = 0 if p == R - 1 else p + 1
    return out

def fd(a, b):
    for k in range(min(len(a), len(b))):
        if a[k] != b[k]: return k
    return None

if __name__ == "__main__":
    # 黄金 DLine(3) 滞后 = 3;S = D - Lc = 13;先扫 ND×Sd(Sd 可小于 S 补偿写读相位)
    for ND in (3, 4, 5):
        for Sd in (13, 12, 11, 10):
            if Sd < 1: continue
            m = mirror_run(0, ND, Sd)
            mh = ["%08x" % (((y[1]&0xFFFF)<<16)|(y[0]&0xFFFF)) for y in m]
            bad = sum(1 for k in range(min(len(mh), len(gold))) if mh[k] != gold[k] and mh[k] != '00000000' and gold[k] != '00000000')
            print("ND=%d S=%d 非零错=%d" % (ND, Sd, bad))
