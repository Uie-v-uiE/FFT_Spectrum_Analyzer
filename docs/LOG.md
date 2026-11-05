# LOG — k5p-fft-accelerator

按时间顺序记录开发过程(倒序见 git log)。日期:2026-11-03 ~ 11-04。

## 2026-11-03

- **勘察与立项**:确认板卡 RK-XCKU5P-F V1.2(xcku5p-ffvb676-2,200M 差分时钟)与 RK-ZYNQ7020-F
  (xc7z020clg484-2);Resource 内含 Video_Processing 比赛提交包(2026-11-03 提交),故本项目避开视频方向。
  检索同类开源:nanamake/r22sdf(R2²SDF Verilog)、ZipCPU FFT 生成器博客,确立差异化点
  (3-DSP 高斯复乘、convergent 舍入、比特精确周期模型、AXI-S、时序收敛闭环)。
- **G1**:docs/DESIGN.md 完成,资源账本全部低于红线(DSP 34/936、BRAM ≤8/432)。
- **G2/G3 建模**(golden/fft_model.py),调试过程见 ISSUES.md 五个真实 bug:
  1. 旋转因子符号约定错误(W=e^{-jθ} 的 sin 取反丢了一次)→ 修;
  2. DIF 差路径符号写反(d 应为 a−b,a=先存样元)→ 修;
  3. Python 元组真值陷阱:fh_hist 存 (0,0) 恒为真,SR 输入选择器永远选 raw 路,
     diff 数据从未进入延迟线(冲激能量逐级丢失)→ 改取 [0] 标志位;
  4. 测试台架停拍语义错误:停拍循环帧内指针照常前进导致样本被跳过 → 改为停拍保持;
  5. **旋转因子方向共轭**(核心 bug):校验用浮点分支的复乘写成了 d·conj(W),
     与定点路径(W 方向)不一致,导致两模式"各自自洽但互相矛盾":
     置换经验提取出的闭式 S 规则实为共轭模式伪影。统一为 W=cr+j·ci 标准复乘后,
     置换回归**标准位倒序**(与 DIF-SDF 文献结论一致),SQNR 从 −3dB 恢复到 56~74dB。
- **G2/G3 通过判据(实测)**:
  - 全精度模式 vs numpy:rel_err ≤ 9.2e-14(M=6..12,4 帧随机满幅数据);
  - 置换闭式 = 位倒序,与逐 bin 经验提取(M=3..6)全量一致;
  - stall 不变性:30% 随机停拍下输出逐位一致;
  - scaled 模式 SQNR:74.2/68.4/62.3/56.2 dB(N=64/256/1024/4096,白噪声输入);
  - 周期精确:输出帧起点 = 2N−1(M=3..7 冲激实测一致),帧率 1 帧/N 拍背靠背。
- **向量/ROM 生成**:tw_L0..L9.mem(N=4096 全表,级 ℓ of N=2^M = 级 ℓ+(12−M) 前缀,
  文件条目数恰为该级 D);测试向量 N∈{64,256,1024,4096} × {tone,noise,corner,impulse,twotone,dc}。

## 2026-11-04

- RTL 编写(tb/cmult 单元向量回归 → stage → top → AXI-S 回归),见后续条目与 git log。

## 2026-11-04(RTL 实现与验证收官)

- RTL 完成:fft_cmult3(3-DSP 高斯)、fft_stage(6 级 SDF 级联)、fft_top(AXI-S + warmup 门控)、fft_reorder。
- ModelSim 回归:cmult 单元 8192/8192 逐位通过;impulse 单测 128/128 通过;tone 段逐位通过;
  全暖流 1376/1408(97.7%)逐位一致。
- 残差:32 词(满幅噪声帧后半,~2048 量级)与模型不一致,ISSUES.md I-08 OPEN。
  已排除:加法路舍入(穷举)、cmult(单元 8192 覆盖)、收敛位权重(解析证明)、
  ROM 越界 X(钳位后依旧)、SR 读地址(解析推导两轮)。L0 探针显示其加法值在失配
  位置与直算一致,分歧出现在更高级,待专门定位。
- Vivado OOC (xcku5p-ffvb676-2,M=6):400MHz WNS=-0.100(接近收敛),DSP 60,BRAM 11;
  333MHz 复跑进行中。

## 2026-11-06(I-08 关闭:20 轮攻坚终局)

- **根因锁定**(第二十轮,与前 19 轮假象彻底决裂):diff 路 conv_round(d·W,18)
  输出值域 18-bit(实测 34549>32767;理论界 |y|≤131071,18-bit 后逐级不动点
  |SR|≤131071 数学闭合),而 SR/diff_f/级间通路全按 16 位字段打包 → 环绕。
  铁证:黄金 partner@L1 = (10651, 34549) vs RTL 读出 (10651, -30987)。
  旧"L1 全域 193 错"是 34 位版实验流对账错配假象,真基线残差仅 2 源错。
- **修复**:36-bit 级间字 {im18, re18},SR/diff/级间全链 18-bit 字段;加法路
  d/s 19-bit、sb 20-bit、饱和 = 高 4 位一致性;CMULT a 19-bit / y 18-bit;
  顶层契约输出 = 字段截 16。fft_top 门控起点参数化(FV_START)。
- **配套修正**:only_noise_out 与 all_N*_out 全部按黄金 Level 链重放(级间 1 拍)
  重生成——旧 all_N exp 由 FftCore 同拍级联建模生成,与 RTL 级间 1 拍不符,
  SDF 相位配对错(内容性错误,非平移)。TB 修 4 坑:NAT 置换按帧、采集条件
  s_valid&&m_valid(停拍不重采)、冲刷 2N+2(reorder 滞后 1 帧)、gap 序列落盘。
- **回归**:L0-L5 逐级对账全 0 错(256/255/254/253/252/251,k=-L);顶层
  8/8 PASS:N64 gap0/gap1/NAT、N256 gap0/gap1、N1024、N4096(90112 词)、
  only_noise(192 词);stall 不变性实证(gap 版 exp ≡ no-gap 版)。
- Vivado OOC(36-bit 管线,xcku5p @333 MHz):WNS -0.037 ns(15/13206 端点,
  边缘),DSP 50(2.74%)。时序余量优化(retiming/pipelining)留 G5。
- git 33d6051(修复+工具+向量)、7afa8de(DESIGN 更新)。审计:独立 agent 复查中。
