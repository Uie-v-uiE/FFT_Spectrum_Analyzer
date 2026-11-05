// tb_fft_cmult3.v — 3-DSP 高斯复乘单元自检 TB。
// 向量 cmult_tv.hex:每行 a_p b_p y_p(a={ai,ar} 34b;b={bi,br} 36b;y={yi,yr} 32b),
// 由 golden 模型生成。驱动 8192 例,采集输出后逐一比对,报告 PASS/FAIL。
`timescale 1ns/1ps
module tb_fft_cmult3;
    localparam NCASE = 8192;
    localparam DW16 = 16;   // 期望向量场宽(17bit 输出的符号冗余位丢弃,与模型一致)

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg        rst = 1'b1;
    reg        en = 1'b0;
    reg        a_valid = 1'b0;
    reg signed [18:0] a_re, a_im;
    reg signed [17:0] b_re, b_im;
    wire signed [17:0] y_re, y_im;
    wire        y_valid;

    fft_cmult3 #(.AW(19), .BW(18), .RSH(18), .YW(18)) dut (
        .clk, .en, .a_re, .a_im, .b_re, .b_im, .a_valid,
        .y_re, .y_im, .y_valid
    );

    reg  [31:0] exp_arr [0:NCASE-1];
    reg  [31:0] got_arr [0:NCASE-1];
    integer     n_got;

    initial n_got = 0;
    always @(posedge clk) begin
        if (y_valid && n_got < NCASE) begin
            got_arr[n_got] <= {y_im[DW16-1:0], y_re[DW16-1:0]};
            if (n_got < 3)
                $display("CAP n=%0d t=%0t y_im=%0d y_re=%0d packed=%h",
                         n_got, $time, y_im, y_re, {y_im[15:0], y_re[15:0]});
            n_got          <= n_got + 1;
        end
    end

    integer i, errors, fd, code;
    reg [35:0] ea;
    reg [35:0] eb;
    reg [31:0] ey;

    initial begin
        a_re = 0; a_im = 0; b_re = 0; b_im = 0;
        repeat (4) @(posedge clk);
        rst = 0;
        @(posedge clk);

        fd = $fopen("vectors/cmult_tv.hex", "r");
        if (fd == 0) begin
            $display("CMULT FAIL: cannot open vectors/cmult_tv.hex");
            $finish;
        end
        for (i = 0; i < NCASE; i = i + 1) begin
            code = $fscanf(fd, "%h %h %h", ea, eb, ey);
            if (code != 3) begin
                $display("CMULT FAIL: parse error at case %0d", i);
                $finish;
            end
            exp_arr[i] = ey;
            a_re    = {{1{ea[17]}},  ea[17:0]};    // 18 位位选赋 19 位 reg:须显式符号扩展
            a_im    = {{1{ea[35]}},  ea[35:18]};
            b_re    = eb[17:0];
            b_im    = eb[35:18];
            en      = 1'b1;
            a_valid = 1'b1;
            @(posedge clk);
        end
        // 流水冲刷:保持 en=1、a_valid=0 三拍,让最后 3 例输出流出,再停 en
        a_valid = 1'b0;
        repeat (3) @(posedge clk);
        en = 1'b0;
        $fclose(fd);

        // 等待流水排空(上限 100 拍)
        i = 0;
        while (n_got < NCASE && i < 100) begin
            @(posedge clk);
            i = i + 1;
        end

        errors = 0;
        for (i = 0; i < NCASE; i = i + 1) begin
            if (got_arr[i] !== exp_arr[i]) begin
                if (errors < 8)
                    $display("CMULT case %0d mismatch: got %h exp %h", i, got_arr[i], exp_arr[i]);
                errors = errors + 1;
            end
        end
        if (errors == 0) $display("CMULT SELF-CHECK PASS (%0d cases)", NCASE);
        else             $display("CMULT SELF-CHECK FAIL (%0d/%0d errors)", errors, NCASE);
        $finish;
    end
endmodule
