#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
比特精确周期级模型 —— radix-2 SDF 流水线 FFT(DIF,自然序入 / 位倒序出)
=================================================================================
本模型是 RTL 的唯一真值源(路线图闸门 G2),同时是周期精确模型(G3)。

硬件约定(与 rtl/ 一致,RTL 必须逐位复现):
- tdata = {im, re},DATA_W=16 有符号;每级加法路与乘法路各 >>1 convergent 舍入;
- 旋转因子 18-bit 有符号,刻度 2^17;乘积总移位 >>18(17 刻度 + 1 级缩放),单次舍入;
- 级 ℓ(0=最粗):块长 R=N/2^ℓ,延迟深度 D=R/2,块内前半拍存数、后半拍配对;
  输出流 = [前半拍:上一块 diff·W | 后半拍:(a+b)>>1],级间自然交织、零胶合;
- 复乘流水 Lc=3(高斯 3-DSP:P@t+2,舍入寄存@t+3);平凡级(W4/W2)Lc=1;
  主延迟线 SR = D-Lc,原始数先经 Lc 深管再入 SR(两路合计恰 D 拍);
- 全局 stall:adv=0 时所有级冻结(时序不变量:相位计数与延迟线同步停);
- 复位后第一帧输出无效(延迟线初值无意义),自第 2 帧起逐位有效。
"""
import math
import numpy as np

DATA_W = 16
TW_W = 18
TW_Q = 1 << (TW_W - 1)                       # 2^17
DIN_MIN, DIN_MAX = -(1 << (DATA_W - 1)), (1 << (DATA_W - 1)) - 1

# ---------------------------------------------------------------- 舍入
def conv_round(x: int, s: int) -> int:
    """convergent(round-half-to-even)算术右移 s 位(二进制补码语义)。"""
    q, r = divmod(x, 1 << s)
    half = 1 << (s - 1)
    if r > half or (r == half and (q & 1)):
        q += 1
    return q

def rtl_round(x: int, s: int) -> int:
    """RTL 惯用式 y=(x+(1<<(s-1))-1+((x>>s)&1))>>s 的 64 位补码模拟,自检用。"""
    M64 = 1 << 64
    ax = x & (M64 - 1)
    y = (ax + (1 << (s - 1)) - 1 + ((ax >> s) & 1)) >> s
    # 还原有符号结果:y 为 (64-s) 位补码
    if y >> (63 - s) & 1:
        y -= M64 >> 0 if False else 0
    # 更稳妥:按模回卷
    ys = y & ((1 << (64 - s)) - 1)
    if ys >> (63 - s) & 1:
        ys -= 1 << (64 - s)
    return ys

# ---------------------------------------------------------------- 旋转因子
def gen_twiddles(M: int):
    """tw[l][j] = (cos_q, -sin_q),表示 W = (cos_q - j·sin_q)/2^17 = e^{-j2π·2^l·j/N}"""
    N = 1 << M
    out = []
    for l in range(M):
        D = N >> (l + 1)
        lvl = []
        for j in range(D):
            th = 2 * math.pi * ((1 << l) * j) / N   # W = e^{-jθ} = cosθ - j·sinθ
            # 钳位到 18bit 有符号:cos(0)=1 -> 2^17-1,|W|<1 严格成立(无溢出证明前提)
            c = min(int(round(math.cos(th) * TW_Q)), TW_Q - 1)
            s = max(int(round(-math.sin(th) * TW_Q)), -TW_Q)
            assert -TW_Q <= c <= TW_Q - 1 and -TW_Q <= s <= TW_Q - 1
            lvl.append((c, s))
        out.append(lvl)
    return out

def cmult_gauss(ar, ai, br, bi):
    """3-DSP 高斯复乘:k1=br·(ar+ai)[DSP预加器], k2=ai·(br+bi)[B路进位预加],
    k3=bi·(ar-ai)[DSP预加器];re=k1-k2, im=k2+k3。"""
    k1 = br * (ar + ai)
    k2 = ai * (br + bi)
    k3 = bi * (ar - ai)
    return k1 - k2, k2 + k3

def cmult_ref(ar, ai, br, bi):
    return ar * br - ai * bi, ar * bi + ai * br

# ---------------------------------------------------------------- 延迟线(精确 S 拍)
class DLine:
    """硬件移位寄存器:push 于周期 c 的值在周期 c+S 可从 front 读到。"""
    def __init__(self, S, fill=(0, 0)):
        self.S = S
        self.buf = [fill] * S if S > 0 else []

    def push(self, v):
        if self.S > 0:
            self.buf.append(v)
            if len(self.buf) > self.S:
                self.buf.pop(0)

    @property
    def front(self):
        assert self.S > 0
        return self.buf[0]

# ---------------------------------------------------------------- 级模型
class Level:
    """级 ℓ:DIF SDF。SR 输入选择用延迟 Lc 拍的相位(原始数经 raw_pipe 才到 SR 口)。
       时序不变量:任意输入样元从本级输入到配对完成恰 D 拍;diff 从算出到输出恰 D 拍。"""
    def __init__(self, M, l, tw, scale=True, twf=None):
        N = 1 << M
        self.M, self.l = M, l
        self.R = N >> l
        self.D = self.R >> 1
        self.trivial = (l >= M - 2)
        self.Lc = 1 if self.trivial else 3
        self.S = self.D - self.Lc
        assert self.S >= 0, f"level {l}: S<0"
        self.scale = scale
        self.tw = tw[l]
        self.twf = twf[l] if twf is not None else None   # 浮点精确旋转因子(算法校验用)
        self.raw_pipe = DLine(self.Lc)          # 仅前半拍输入的原始数
        self.diff_pipe = DLine(self.Lc)         # 复乘/旋转 + 舍入后的 diff 路
        self.fh_hist = DLine(self.Lc)           # 相位(前半拍标志)延迟 Lc,SR 口选择用
        self.sr = DLine(self.S) if self.S > 0 else None
        self.p = 0
        self.out = (0, 0)

    def step(self, x, adv):
        """严格 read-before-write:当拍先读所有寄存态(=硬件组合读),再统一写入。
           时序:fh 输入@t -> raw_pipe.front@t+Lc -> SR 口@t+Lc -> SR.front@t+D(配对);
                 diff 算出@t(sh) -> diff_pipe.front@t+Lc -> SR 口 -> SR.front@t+D(下块前半拍输出)。"""
        if adv:
            re, im = x
            p = self.p
            half = self.R >> 1
            fh_now = p < half
            # ---- 组合读(当前态)----
            raw_f = self.raw_pipe.front
            diff_f = self.diff_pipe.front
            fh_f = self.fh_hist.front
            sr_f = self.sr.front if self.sr is not None else None
            partner = sr_f if self.sr is not None else raw_f
            # ---- 组合运算 ----
            if fh_now:
                out_raw = sr_f if self.sr is not None else diff_f
                y = None
            else:
                j = p - half
                bre, bim = partner
                d_re, d_im = bre - re, bim - im   # DIF: d = a - b,a=先存样元(早 D 拍)
                s_re, s_im = re + bre, im + bim
                if self.scale:
                    # 加法路 >>1 舍入后饱和到 16 位有符号(与 RTL 一致;输入含 −32768 时
                    # s 可达 65535,舍入 = 32768 溢出,饱和是宽度账闭合的一部分)
                    add_out = (max(-32768, min(32767, conv_round(s_re, 1))),
                               max(-32768, min(32767, conv_round(s_im, 1))))
                else:
                    add_out = (s_re, s_im)
                if self.trivial:
                    r_re, r_im = (d_re, d_im) if j == 0 else (d_im, -d_re)
                    y = (conv_round(r_re, 1), conv_round(r_im, 1)) if self.scale else (r_re, r_im)
                else:
                    if self.scale:
                        c_q, s_q = self.tw[j]
                        p_re, p_im = cmult_gauss(d_re, d_im, c_q, s_q)
                        y = (conv_round(p_re, 18), conv_round(p_im, 18))
                    else:
                        cr, ci = self.twf[j]           # (cr,ci)=(cos,-sin) 表示 W=cr+j·ci,标准复乘
                        y = (d_re * cr - d_im * ci, d_re * ci + d_im * cr)
                out_raw = add_out
            # ---- 统一写入 ----
            self.raw_pipe.push(x if fh_now else (0, 0))
            self.diff_pipe.push(y if y is not None else (0, 0))
            self.fh_hist.push((1, 0) if fh_now else (0, 0))
            if self.sr is not None:
                self.sr.push(raw_f if fh_f[0] else diff_f)   # fh_f 是元组,取标志位
            self.out = out_raw
            self.p = 0 if p == self.R - 1 else p + 1
        return self.out

# ---------------------------------------------------------------- 顶层

def to_c(fr):
    """(N,2) int 数组 -> complex ndarray"""
    return fr[:, 0].astype(np.float64) + 1j * fr[:, 1].astype(np.float64)

def bitrev(k, M):
    r = 0
    for _ in range(M):
        r = (r << 1) | (k & 1)
        k >>= 1
    return r

def out_perm(M):
    """输出置换 = 标准位倒序(DIF-SDF 经典结论)。
       旋转因子方向修正后,与逐 bin 经验提取(M=3..6,随机数据全 bin)完全一致。"""
    N = 1 << M
    pi = [bitrev(p, M) for p in range(N)]
    assert len(set(pi)) == N, "perm not bijective"
    return pi

def gen_twiddles_f(M):
    N = 1 << M
    out = []
    for l in range(M):
        D = N >> (l + 1)
        out.append([(math.cos(2 * math.pi * ((1 << l) * j) / N),
                     -math.sin(2 * math.pi * ((1 << l) * j) / N)) for j in range(D)])
    return out

class FftCore:
    def __init__(self, M, scale=True):
        self.M, self.N = M, 1 << M
        tw = gen_twiddles(M)
        twf = gen_twiddles_f(M)
        self.levels = [Level(M, l, tw, scale, twf) for l in range(M)]
        self.cyc = 0

    def step(self, x, adv):
        y = x
        for lv in self.levels:
            y = lv.step(y, adv)
        if adv:
            self.cyc += 1
        return y

def run_stream(M, frames, gap_fn=None, scale=True):
    """返回 (输出流, 输出流绝对周期号)。周期号含 stall 停拍。"""
    N = 1 << M
    core = FftCore(M, scale)
    stream, cycles = [], []
    t = 0
    for f, fr in enumerate(frames + [np.zeros((N, 2), np.int64)]):   # 末尾冲刷帧,保证最后一块输出完整
        i = 0
        while i < N:
            adv = 0 if (gap_fn is not None and gap_fn(t)) else 1
            y = core.step((int(fr[i][0]), int(fr[i][1])), adv)
            if adv:
                i += 1
                stream.append(y)
                cycles.append(t)
            t += 1
    return stream, cycles

def find_align(M, stream, frames, gain=1.0, tol=None, rel=0.0):
    """搜索帧对齐:输出流中输入帧 1 的输出帧起始下标。tol 绝对容差,rel 相对容差。"""
    N = 1 << M
    PI = out_perm(M)
    ref1 = np.fft.fft(to_c(frames[1])) * gain
    if tol is None:
        tol = max(8, N >> 4)
    best = (None, -1)
    step = max(1, N >> 4)
    for off in range(N, 3 * N):
        hits = 0
        for pp in range(0, N, step):
            yr, yi = stream[off + pp]
            er, ei = ref1[PI[pp]].real, ref1[PI[pp]].imag
            at = max(tol, abs(er) * rel)
            if abs(yr - er) <= at and abs(yi - ei) <= at:
                hits += 1
        if hits > best[1]:
            best = (off, hits)
    off = best[0]
    assert off is not None and best[1] >= (N >> 4) - 2, f"align fail {best}"
    return off

def check_alg(M, nframes=4, seed=11):
    """全精度(零舍入)模式对 numpy:验证算法/序数/交织正确(闸门 G2 算法面)。
       模型保留每级 2^17 刻度:M-2 个复乘 -> 总增益 2^(17*(M-2))。"""
    N = 1 << M
    rng = np.random.default_rng(seed)
    frames = [rng.integers(DIN_MIN, DIN_MAX + 1, size=(N, 2)).astype(np.int64) for _ in range(nframes)]
    stream, _ = run_stream(M, frames, scale=False)
    PI = out_perm(M)
    ref1 = np.fft.fft(to_c(frames[1]))
    # 稳健对齐:DC(bin0,流位置0)精确匹配候选 + 全 bin 验证
    off = None
    for o in range(N, 3 * N):
        yr, yi = stream[o]
        if abs(yr - ref1[0].real) <= 1e-6 * max(1.0, abs(ref1[0].real)) and            abs(yi - ref1[0].imag) <= 1e-6 * max(1.0, abs(ref1[0].imag)):
            ok = True
            for pp in range(0, N, max(1, N >> 3)):
                yr2, yi2 = stream[o + pp]
                if abs(yr2 - ref1[PI[pp]].real) > 1e-6 * max(1.0, abs(ref1[PI[pp]].real)) or                    abs(yi2 - ref1[PI[pp]].imag) > 1e-6 * max(1.0, abs(ref1[PI[pp]].imag)):
                    ok = False
                    break
            if ok:
                off = o
                break
    assert off is not None, f"M={M} align fail"
    max_rel = 0.0
    for fi in range(1, nframes):
        ref = np.fft.fft(to_c(frames[fi]))
        for pp in range(N):
            yr, yi = stream[off + (fi - 1) * N + pp]
            er, ei = ref[PI[pp]].real, ref[PI[pp]].imag
            den = max(1.0, abs(er), abs(ei))
            max_rel = max(max_rel, abs(yr - er) / den, abs(yi - ei) / den)
    assert max_rel < 1e-8, f"M={M} full-prec rel err {max_rel}"
    return max_rel, off

def check_stall_invariance(M, seed=13, nframes=3):
    """随机 stall(约 30% 停拍)下输出与无 stall 完全一致(SDF 时序不变量)。"""
    N = 1 << M
    rng = np.random.default_rng(seed)
    frames = [rng.integers(DIN_MIN, DIN_MAX + 1, size=(N, 2)).astype(np.int64) for _ in range(nframes)]
    s0, _ = run_stream(M, frames, scale=True)
    grng = np.random.default_rng(seed + 1)
    s1, _ = run_stream(M, frames, gap_fn=lambda t: grng.random() < 0.3, scale=True)
    assert s0 == s1, "stall invariance broken"
    return len(s0)

def sqnr(M, nframes=6, seed=17):
    N = 1 << M
    rng = np.random.default_rng(seed)
    frames = [rng.integers(DIN_MIN, DIN_MAX + 1, size=(N, 2)).astype(np.int64) for _ in range(nframes)]
    stream, _ = run_stream(M, frames, scale=True)
    PI = out_perm(M)
    g = 0.5 ** M
    off = 2 * N - 1                      # 确定性填充时延(M=3..7 冲激实测一致)
    refc = np.fft.fft(to_c(frames[1]))[0] * g
    assert abs(stream[off][0] - refc.real) < max(64.0, abs(refc.real) * 2e-3) and            abs(stream[off][1] - refc.imag) < max(64.0, abs(refc.imag) * 2e-3),            f"M={M} latency assumption broken: {stream[off]} vs {refc}"
    errs, sigs = [], []
    for fi in range(1, nframes):
        ref = np.fft.fft(to_c(frames[fi])) * g
        for pp in range(N):
            yr, yi = stream[off + (fi - 1) * N + pp]
            er, ei = ref[PI[pp]].real, ref[PI[pp]].imag
            errs.append((yr - er) ** 2 + (yi - ei) ** 2)
            sigs.append(er * er + ei * ei)
    return 10 * math.log10(sum(sigs) / len(sigs) / max(sum(errs) / len(errs), 1e-30))

# ---------------------------------------------------------------- 向量与 mem 生成
def gen_frames(test, N, nframes, seed):
    rng = np.random.default_rng(seed)
    frames = []
    for f in range(nframes):
        if test == "impulse":
            x = np.zeros((N, 2), np.int64)
            x[(f * 37) % N, 0] = 10000 if f % 2 == 0 else -9000
        elif test == "dc":
            x = np.full((N, 2), 1234 if f % 2 == 0 else -1234, np.int64)
        elif test == "tone":
            a, k = 20000, 5 + f
            x = np.stack([a * np.cos(2 * np.pi * k * np.arange(N) / N),
                          a * np.sin(2 * np.pi * k * np.arange(N) / N)], 1).astype(np.int64)
        elif test == "twotone":
            a = 12000
            x = np.stack([a * np.cos(2 * np.pi * 3 * np.arange(N) / N) + a * np.cos(2 * np.pi * 17 * np.arange(N) / N + 0.7),
                          a * np.sin(2 * np.pi * 3 * np.arange(N) / N) + a * np.sin(2 * np.pi * 17 * np.arange(N) / N + 0.7)], 1).astype(np.int64)
        elif test == "noise":
            x = rng.integers(DIN_MIN, DIN_MAX + 1, size=(N, 2)).astype(np.int64)
        elif test == "corner":
            x = np.zeros((N, 2), np.int64)
            x[0] = (DIN_MAX, DIN_MAX); x[1] = (DIN_MIN, DIN_MIN)
            x[2] = (DIN_MAX, DIN_MIN); x[3] = (DIN_MIN, DIN_MAX)
            x[4::7] = (DIN_MAX, 0); x[5::11] = (0, DIN_MIN)
        else:
            raise ValueError(test)
        frames.append(np.clip(x, DIN_MIN, DIN_MAX))
    return frames

def pack_word(re, im, W):
    return ((int(im) & ((1 << W) - 1)) << W) | (int(re) & ((1 << W) - 1))

def export(M, test, nframes=3, outdir="vectors", seed=1234):
    import os
    N = 1 << M
    os.makedirs(outdir, exist_ok=True)
    frames = gen_frames(test, N, nframes, seed)
    stream, _ = run_stream(M, frames, scale=True)
    off = 2 * N - 1                      # 第 1 输入帧的输出帧起点(流下标),确定性时延
    base = os.path.join(outdir, f"tv_N{N}_{test}")
    with open(base + "_in.hex", "w") as fo:
        for fr in frames:
            for re, im in fr:
                fo.write(f"{pack_word(re, im, DATA_W):08X}\n")
    # 输出有效段:从输入帧 1(第 2 帧)的输出起点开始,长度 (nframes-1)*N
    with open(base + "_out.hex", "w") as fo:
        for yr, yi in stream[off: off + (nframes - 1) * N]:
            fo.write(f"{pack_word(yr, yi, DATA_W):08X}\n")
    with open(base + "_info.txt", "w") as fo:
        fo.write(f"N={N} M={M} test={test} nframes={nframes}\n")
        fo.write("in.hex : nframes*N words, tdata={im[15:0],re[15:0]}, frame-major\n")
        fo.write("out.hex: (nframes-1)*N words = 输入帧1..nframes-1 的输出(位倒序)\n")
        fo.write("first input frame output is discarded (SR warm-up)\n")
    return off

def gen_all_mem(M_list=(6, 8, 10, 12), outdir="vectors"):
    import os
    os.makedirs(outdir, exist_ok=True)
    for M in M_list:
        tw = gen_twiddles(M)
        for l, lvl in enumerate(tw):
            if l >= M - 2:
                continue
            with open(os.path.join(outdir, f"tw_N{1 << M}_L{l}.mem"), "w") as fo:
                for c, s in lvl:
                    fo.write(f"{(((s & 0x3FFFF) << 18) | (c & 0x3FFFF)):09X}\n")

# ---------------------------------------------------------------- 自检
def self_test():
    rng = np.random.default_rng(0)
    for _ in range(20000):
        x = int(rng.integers(-(1 << 40), 1 << 40))
        s = int(rng.integers(1, 20))
        assert conv_round(x, s) == rtl_round(x, s), (x, s)
    for _ in range(10000):
        a, b, c, d = [int(v) for v in rng.integers(-(1 << 20), 1 << 20, 4)]
        assert cmult_gauss(a, b, c, d) == cmult_ref(a, b, c, d)
    print("[self-test] rounding + gauss identity PASS")

def perm_empirical_check(Mmax=6):
    """用浮点精确模式逐 bin 提取经验置换,与闭式 pi 断言一致。"""
    for M in range(3, Mmax + 1):
        N = 1 << M
        rng = np.random.default_rng(100 + M)
        frames = [rng.integers(DIN_MIN, DIN_MAX + 1, size=(N, 2)).astype(np.int64) for _ in range(3)]
        stream, _ = run_stream(M, frames, scale=False)
        ref = np.fft.fft(to_c(frames[1]))
        off = None
        for o in range(N, 3 * N):
            if abs(stream[o][0] - ref[0].real) < 1e-6 * max(1.0, abs(ref[0].real)) and                abs(stream[o][1] - ref[1 if False else 0].imag) < 1e-6 * max(1.0, abs(ref[0].imag)):
                off = o
                break
        assert off is not None, f"M={M} no DC"
        PI = out_perm(M)
        for p in range(N):
            yr, yi = stream[off + p]
            er, ei = ref[PI[p]].real, ref[PI[p]].imag
            assert abs(yr - er) <= 1e-6 * max(1.0, abs(er)) and abs(yi - ei) <= 1e-6 * max(1.0, abs(ei)),                 f"M={M} p={p} pi mismatch"
    print(f"[self-test] output permutation closed-form == empirical (M=3..{Mmax}) PASS")

def gen_perm_mem(M_list=(6, 8, 10, 12), outdir="vectors"):
    import os
    os.makedirs(outdir, exist_ok=True)
    for M in M_list:
        N = 1 << M
        PI = out_perm(M)
        with open(os.path.join(outdir, f"perm_N{N}.mem"), "w") as fo:
            w = (M + 3) // 4
            for v in PI:
                fo.write(("%0" + str(w) + "X\n") % (v & ((1 << M) - 1)))

if __name__ == "__main__":
    self_test()
    perm_empirical_check()
    for M in (6, 8, 10, 12):
        me, off = check_alg(M)
        si = check_stall_invariance(M)
        q = sqnr(M)
        print(f"[G2] N={1<<M:5d} full-prec rel_err={me:.2e} | stall-inv {si} smp | scaled SQNR={q:6.2f} dB")
    gen_all_mem()
    gen_perm_mem()
    for M in (6, 8, 10, 12):
        for test in ("tone", "noise", "corner", "impulse", "twotone", "dc"):
            export(M, test, nframes=3)
    print("vectors + twiddle mem generated")
