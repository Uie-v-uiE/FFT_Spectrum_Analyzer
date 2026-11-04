# I-08 分析资产(2026-11-05 会话)
- mirror_sweep_result.txt: 镜像穷举结果——L0..L3 在 (pinit=0, 3元素管, ROM=p_j, SRD=0) 下
  与黄金 Level 逐位全对;L4/L5 需镜像补 TRIVIAL tr 路径。
- 关键实测律: 丢点 = 47 - PINIT(PINIT 0/1/2/31 → 47/46/45/48),SR 内容相位随 PINIT
  非单调(PINIT=0: 早2; PINIT=1: 晚1),L1 输出对 fr 内容改动免疫 → 丢点结构性,
  SR 内容序列与黄金差 1 拍且与 fh 窗口耦合,单一旋钮不可解。
- 镜像对拍脚本要点: 输入必须 stream[k+DELAY]、ROM 等效 tw[p_j]、DLine滞后=管长、
  大小写统一 lower()、真实输入向量 only_noise_in.hex。
