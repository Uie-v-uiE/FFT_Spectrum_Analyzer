// fft_top.v — radix-2 SDF 流水线 FFT 顶层(AXI4-Stream)。
//
//   s_axis: tdata = {im[DW-1:0], re[DW-1:0]},TUSER 无(帧节拍由核心内部计数)
//   m_axis: tdata 同上;tuser=帧首;tlast=帧尾;输出序 = 位倒序(OUT_NATURAL=0)
//           或自然序(OUT_NATURAL=1,内置 ping-pong 重排序缓冲,延迟 +N 拍)
//
// 反压:en = s_axis_tvalid & m_axis_tready —— 两侧均为外部寄存信号,核心内部
// 无组合 ready 链;全流水零气泡(背靠背帧)。停拍时所有状态冻结(时序不变量
// 已由模型 stall 不变性验证)。
// warmup:复位后前 FIRST_VALID 个原始输出无效(填充瞬态),m_valid 门控。
// cyc = 原始输出流下标,与模型流下标一一对应;首输出 = 模型流下标 2N−1(帧 2 起点)。

module fft_top #(
    parameter M  = 12,
    parameter DW = 16,
    parameter OUT_NATURAL = 0,
    parameter FV_START = 0   // 门控起点覆盖:0 = 旧默认 3N;向量配套契约起点(模型流下标)- M + 2
)(
    input  wire             clk,
    input  wire             rst,            // 同步复位(仅控制状态)
    input  wire [2*DW-1:0]  s_axis_tdata,
    input  wire             s_axis_tvalid,
    output wire             s_axis_tready,
    output wire [2*DW-1:0]  m_axis_tdata,
    output wire             m_axis_tvalid,
    output wire             m_axis_tuser,   // 帧首
    output wire             m_axis_tlast,   // 帧尾
    input  wire             m_axis_tready
);
    localparam N  = 1 << M;
    localparam SW = 18;                     // 级间字段宽(18 位,I-08 终版)
    localparam NFIRST = 3*N;                // cyc(滞后1) +1 ≥ 3N ⟺ 首个门控 = 流下标 3N−1(帧2块起点)

    function integer clog2p1(input integer v);
        integer vv;
        begin
            clog2p1 = 0;
            for (vv = v - 1; vv > 0; vv = vv >> 1) clog2p1 = clog2p1 + 1;
        end
    endfunction

    localparam CW = clog2p1(NFIRST + 1);
    localparam [CW-1:0] FIRST_VALID = (FV_START > 0) ? FV_START : NFIRST;
    localparam [CW-1:0] CWZERO = {CW{1'b0}};

    // ---------------- 推进与 warmup 计数 ----------------
    wire en = s_axis_tvalid & m_axis_tready & !rst;
    assign s_axis_tready = m_axis_tready;   // 核心无内部缓冲:ready=可推进

    // ---------------- 级联 ----------------
    wire [2*SW-1:0] lk_tdata [0:M];
    wire            lk_valid[0:M];
    // 输入 16 位符号扩展到 18 位字段(黄金语义:输入 16 位,内部 18 位域)
    assign lk_tdata[0]  = {{2{s_axis_tdata[2*DW-1]}}, s_axis_tdata[2*DW-1:DW],
                           {2{s_axis_tdata[DW-1]}},  s_axis_tdata[DW-1:0]};
    assign lk_valid[0]  = s_axis_tvalid;

    genvar g;
    generate
        for (g = 0; g < M; g = g + 1) begin : g_stages
            // K=g:级间 1 拍寄存的相位补偿——数据到级 g 晚 g 拍,PINIT 滞后 g
            // 才能与数据流相位对齐(缺此补偿蝶形配对错位,级联不是 DFT)
            fft_stage #(.M(M), .L(g), .DW(DW), .SW(SW), .K(g)) u_st (
                .clk(clk), .rst(rst), .en(en),
                .x_tdata(lk_tdata[g]), .x_valid(lk_valid[g]),
                .y_tdata(lk_tdata[g+1]), .y_valid(lk_valid[g+1])
            );
        end
    endgenerate

    // 原始输出流下标计数:统计 lk_valid 脉冲数 = 当前输出的模型流下标
    // (门控起点 = 3N−1,即帧 2 的第一个输出;warmup 契约外)
    reg [CW-1:0] cyc;
    initial cyc = {CW{1'b0}};
    always @(posedge clk) begin
        if (rst)         cyc <= CWZERO;
        else if (en && lk_valid[M]) cyc <= (cyc == FIRST_VALID) ? FIRST_VALID : cyc + 1'b1;
    end


    // ---------------- 输出序(位倒序 / 自然序) ----------------
    wire [2*SW-1:0] raw_tdata = lk_tdata[M];
    wire            raw_valid = lk_valid[M] & (cyc + 1'b1 >= FIRST_VALID);

    // 输出块内位置计数(有效输出推进计)
    localparam OW = clog2p1(N);
    localparam [OW-1:0] N_M1 = N - 1;
    localparam [OW-1:0] OWZERO = {OW{1'b0}};
    reg [OW-1:0] opos;
    initial opos = {OW{1'b0}};
    always @(posedge clk) begin
        if (rst)                 opos <= OWZERO;
        else if (raw_valid)      opos <= (opos == N_M1) ? OWZERO : opos + 1'b1;
    end
    wire frame_last = (opos == N_M1);
    wire frame_first = (opos == OWZERO);

    generate if (OUT_NATURAL == 0) begin : g_direct
        // 末端 16 位契约输出 = 级间字低 32 位(模 2^16,与黄金 16 位流文件一致)
        assign m_axis_tdata  = {raw_tdata[33:18], raw_tdata[15:0]};  // 16 位契约:各取 18 位字段低 16
        assign m_axis_tvalid = raw_valid;
        assign m_axis_tuser  = raw_valid & frame_first;
        assign m_axis_tlast  = raw_valid & frame_last;
    end else begin : g_reorder
        // ping-pong 重排:写地址 = 位倒序(opos),块满切换读出
        wire [2*SW-1:0] rb_tdata;
        wire            rb_valid, rb_first, rb_last;
        fft_reorder #(.M(M), .DW(DW), .SW(SW)) u_reorder (
            .clk(clk), .rst(rst), .en(en),
            .x_tdata(raw_tdata), .x_pos(opos), .x_valid(raw_valid),
            .y_tdata(rb_tdata), .y_valid(rb_valid),
            .y_first(rb_first), .y_last(rb_last)
        );
        assign m_axis_tdata  = {rb_tdata[33:18], rb_tdata[15:0]};
        assign m_axis_tvalid = rb_valid;
        assign m_axis_tuser  = rb_valid & rb_first;
        assign m_axis_tlast  = rb_valid & rb_last;
    end endgenerate

endmodule
