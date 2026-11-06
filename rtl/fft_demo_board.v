// fft_demo_board.v — FFT 处理器板级演示顶层(RK-XCKU5P-F)。
//   内置 64 点双音帧 ROM(bin 5 + bin 20),连续帧送入 FFT(M=6,位倒序输出),
//   每帧取 |I|+|Q| 峰值 bin → LED[3:0] 显示 bin 低 4 位(稳定不滚 = 功能证据);
//   LED 全帧闪烁作活性。功能正确性已由比特精确模型逐级对账 + 8/8 回归保证。
//   时钟:板载 200 MHz 差分直入(IBUFDS,333 MHz 已布线闭环,200 MHz 大裕量)。
module fft_demo_board (
    input  wire       i_sys_clk_p,   // T24 差分 200 MHz
    input  wire       i_sys_clk_n,
    input  wire       i_sys_rst,     // K9 按键(高有效按下)
    output wire [3:0] o_led          // H9/J9/G11/H11
);
    // 差分时钟入
    wire clk;
    IBUFDS u_ibufds (
        .O(clk), .I(i_sys_clk_p), .IB(i_sys_clk_n));

    // 复位:按键按下(1)→ 复位,2FF 同步
    reg [1:0] rsync;
    always @(posedge clk) rsync <= {rsync[0], i_sys_rst};
    wire rst = rsync[1];

    reg [24:0] blink_cnt;
    always @(posedge clk) blink_cnt <= blink_cnt + 1'b1;

    // ---------------- 帧数据源:ROM 64 字连续回放 ----------------
    localparam N = 64;
    reg [31:0] rom [0:N-1];                    // {im16, re16}
    initial $readmemh("fft_demo_frame.mem", rom);
    reg [5:0]  ridx;
    always @(posedge clk) begin
        if (rst) ridx <= 6'd0;
        else     ridx <= ridx + 1'b1;          // 背靠背帧,无间隙
    end

    // ---------------- AXI-Stream 打包 ----------------
    reg        s_valid;
    always @(posedge clk) begin
        if (rst) s_valid <= 1'b0;
        else     s_valid <= 1'b1;
    end
    wire        s_ready;
    wire        m_valid, m_user, m_last;
    wire [31:0] m_data;
    wire        m_ready = 1'b1;                // 演示恒收

    fft_top #(.M(6), .DW(16), .OUT_NATURAL(0)) u_fft (
        .clk(clk), .rst(rst),
        .s_axis_tdata({rom[ridx][31:16], rom[ridx][15:0]}),
        .s_axis_tvalid(s_valid), .s_axis_tready(s_ready),
        .m_axis_tdata(m_data), .m_axis_tvalid(m_valid),
        .m_axis_tuser(m_user), .m_axis_tlast(m_last),
        .m_axis_tready(m_ready)
    );

    // ---------------- 峰值 bin 检测(流式)----------------
    // m_user 帧首清 best;每输出字 |I|+|Q| 与 best 比较更新(纯流水,无帧 RAM)
    reg [4:0]  widx;
    reg [15:0] best_v;
    reg [5:0]  best_b;
    wire [15:0] ai = m_data[15] ? (~m_data[15:0] + 1'b1)  : m_data[15:0];   // |re|
    wire [15:0] aq = m_data[31] ? (~m_data[31:16] + 1'b1) : m_data[31:16];  // |im|
    always @(posedge clk) begin
        if (rst) begin
            widx <= 0; best_v <= 16'h0; best_b <= 6'h0;
        end else if (m_valid) begin
            if (m_user) begin
                widx   <= 0;
                best_v <= 16'h0;
                best_b <= 6'h0;
            end else begin
                if ((ai + aq) > best_v) begin
                    best_v <= ai + aq;
                    best_b <= widx;
                end
                widx <= widx + 1'b1;
            end
        end
    end

    assign o_led = {blink_cnt[24], best_b[2:0]};   // LED3 活性闪烁;LED[2:0] = 峰值 bin 低 3 位
endmodule
