// fft_cmult3.v — 3-DSP 高斯复数乘法器(恒等式:k1=br·(ar+ai), k2=ai·(br+bi),
// k3=bi·(ar−ai);re=k1−k2, im=k2+k3),三个 DSP48E2 全部使用预加器,无 LUT 预加。
// 流水 Lc=3:a@t → r1@t+1 → P@t+2 → 舍入寄存@t+3;输出 = convergent(a·b >> 18)
// (17 位旋转因子刻度 + 1 位级缩放,单次舍入,与 golden/fft_model.py 逐位一致)。
// 位宽账:|a|≤2^16(17b 有符号),|b|≤1(18b 定点 2^17),|a·b|/2 ≤ 2^15+ε → 输出 17b
// (位 16 为符号冗余,取 [DW-1:0] 与模型一致)。全部寄存器零初始化(与模型对齐)。

module fft_cmult3 #(
    parameter AW = 17,                       // a 路位宽(有符号)
    parameter BW = 18,                       // b 路位宽(有符号,2^17 刻度)
    parameter RSH = 18                       // 总移位 = 17(刻度) + 1(级缩放)
)(
    input  wire                    clk,
    input  wire                    en,       // 流水推进
    input  wire signed [AW-1:0]    a_re,     // t 拍组合输入(蝶形差路)
    input  wire signed [AW-1:0]    a_im,
    input  wire signed [BW-1:0]    b_re,     // t 拍旋转因子(ROM 出)
    input  wire signed [BW-1:0]    b_im,
    input  wire                    a_valid,
    output reg  signed [AW-1:0]    y_re,     // t+3 拍
    output reg  signed [AW-1:0]    y_im,
    output reg                     y_valid
);
    localparam PW = AW + BW + 2;             // 乘积位宽(48 内)

    // ---- r1:输入寄存(综合吸收进 DSP A1/B1/D1) ----
    reg signed [AW-1:0] ar1, ai1;
    reg signed [BW-1:0] br1, bi1;
    reg v1;
    initial begin
        ar1 = {AW{1'b0}}; ai1 = {AW{1'b0}};
        br1 = {BW{1'b0}}; bi1 = {BW{1'b0}}; v1 = 1'b0;
    end
    always @(posedge clk) if (en) begin
        ar1 <= a_re; ai1 <= a_im;
        br1 <= b_re; bi1 <= b_im;
        v1  <= a_valid;
    end

    // ---- p:三个乘积(综合映射 3×DSP48E2,预加器吸收 A±D) ----
    reg signed [PW-1:0] k1, k2, k3;
    reg v2;
    initial begin
        k1 = {PW{1'b0}}; k2 = {PW{1'b0}}; k3 = {PW{1'b0}}; v2 = 1'b0;
    end
    always @(posedge clk) if (en) begin
        k1 <= br1 * (ar1 + ai1);             // DSP 预加器 A+D
        k2 <= ai1 * (br1 + bi1);             // DSP 预加器 A+D(操作数经 A/D 侧)
        k3 <= bi1 * (ar1 - ai1);             // DSP 预加器 A-D
        v2 <= v1;
    end

    // ---- y:求和 + convergent 舍入 >>RSH ----
    // y = (x + 2^(RSH-1) - 1 + ((x>>RSH)&1)) >> RSH,与模型 rtl_round 逐位一致
    wire signed [PW-1:0] sre = k1 - k2;
    wire signed [PW-1:0] sim = k2 + k3;
    wire signed [PW-1:0] sre_b = sre + {{(PW-1){1'b0}}, sre[RSH]} + {{(PW-RSH+1){1'b0}}, {(RSH-1){1'b1}}};
    wire signed [PW-1:0] sim_b = sim + {{(PW-1){1'b0}}, sim[RSH]} + {{(PW-RSH+1){1'b0}}, {(RSH-1){1'b1}}};
    always @(posedge clk) if (en) begin
        y_re    <= sre_b[PW-1:RSH];
        y_im    <= sim_b[PW-1:RSH];
        y_valid <= v2;
    end
endmodule

/* 偏置核对:偏置 = (2^(RSH-1) − 1) + ((x>>RSH)&1),convergent 位权重为 1(加在最低位)。
   初版两处都错:低场写成 2^RSH−1、convergent 位放在 bit[RSH](权重 2^RSH),
   分别造成 ±1 与恰逢半 LSB 时的进位错误,由 tb_fft_cmult3 逐位对拍捕获(I-07)。 */
