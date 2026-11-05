// fft_stage.v — radix-2 SDF 流水线第 L 级(DIF,自然序入 / 位倒序出)。
//
// 与 golden/fft_model.py 的 Level 类逐拍对应(含初值:全部数据通路寄存器/存储
// 零初始化 = 模型 DLine 的 (0,0) 初值,这是"帧1起输出逐位有效"证明的前提):
//   相位 p(块长 R=N/2^L,D=R/2):前半拍(fh)存数,后半拍(sh)配对;
//   fh 拍:输出 SR 前端(上一块的 diff·W);x 进 raw_pipe(深 LC);
//   sh 拍:partner=SR 前端,d=partner−x,s=x+partner;
//         加法路:s>>1 convergent → 饱和 16 位 → 本拍输出;
//         差 路:非平凡级 fft_cmult3(Lc=3)回填 SR;平凡级(W4/W2)纯旋转+舍入(Lc=1);
//   SR:深 S=D−LC 循环延迟线(S=1 退化为单寄存),无复位、零初始化;
//   SR 写入选择 = 延迟 LC 拍的 fh 标志(原始数经 raw_pipe 到达 SR 口恰迟 LC 拍)。
//
// 位宽(I-08 终版,黄金语义逐位对齐):
//   SR 内容 = diff 路 conv_round(d·W,18) 输出,值域 18 位(实测 34549>32767,
//   理论界 |y|≤131071);级间字 36 位 = {im18, re18},SR/raw_pipe/fr 全 36 位;
//   partner/x 18 位;d/s 19 位;sb(=2s+s[1])20 位;饱和检测 = sb 高 4 位
//   一致性;ad 16 位(不变);cmult a 路 19 位、y 路 18 位。
//   顶层输出 m_axis = 级间字低 32 位(模 2^16,与黄金 16 位流文件一致)。
//
// 旋转因子 ROM:vectors/tw_L{LI}.mem,LI = L+12−M(级前缀复用,条目数恰为 D),未旋转表;
//   地址 = p_j+1(R=2^PW,回绕自然):rom_q@t = tw[j(t)],与差路同拍进入复乘。
// 时序不变量(模型已验证):样元本级输入→配对完成恰 D 拍;diff 算出→输出恰 D 拍。

