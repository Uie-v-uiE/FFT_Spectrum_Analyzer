// fft_reorder.v — 位倒序 → 自然序 ping-pong 重排序缓冲。
// 写:帧内位置 opos 写入 bank[bitrev(opos)];帧满(帧尾)切换写 bank;
// 读:对已完成的另一 bank 线性读出,读指针与写帧对齐(各 N 拍)。
// 首帧未完成前 y_valid=0。延迟 = N 拍。

module fft_reorder #(
    parameter M  = 12,
    parameter DW = 16,
    parameter AW = DW + 1
)(
    input  wire             clk,
    input  wire             rst,
    input  wire             en,
    input  wire [2*AW-1:0]  x_tdata,
    input  wire [M-1:0]     x_pos,      // 帧内位置 0..N-1(N=2^M,位宽恰为 M)
    input  wire             x_valid,
    output reg  [2*AW-1:0]  y_tdata,
    output reg              y_valid,
    output reg              y_first,
    output reg              y_last
);
    localparam N  = 1 << M;
    localparam OW = M;                     // N=2^M → 位倒序宽度恰为 M
    localparam [OW-1:0] N_M1 = N - 1;

    function integer f_clog2p1(input integer v);
        integer vv;
        begin
            f_clog2p1 = 0;
            for (vv = v - 1; vv > 0; vv = vv >> 1) f_clog2p1 = f_clog2p1 + 1;
        end
    endfunction

    function [OW-1:0] bitrev(input [OW-1:0] a);
        integer i;
        begin
            for (i = 0; i < OW; i = i + 1) bitrev[i] = a[OW-1-i];
        end
    endfunction

    reg             wr_bank;    // 当前写 bank(0/1)
    reg             rd_bank;    // 当前可读 bank(已完成帧)
    reg             started;
    reg [OW-1:0]    rptr;
    reg             dv, df, dl;

    (* ram_style = "block" *)
    reg [2*AW-1:0] mem0 [0:N-1];
    (* ram_style = "block" *)
    reg [2*AW-1:0] mem1 [0:N-1];

    integer zi;
    initial begin
        wr_bank = 1'b0; rd_bank = 1'b0; started = 1'b0; rptr = {OW{1'b0}};
        dv = 1'b0; df = 1'b0; dl = 1'b0; y_tdata = {2*AW{1'b0}};
        y_valid = 1'b0; y_first = 1'b0; y_last = 1'b0;
        for (zi = 0; zi < N; zi = zi + 1) begin
            mem0[zi] = {2*AW{1'b0}}; mem1[zi] = {2*AW{1'b0}};
        end
    end

    wire frame_last_in = x_valid && (x_pos == N_M1);

    always @(posedge clk) begin
        if (rst) begin
            wr_bank <= 1'b0; rd_bank <= 1'b0; started <= 1'b0; rptr <= {OW{1'b0}};
            dv <= 1'b0; df <= 1'b0; dl <= 1'b0;
        end else if (en) begin
            // 写
            if (x_valid) begin
                if (!wr_bank) mem0[bitrev(x_pos)] <= x_tdata;
                else          mem1[bitrev(x_pos)] <= x_tdata;
            end
            // 帧满切换
            if (frame_last_in) begin
                started <= 1'b1;
                rd_bank <= wr_bank;         // 刚完成的帧所在 bank
                wr_bank <= ~wr_bank;
            end
            // 读(与写帧相位对齐,各 N 拍)
            if (started) begin
                rptr <= (rptr == N_M1) ? {OW{1'b0}} : rptr + 1'b1;
                if (rptr == N_M1) rd_bank <= ~rd_bank;
                y_tdata <= rd_bank ? mem1[rptr] : mem0[rptr];
                dv <= 1'b1; df <= (rptr == {OW{1'b0}}); dl <= (rptr == N_M1);
            end else begin
                dv <= 1'b0;
            end
        end
    end

    assign y_valid = dv;
    assign y_first = df;
    assign y_last  = dl;

endmodule
