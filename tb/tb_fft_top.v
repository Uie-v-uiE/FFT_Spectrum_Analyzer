// tb_fft_top.v — fft_top 全核自检 TB(比特精确)。
// plusargs:+M=<log2N> +INFILE=<path> +OUTFILE=<path> +GAP=<0/1 随机停拍> [+NATURAL=<0/1>]
//   INFILE : 18N 个 32b 字(tdata={im,re},帧主序),golden 生成;
//   OUTFILE: 18N 个 32b 字(位倒序输出流,warm 模式,全部帧有效)。
// 驱动:GAP=1 时 ~30% 拍撒 tvalid 停拍(源保持数据,符合 AXI-S)。
// 校验:先按首字搜索对齐(容许 warmup),随后全流逐位比对;错误>0 即 FAIL。
`timescale 1ns/1ps
module tb_fft_top #(
    parameter M_P      = 6,     // vsim -gM_P=<log2N> 覆盖
    parameter NAT_P    = 0      // vsim -gNAT_P=1 自然序
)(
);
    reg [1023:0] infile, outfile;

    localparam DW = 16;
    localparam MAXN = 1 << 12;
    localparam MAXW = 18 * MAXN;               // 18 帧 × 4096

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg         rst = 1'b1;
    reg [2*DW-1:0] s_tdata;
    reg         s_valid;
    wire        s_ready;
    wire [2*DW-1:0] m_tdata;
    wire        m_valid, m_user, m_last;
    reg         m_ready = 1'b1;

    fft_top #(
        .M(M_P), .DW(DW), .OUT_NATURAL(NAT_P)
    ) dut (
        .clk, .rst,
        .s_axis_tdata(s_tdata), .s_axis_tvalid(s_valid), .s_axis_tready(s_ready),
        .m_axis_tdata(m_tdata), .m_axis_tvalid(m_valid),
        .m_axis_tuser(m_user), .m_axis_tlast(m_last),
        .m_axis_tready(m_ready)
    );

    // 输入/期望
    reg [31:0] in_mem  [0:MAXW-1];
    reg [31:0] exp_mem [0:MAXW-1];
    reg [31:0] got_mem [0:MAXW-1];
    integer    n_in, n_got, n_exp;

    // 随机停拍
    integer seed;
    integer gap_en, gap_cnt;

    // 采集
    always @(posedge clk) begin
        if (m_valid && m_ready && n_got < MAXW) begin
            got_mem[n_got] <= m_tdata;
            n_got <= n_got + 1;
        end
    end

    integer mcnt;
    initial mcnt = 0;
    always @(posedge clk) if (!rst && mcnt < 260) begin
        mcnt <= mcnt + 1;
        $display("L1ST k=%0d x_im=%0d pr_im=%0d s_im=%0d simsa=%b out=%h",
                 mcnt, $signed(dut.g_stages[1].u_st.x_im),
                 $signed(dut.g_stages[1].u_st.pr_im),
                 $signed(dut.g_stages[1].u_st.s_im),
                 dut.g_stages[1].u_st.sat_im, dut.g_stages[1].u_st.y_tdata);
    end
    // 逐级探针(级定位用):lvl_mem[l][c] = 第 l 级输出在绝对周期 c 的值
    wire [2*DW+1:0] lv_tdata [0:M_P-1];
    wire            lv_valid [0:M_P-1];
    genvar gp;
    generate
        for (gp = 0; gp < M_P; gp = gp + 1) begin : g_probe
            assign lv_tdata[gp] = dut.g_stages[gp].u_st.y_tdata;
            assign lv_valid[gp] = dut.g_stages[gp].u_st.y_valid;
        end
    endgenerate
    reg [31:0] lvl_mem [0:M_P-1][0:4095];
    reg [15:0] lvl_cyc [0:M_P-1];
    integer    gi;
    initial begin
        for (gi = 0; gi < M_P; gi = gi + 1) lvl_cyc[gi] = 16'h0;
    end
    integer dbg_cnt;
    initial dbg_cnt = 0;
    always @(posedge clk) begin
        if (!rst) begin
            for (gi = 0; gi < M_P; gi = gi + 1) begin
                if (lv_valid[gi] && lvl_cyc[gi] < 4095) begin
                    lvl_mem[gi][lvl_cyc[gi]] <= {lv_tdata[gi][2*DW-1:DW], lv_tdata[gi][DW-1:0]};
                    if (gi == 5 && dbg_cnt < 16)
                        $display("PROBE t=%0t L5 cap#%0d val=%h (pre-edge valid)", $time, lvl_cyc[gi], lv_tdata[gi]);
                    lvl_cyc[gi] <= lvl_cyc[gi] + 1'b1;
                end
            end
            if (lv_valid[5]) dbg_cnt <= dbg_cnt + 1;
            if (dbg_cnt >= 88 && dbg_cnt <= 96)
                $display("L1I t=%0t fh_sel=%b raw_f=%h diff_f=%h sr_front=%h out=%h",
                         $time, dut.g_stages[1].u_st.fh_sel,
                         dut.g_stages[1].u_st.raw_f, dut.g_stages[1].u_st.diff_f,
                         dut.g_stages[1].u_st.sr_front_w,
                         dut.g_stages[1].u_st.y_tdata);
                $display("CYC t=%0t L0: p=%0d fh=%b x=(%0d,%0d) out=(%0d,%0d) v=%b",
                         $time, dut.g_stages[0].u_st.p, dut.g_stages[0].u_st.fh_now,
                         dut.g_stages[0].u_st.x_im, dut.g_stages[0].u_st.x_re,
                         dut.g_stages[0].u_st.y_tdata[31:16], dut.g_stages[0].u_st.y_tdata[15:0],
                         lv_valid[0]);
                if (gi == 0)
                    $display("L0DBG t=%0t partner=(%0d,%0d) sre=%0d sim=%0d",
                             $time, dut.g_stages[0].u_st.g_srN.fr[15:0], dut.g_stages[0].u_st.g_srN.fr[31:16],
                             dut.g_stages[0].u_st.u_cmult.sre, dut.g_stages[0].u_st.u_cmult.sim);
        end
    end
    integer i, errors, off, j, fd, code, anch, fo, f4;
    reg match;

    initial begin
        // plusargs(M/NATURAL 为 elaboration 参数,经 vsim -g 覆盖)
        if (!$value$plusargs("GAP=%d", gap_en))       gap_en = 0;
        if (!$value$plusargs("SEED=%d", seed))        seed = 7;
        if (!$value$plusargs("INFILE=%s", infile))    infile = "all_N64_in.hex";
        if (!$value$plusargs("OUTFILE=%s", outfile))  outfile = "all_N64_out.hex";

        s_tdata = 0; s_valid = 0; m_ready = 1;
        n_got = 0; n_in = 0; n_exp = 0;
        gap_cnt = 0;

        // 装载
        fd = $fopen(infile, "r");
        if (fd == 0) begin $display("TB FAIL: open %0s", infile); $finish; end
        while ($fscanf(fd, "%h", in_mem[n_in]) == 1) n_in = n_in + 1;
        $fclose(fd);
        fd = $fopen(outfile, "r");
        if (fd == 0) begin $display("TB FAIL: open %0s", outfile); $finish; end
        while ($fscanf(fd, "%h", exp_mem[n_exp]) == 1) n_exp = n_exp + 1;
        $fclose(fd);
        $display("TB: M=%0d in=%0d exp=%0d gap=%0d natural=%0d seed=%0d",
                 M_P, n_in, n_exp, gap_en, NAT_P, seed);

        repeat (8) @(posedge clk);
        rst = 0;
        @(posedge clk);

        // 驱动(真实输入):AXI-S 语义——停拍时源保持数据与 valid,被接受才推进
        i = 0;
        while (i < n_in) begin
            s_tdata = in_mem[i];
            if (gap_en && (({$random(seed)} % 10) < 3)) begin
                s_valid = 1'b0;                     // 停拍一拍(数据保持)
                @(posedge clk);
            end else begin
                s_valid = 1'b1;
                @(posedge clk);
                if (s_ready === 1'b1) i = i + 1;    // 被接受才推进
            end
        end
        // 冲刷帧:2N 个零字,把尾帧输出推出来(与模型 run_stream 的冲刷一致)
        s_tdata = 0;
        for (i = 0; i < 2 * (1 << M_P); i = i + 1) begin
            s_valid = 1'b1;
            @(posedge clk);
        end
        s_valid = 1'b0;

        // 等采集完成(超时看门狗)
        j = 0;
        while (n_got < n_exp && j < 40 * MAXN) begin
            @(posedge clk);
            j = j + 1;
        end

        // 自然序模式:期望流按位倒序自反置换(位倒序为自反置换)
        if (NAT_P == 1) begin : perm
            reg [31:0] tmp;
            integer a, b, mm;
            for (a = 0; a < (1 << M_P); a = a + 1) begin
                b = 0;
                for (mm = 0; mm < M_P; mm = mm + 1)
                    b[mm] = a[M_P-1-mm];
                if (b > a) begin           // 只交换一次(位倒序自反,避免二次交换抵消)
                    tmp = exp_mem[a];
                    exp_mem[a] = exp_mem[b];
                    exp_mem[b] = tmp;
                end
            end
        end

        // 对齐:门控起点即契约起点(FIRST_VALID = 2N-1+M),确定性 off=0
        off = 0;
        $display("TB: aligned (deterministic off=%0d)", off);

        // 全量逐位比对
        errors = 0;
        for (i = 0; i < n_exp; i = i + 1) begin
            if (off + i >= n_got) begin
                $display("TB FAIL: stream ended early at exp %0d", i);
                errors = errors + 1;
                i = n_exp;
            end else if (got_mem[off+i] !== exp_mem[i]) begin
                if (errors < 8)
                    $display("TB mismatch at %0d: got %h exp %h", i, got_mem[off+i], exp_mem[i]);
                errors = errors + 1;
            end
        end
        // 落盘全流供 Python 对账
        begin
            fo = $fopen("sim/got_dump.hex", "w");
            for (i = 0; i < n_got; i = i + 1) $fwrite(fo, "%h
", got_mem[i]);
            $fclose(fo);
        end
        begin
            f4 = $fopen("sim/got_lvl0.hex", "w");
            for (i = 0; i < lvl_cyc[0]; i = i + 1) $fwrite(f4, "%h
", lvl_mem[0][i]);
            $fclose(f4);
            f4 = $fopen("sim/got_lvl1.hex", "w");
            for (i = 0; i < lvl_cyc[1]; i = i + 1) $fwrite(f4, "%h
", lvl_mem[1][i]);
            $fclose(f4);
            f4 = $fopen("sim/got_lvl2.hex", "w");
            for (i = 0; i < lvl_cyc[2]; i = i + 1) $fwrite(f4, "%h
", lvl_mem[2][i]);
            $fclose(f4);
            f4 = $fopen("sim/got_lvl3.hex", "w");
            for (i = 0; i < lvl_cyc[3]; i = i + 1) $fwrite(f4, "%h
", lvl_mem[3][i]);
            $fclose(f4);
            f4 = $fopen("sim/got_lvl4.hex", "w");
            for (i = 0; i < lvl_cyc[4]; i = i + 1) $fwrite(f4, "%h
", lvl_mem[4][i]);
            $fclose(f4);
            f4 = $fopen("sim/got_lvl5.hex", "w");
            for (i = 0; i < lvl_cyc[5]; i = i + 1) $fwrite(f4, "%h
", lvl_mem[5][i]);
            $fclose(f4);
        end
        if (errors == 0)
            $display("FFT TOP SELF-CHECK PASS (M=%0d words=%0d aligned+%0d)", M_P, n_exp, off);
        else
            $display("FFT TOP SELF-CHECK FAIL (M=%0d, %0d errors)", M_P, errors);
        $finish;
    end

    // 看门狗(绝对)
    initial begin
        #200_000_000;  // 200ms 仿真时间上限
        $display("TB FAIL: global timeout (n_got=%0d)", n_got);
        $finish;
    end
endmodule