module fft_stage #(
    parameter M  = 12,
    parameter L  = 0,
    parameter DW = 16,
    parameter SW = 18,                         // SR/级间字段宽(18 位补码)
    parameter K  = 0                           // 相位滞后拍数 = 级间寄存级数(顶层传 L)
)(
    input  wire             clk,
    input  wire             rst,        // 仅复位相位计数(控制状态)
    input  wire             en,         // 流水推进
    input  wire [2*SW-1:0]  x_tdata,    // {im18, re18} 全精度级间字
    input  wire             x_valid,
    output wire [2*SW-1:0]  y_tdata,
    output wire             y_valid
);
    localparam N  = 1 << M;
    localparam R  = N >> L;
    localparam D  = R >> 1;
    localparam TRIVIAL = (L >= M - 2);
    localparam LC = TRIVIAL ? 1 : 3;
    localparam S  = D - LC;
    localparam SWW = SW;                       // SR/级间字段宽(18 位补码)
    localparam AW  = 19;                       // d/s 路位宽
    localparam LI = L + (12 - M);              // 旋转因子文件级号

    function integer clog2p1(input integer v);
        integer vv;
        begin
            clog2p1 = 0;
            for (vv = v - 1; vv > 0; vv = vv >> 1) clog2p1 = clog2p1 + 1;
        end
    endfunction

    localparam PW = clog2p1(R);
    localparam PINIT_I = (R - (K % R)) % R;
    localparam [PW-1:0] PINIT = PINIT_I;
    localparam [PW-1:0] R_M1 = R - 1;
    localparam [PW-1:0] HALF = R / 2;

    // ---------------- 相位 ----------------
    reg [PW-1:0] p;
    wire fh_now = (p < HALF);
    wire [PW-1:0] p_j = p - HALF;              // sh 拍内配对号 j(仅 !fh_now 有意义)
    always @(posedge clk) begin
        if (rst)     p <= PINIT;
        else if (en) p <= (p == R_M1) ? {PW{1'b0}} : p + 1'b1;
    end

    // ---------------- 前向声明 ----------------
    wire [2*SWW-1:0] sr_in;                    // SR 写入口(差路之后赋值)
    wire [2*SWW-1:0] sr_front_w;

    // ---------------- 输入 ----------------
    wire signed [SWW-1:0] x_re = x_tdata[SWW-1:0];
    wire signed [SWW-1:0] x_im = x_tdata[2*SWW-1:SWW];

    // ---------------- raw_pipe(深 LC)+ fh 历史 ----------------
    reg [2*SWW-1:0] rp0, rp1, rp2;
    reg f0, f1, f2;
    initial begin
        rp0 = {2*SWW{1'b0}}; rp1 = {2*SWW{1'b0}}; rp2 = {2*SWW{1'b0}};
        f0 = 1'b0; f1 = 1'b0; f2 = 1'b0;
    end
    always @(posedge clk) if (en) begin
        if (LC == 3) begin
            rp0 <= rp1;  rp1 <= rp2;  rp2 <= fh_now ? x_tdata : {2*SWW{1'b0}};
            f0  <= f1;   f1  <= f2;   f2  <= fh_now;
        end else begin
            rp0 <= fh_now ? x_tdata : {2*SWW{1'b0}};
            f0  <= fh_now;
        end
    end
    wire [2*SWW-1:0] raw_f = rp0;
    wire fh_sel = f0;                          // LC 拍前的 fh 标志

    // ---------------- 蝶形 ----------------
    wire [2*SWW-1:0] partner_w = (S > 0) ? sr_front_w : raw_f;
    wire signed [SWW-1:0] pr_re = partner_w[SWW-1:0];
    wire signed [SWW-1:0] pr_im = partner_w[2*SWW-1:SWW];
    wire signed [SWW-1:0] xr_re = x_re;
    wire signed [SWW-1:0] xr_im = x_im;
    wire signed [AW-1:0] d_re = pr_re - xr_re;             // DIF: d = a − b(a=先存)
    wire signed [AW-1:0] d_im = pr_im - xr_im;
    wire signed [AW-1:0] s_re = xr_re + pr_re;
    wire signed [AW-1:0] s_im = xr_im + pr_im;

    // 加法路 >>1 convergent:y=(s+s[1])>>1,饱和到 16 位有符号
    // sat ⟺ (s+s[1])>>1 ∉ [−32768, 32767] ⟺ sb ∉ [−65536, 65535]
    //     ⟺ sb(20 位)高 4 位非全同
    wire signed [AW:0] sb_re0 = {s_re[AW-1], s_re} + {{AW{1'b0}}, s_re[1]};
    wire signed [AW:0] sb_im0 = {s_im[AW-1], s_im} + {{AW{1'b0}}, s_im[1]};
    wire sat_re = (sb_re0[AW] ^ sb_re0[AW-1]) | (sb_re0[AW-1] ^ sb_re0[AW-2]) | (sb_re0[AW-2] ^ sb_re0[AW-3]);
    wire sat_im = (sb_im0[AW] ^ sb_im0[AW-1]) | (sb_im0[AW-1] ^ sb_im0[AW-2]) | (sb_im0[AW-2] ^ sb_im0[AW-3]);
    wire signed [DW-1:0] ad_re = sat_re ? (sb_re0[AW] ? -32768 : 32767) : sb_re0[DW:1];
    wire signed [DW-1:0] ad_im = sat_im ? (sb_im0[AW] ? -32768 : 32767) : sb_im0[DW:1];

    // ---------------- 差路 ----------------
    wire signed [17:0] tw_re, tw_im;
    wire signed [SWW-1:0] cm_re, cm_im;
    wire cm_v;

    generate if (!TRIVIAL) begin : g_rom
        (* rom_style = "block" *)
        reg [35:0] rom [0:D-1];
        reg [35:0] rom_q;
        // 地址 = p_j+1(mod D):在 t−1 拍取 j(t)−1,一拍延迟后 rom_q@t = tw[j(t)];
        // 显式 mod D 钳位:fh 拍的 p_j 回绕值会越界,行为仿真产生 X 并沿复乘传播。
        localparam [PW-1:0] D_M1 = D - 1;
        wire [PW-1:0] a_idx = (p_j + 1'b1) & D_M1;   // mod D,D=2^k:全地址域钳位,杜绝越界 X
        always @(posedge clk) if (en) rom_q <= rom[a_idx];
        assign tw_re = rom_q[17:0];
        assign tw_im = rom_q[35:18];
        initial begin
            rom_q = 36'h0;
            if      (LI == 0) $readmemh("vectors/tw_L0.mem", rom);
            else if (LI == 1) $readmemh("vectors/tw_L1.mem", rom);
            else if (LI == 2) $readmemh("vectors/tw_L2.mem", rom);
            else if (LI == 3) $readmemh("vectors/tw_L3.mem", rom);
            else if (LI == 4) $readmemh("vectors/tw_L4.mem", rom);
            else if (LI == 5) $readmemh("vectors/tw_L5.mem", rom);
            else if (LI == 6) $readmemh("vectors/tw_L6.mem", rom);
            else if (LI == 7) $readmemh("vectors/tw_L7.mem", rom);
            else if (LI == 8) $readmemh("vectors/tw_L8.mem", rom);
            else              $readmemh("vectors/tw_L9.mem", rom);
        end
    end endgenerate

    fft_cmult3 #(.AW(AW), .BW(18), .RSH(18), .YW(SWW)) u_cmult (
        .clk(clk), .en(en),
        .a_re(d_re), .a_im(d_im),
        .b_re(tw_re), .b_im(tw_im),
        .a_valid(x_valid),
        .y_re(cm_re), .y_im(cm_im), .y_valid(cm_v)
    );

    // 平凡级:W4 {1,−j} / W2 {1},纯旋转 + >>1 舍入寄存(Lc=1)
    // y = conv_round(d',1) 值域 18 位 → tr_y 取 trb[18:1]
    wire tri_id = (p_j == 0) || (R == 2);
    wire signed [AW-1:0] tr_re = tri_id ? d_re : d_im;
    wire signed [AW-1:0] tr_im = tri_id ? d_im : -d_re;
    wire signed [AW:0] trb_re = {tr_re[AW-1], tr_re} + {{AW{1'b0}}, tr_re[1]};
    wire signed [AW:0] trb_im = {tr_im[AW-1], tr_im} + {{AW{1'b0}}, tr_im[1]};
    reg [SWW-1:0] tr_y_re, tr_y_im;
    initial begin
        tr_y_re = {SWW{1'b0}}; tr_y_im = {SWW{1'b0}};
    end
    always @(posedge clk) if (en) begin
        tr_y_re <= trb_re[SWW:1];
        tr_y_im <= trb_im[SWW:1];
    end

    wire [2*SWW-1:0] diff_f = TRIVIAL ? {tr_y_im, tr_y_re}
                                     : {cm_im, cm_re};

    assign sr_in = fh_sel ? raw_f : diff_f;

    // ---------------- 主延迟线 SR(深 S,无复位,零初始化) ----------------
    generate if (S == 1) begin : g_sr1
        reg [2*SWW-1:0] fr;
        initial fr = {2*SWW{1'b0}};
        always @(posedge clk) if (en) fr <= sr_in;
        assign sr_front_w = fr;
    end else if (S > 1) begin : g_srN
        localparam AWD = clog2p1(S);
        localparam [AWD-1:0] S_M1 = S - 1;
        reg [2*SWW-1:0] mem [0:S-1];
        reg [AWD-1:0]  wptr;
        reg [2*SWW-1:0] fr;
        wire [AWD-1:0] rm1 = (wptr == S_M1) ? {AWD{1'b0}} : wptr + 1'b1;
        integer zi;
        initial begin
            fr = {2*SWW{1'b0}}; wptr = {AWD{1'b0}};
            for (zi = 0; zi < S; zi = zi + 1) mem[zi] = {2*SWW{1'b0}};
        end
        always @(posedge clk) if (en) begin
            mem[wptr] <= sr_in;
            wptr      <= rm1;
            fr        <= mem[rm1];             // raddr=wptr+1:fr@t = t−S 拍写入值
        end
        assign sr_front_w = fr;
    end else begin : g_sr0
        assign sr_front_w = {2*SWW{1'b0}};
    end endgenerate

    // ---------------- 输出选择 ----------------
    // fh 段:SR 读出 36 位全精度透传(级间);末级由 fft_top 取低 32 位
    // sh 段:ad 16 位符号扩展到 18 位字段
    wire [2*SWW-1:0] out_c = fh_now ? ((S > 0) ? sr_front_w : diff_f)
                                   : {{(SWW-DW){ad_im[DW-1]}}, ad_im,
                                      {(SWW-DW){ad_re[DW-1]}}, ad_re};
    reg [2*SWW-1:0] out_r;
    reg            out_v;
    initial begin
        out_r = {2*SWW{1'b0}}; out_v = 1'b0;
    end
    always @(posedge clk) if (en) begin
        out_r <= out_c;
        out_v <= x_valid;
    end
    assign y_tdata = out_r;
    assign y_valid = out_v;

endmodule
