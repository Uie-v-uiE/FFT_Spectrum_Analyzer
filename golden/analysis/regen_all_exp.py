# -*- coding: utf-8 -*-
"""重生成 all_N{6,8,10,12}_out.hex:黄金 Level 链重放(级间 1 拍,与 RTL 实证一致)。
契约窗口 = 模型流下标 3N-1 起,长度 (24-2)·N。
GAP 模式:--gap sim/gap_seq.hex(TB 落盘的停拍样元号),按序列插入 adv=0 拍。
用法:python regen_all_exp.py [--gap FILE] [M ...](默认 6 8 10 12)"""
import sys
sys.path.insert(0, 'golden')
from fft_model import Level, gen_twiddles

args = sys.argv[1:]
gapfile = None
if args and args[0] == '--gap':
    gapfile = args[1]
    args = args[2:]
Ms = [int(a) for a in args] or [6, 8, 10, 12]
NF = 24                                    # 6 测试 × 4 帧

gapcnt = {}
if gapfile:
    from collections import Counter
    _lst = []
    for ln in open(gapfile):
        ln = ln.strip()
        if ln:
            _lst.append(int(ln))
    gapcnt = Counter(_lst)                 # 同一样元可连续停多拍(TB gap 连续触发)
    print("GAP: %d 条记录, %d 个停拍样元" % (len(_lst), len(gapcnt)))

for M in Ms:
    N = 1 << M
    tw = gen_twiddles(M)
    levels = [Level(M, l, tw, True) for l in range(M)]
    seq = []
    for ln in open('vectors/all_N%d_in.hex' % (1 << M)):
        ln = ln.strip()
        if not ln:
            continue
        w = int(ln, 16)
        re, im = w & 0xFFFF, (w >> 16) & 0xFFFF
        seq.append((re - 65536 if re >= 32768 else re, im - 65536 if im >= 32768 else im))
    assert len(seq) == NF * N, "in 行数 %d != %d" % (len(seq), NF * N)
    # adv 序列:输入段按 gap 集插停拍;冲刷段全 1
    adv_seq = []
    n_gap_here = 0
    for i in range(NF * N):
        g = gapcnt.get(i, 0)
        if g:
            adv_seq += [0] * g
            n_gap_here += g
        adv_seq.append(1)
    adv_seq += [1] * (3 * N)
    DELAY = 10
    prev = [(0, 0)] * M
    last = []
    k = 0
    for t in range(DELAY + len(adv_seq)):
        if t < DELAY:
            feed = (0, 0)
            adv = 0
        else:
            adv = adv_seq[t - DELAY]
            feed = seq[k] if (adv and k < len(seq)) else (0, 0)
            if adv:
                k += 1
        newprev = list(prev)
        for li, lv in enumerate(levels):
            y = lv.step(feed, adv)
            newprev[li] = y if adv else prev[li]
            feed = prev[li]
        prev = newprev
        if adv:
            last.append(prev[M - 1])
    off = 3 * N - 1
    nout = (NF - 2) * N
    assert off + nout <= len(last), "流不够长"
    with open('vectors/all_N%d_out.hex' % (1 << M), 'w') as fo:
        for i in range(nout):
            r, i2 = last[off + i]
            fo.write("%08X\n" % (((i2 & 0xFFFF) << 16) | (r & 0xFFFF)))
    print("M=%d: adv %d 拍(gap %d), 流 %d, 窗口 [%d..%d), 写 %d 行" %
          (M, len(adv_seq), n_gap_here, len(last), off, off + nout, nout))
