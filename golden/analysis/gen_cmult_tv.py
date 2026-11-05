# -*- coding: utf-8 -*-
"""重生成 cmult_tv.hex:覆盖新 d 值域(18-bit,a∈[-131071,131071]),
b 为 18-bit 旋转因子域,y = conv_round(k1-k2 / k2+k3, 18) 18-bit,打包模 2^16。
格式:每行 a_p b_p y_p(a_p={ai18,ar18} 36b;b_p={bi,br} 36b;y_p={yi16,yr16} 32b)"""
import random

TWQ = 1 << 17
def conv_round(x, s):
    q, r = divmod(x, 1 << s)
    half = 1 << (s - 1)
    if r > half or (r == half and (q & 1)):
        q += 1
    return q

rng = random.Random(42)
NCASE = 8192
AMAX = (1 << 17) - 1                       # 18-bit 有符号正上界 131071
with open('vectors/cmult_tv.hex', 'w') as fo:
    for _ in range(NCASE):
        ar = rng.randint(-AMAX, AMAX)
        ai = rng.randint(-AMAX, AMAX)
        br = rng.randint(-TWQ, TWQ - 1)
        bi = rng.randint(-TWQ, TWQ - 1)
        k1 = br * (ar + ai); k2 = ai * (br + bi); k3 = bi * (ar - ai)
        yr = conv_round(k1 - k2, 18)
        yi = conv_round(k2 + k3, 18)
        a_p = ((ai & 0x3FFFF) << 18) | (ar & 0x3FFFF)
        b_p = ((bi & 0x3FFFF) << 18) | (br & 0x3FFFF)
        y_p = ((yi & 0xFFFF) << 16) | (yr & 0xFFFF)
        fo.write("%09X %09X %08X\n" % (a_p, b_p, y_p))
print("cmult_tv.hex: %d cases, a∈[-%d,%d] (18-bit d 域)" % (NCASE, AMAX, AMAX))
