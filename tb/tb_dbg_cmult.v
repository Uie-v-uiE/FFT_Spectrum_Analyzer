// tb_dbg_cmult.v — 流式驱动前 8 例,逐拍打印中间值,定位流式与单例的差异。
`timescale 1ns/1ps
module tb_dbg_cmult;
    reg clk = 1'b0;
    always #5 clk = ~clk;
    reg rst = 1'b1, en = 1'b0, a_valid = 1'b0;
    reg signed [18:0] a_re, a_im;
    reg signed [17:0] b_re, b_im;
    wire signed [17:0] y_re, y_im;
    wire y_valid;

    fft_cmult3 #(.AW(19), .BW(18), .RSH(18), .YW(18)) dut (
        .clk, .en, .a_re, .a_im, .b_re, .b_im, .a_valid,
        .y_re, .y_im, .y_valid
    );

    reg [35:0] ea;
    reg [35:0] eb;
    reg [31:0] ey;
    integer fd, code, i;

    initial begin
        a_re = 0; a_im = 0; b_re = 0; b_im = 0;
        fd = $fopen("vectors/cmult_tv.hex", "r");
        repeat (4) @(posedge clk);
        rst = 0;
        @(posedge clk);
        for (i = 0; i < 2; i = i + 1) begin
            code = $fscanf(fd, "%h %h %h", ea, eb, ey);
            a_re = ea[17:0]; a_im = ea[35:18];
            b_re = eb[17:0]; b_im = eb[35:18];
            en = 1; a_valid = 1;
            @(posedge clk);
            $display("DRIVE i=%0d ar=%0d ai=%0d br=%0d bi=%0d exp=%h (im=%0d re=%0d)",
                     i, a_re, a_im, b_re, b_im, ey,
                     $signed(ey[31:16]), $signed(ey[15:0]));
        end
        en = 0; a_valid = 0;
        repeat (5) begin
            @(posedge clk);
            $display("DRAIN t=%0t y=(%0d,%0d) yv=%b", $time, dut.y_re, dut.y_im, y_valid);
        end
        repeat (4) begin
            @(posedge clk);
            $display("DUT k1=%0d k2=%0d k3=%0d sre=%0d sim=%0d", dut.k1, dut.k2, dut.k3, dut.sre, dut.sim);
        end
        $finish;
    end
endmodule
