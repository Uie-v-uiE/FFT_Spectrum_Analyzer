# -*- coding: utf-8 -*-
"""验证 MSB 翻转假设:got_re == gold_re ^ 0x8000?got_im 与 gold 的关系?
并对 im 字段做"字段错位"搜索:got_im 是否 = gold_re/gold_im 的移位/位段?"""
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
def fields(v): return v & 0xFFFF, (v >> 16) & 0xFFFF

K = -1
n = xor_re = plain_re = other_re = 0
im_pl = []   # (j, gold_im, got_im, gold_re, got_re)
for j in range(len(gold)):
    gi = j + K
    if not (0 <= gi < len(got)): continue
    if gold[j] == 0 or got[gi] == 0: continue
    g = got[gi]; d = gold[j]
    gre, gim = fields(g); dre, dim = fields(d)
    n += 1
    if gre == (dre ^ 0x8000): xor_re += 1
    elif gre == dre:          plain_re += 1
    else:                     other_re += 1; im_pl.append((j, dre, gre))
print("n=%d  re=XOR0x8000:%d  re=plain:%d  other:%d" % (n, xor_re, plain_re, other_re))
print("other points:", im_pl[:20])

# XOR 翻转点与 plain 点的 j 分布(找分段规律)
xor_js, plain_js = [], []
for j in range(len(gold)):
    gi = j + K
    if not (0 <= gi < len(got)) or gold[j] == 0 or got[gi] == 0: continue
    gre, _ = fields(got[gi]); dre, _ = fields(gold[j])
    (plain_js if gre == dre else xor_js if gre == (dre ^ 0x8000) else plain_js).append(j)
def runs(lst):
    if not lst: return []
    out = []; s = lst[0]; p = lst[0]
    for x in lst[1:]:
        if x != p + 1: out.append((s, p)); s = x
        p = x
    out.append((s, p)); return out
print("plain(未翻转)runs:", runs(plain_js))
print("xor(翻转)runs:", runs(xor_js))
print("plain mod 32:", sorted(set(j % 32 for j in plain_js)))
print("plain mod 16:", sorted(set(j % 16 for j in plain_js)))
