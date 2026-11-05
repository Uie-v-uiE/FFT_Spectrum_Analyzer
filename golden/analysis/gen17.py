# -*- coding: utf-8 -*-
"""I-08 终局:fft_stage/fft_top/fft_reorder/TB 的 17 位 SR 全路径转换器。
从 5fccc31 基线(32 位)机械替换 + 逐段 assert,产出 34 位版。
位号对照表(34 位 x_tdata / fr / sr_in):
  [16:0]  = re17、[33:17] = im17
  sr_in   = fh_sel ? x_tdata(34, raw 全精度) : {cm_im[16:0], cm_re[16:0]}(或 TRIVIAL tr 扩展)
  partner = S>0 ? fr 全 34 : x_tdata;pr_re = w[16:0]、pr_im = w[33:17]
  fh 段输出 = fr 全 34(out_r/y_tdata 34 位级间;末级 reorder 后由 fft_top 截 16)"""
import sys

def load(p):
    return open(p, encoding='utf-8').read()

def save(p, s):
    open(p, 'w', encoding='utf-8').write(s)

class Trans:
    def __init__(self, s):
        self.s = s
        self.n = 0
    def rep(self, old, new):
        assert self.s.count(old) == 1, "count=%d NOT UNIQUE: %r" % (self.s.count(old), old[:70])
        self.s = self.s.replace(old, new)
        self.n += 1

# ---------- fft_stage.v ----------
t = Trans(load('rtl/fft_stage.v'))
t.rep("""    parameter M  = 12,
    parameter L  = 0,
    parameter DW = 16
)(""",
"""    parameter M  = 12,
    parameter L  = 0,
    parameter DW = 16,
    parameter AW = DW + 1
)(""")
t.rep("    localparam AW = DW + 1;\n", "")
t.rep("    input  wire [2*DW-1:0]  x_tdata,    // {im, re}",
      "    input  wire [2*AW-1:0]  x_tdata,    // {im17, re17} 全精度级间")
t.rep("    output wire [2*DW-1:0]  y_tdata,",
      "    output wire [2*AW-1:0]  y_tdata,")
t.rep("""    wire signed [DW-1:0] x_re = x_tdata[DW-1:0];
    wire signed [DW-1:0] x_im = x_tdata[2*DW-1:DW];""",
"""    wire signed [AW-1:0] x_re = x_tdata[AW-1:0];
    wire signed [AW-1:0] x_im = x_tdata[2*AW-1:AW];""")
t.rep("    reg [2*DW-1:0] rp0, rp1, rp2;", "    reg [2*AW-1:0] rp0, rp1, rp2;")
t.rep("        rp0 = {2*DW{1'b0}}; rp1 = {2*DW{1'b0}}; rp2 = {2*DW{1'b0}};",
      "        rp0 = {2*AW{1'b0}}; rp1 = {2*AW{1'b0}}; rp2 = {2*AW{1'b0}};")
t.rep("            rp0 <= rp1;  rp1 <= rp2;  rp2 <= fh_now ? x_tdata : {2*DW{1'b0}};",
      "            rp0 <= rp1;  rp1 <= rp2;  rp2 <= fh_now ? x_tdata : {2*AW{1'b0}};")
t.rep("            rp0 <= fh_now ? x_tdata : {2*DW{1'b0}};",
      "            rp0 <= fh_now ? x_tdata : {2*AW{1'b0}};")
t.rep("    wire [2*DW-1:0] raw_f = rp0;", "    wire [2*AW-1:0] raw_f = rp0;")
t.rep("""    wire [2*DW-1:0] partner_w = (S > 0) ? sr_front_w : raw_f;
    wire signed [AW-1:0] pr_re = {{(AW-DW){partner_w[DW-1]}}, partner_w[DW-1:0]};
    wire signed [AW-1:0] pr_im = {{(AW-DW){partner_w[2*DW-1]}}, partner_w[2*DW-1:DW]};""",
"""    wire [2*AW-1:0] partner_w = (S > 0) ? sr_front_w : x_tdata;
    wire signed [AW-1:0] pr_re = partner_w[AW-1:0];           // re17 = [16:0]
    wire signed [AW-1:0] pr_im = partner_w[2*AW-1:AW];        // im17 = [33:17]""")
t.rep("    assign sr_in = fh_sel ? raw_f : diff_f;",
"""    assign sr_in = fh_sel ? raw_f
                         : TRIVIAL ? {tr_y_im[DW-1], tr_y_im[DW-1:0],
                                      tr_y_re[DW-1], tr_y_re[DW-1:0]}
                                   : {cm_im[AW-1:0], cm_re[AW-1:0]};""")
t.rep("        reg [2*DW-1:0] fr;\n        initial fr = {2*DW{1'b0}};",
      "        reg [2*AW-1:0] fr;\n        initial fr = {2*AW{1'b0}};")
t.rep("        reg [2*DW-1:0] mem [0:S-1];\n        reg [AWD-1:0]  wptr;\n        reg [2*DW-1:0] fr;",
      "        reg [2*AW-1:0] mem [0:S-1];\n        reg [AWD-1:0]  wptr;\n        reg [2*AW-1:0] fr;")
t.rep("            fr = {2*DW{1'b0}}; wptr = {AWD{1'b0}};\n            for (zi = 0; zi < S; zi = zi + 1) mem[zi] = {2*DW{1'b0}};",
      "            fr = {2*AW{1'b0}}; wptr = {AWD{1'b0}};\n            for (zi = 0; zi < S; zi = zi + 1) mem[zi] = {2*AW{1'b0}};")
t.rep("            mem[wptr] <= sr_in;", "            mem[wptr] <= sr_in;")
t.rep("        always @(posedge clk) if (en) fr <= sr_in;",
      "        always @(posedge clk) if (en) fr <= sr_in;")
t.rep("    end else begin : g_sr0\n        assign sr_front_w = {2*DW{1'b0}};\n    end endgenerate",
      "    end else begin : g_sr0\n        assign sr_front_w = {2*AW{1'b0}};\n    end endgenerate")
t.rep("""    wire [2*DW-1:0] out_c = fh_now ? ((S > 0) ? sr_front_w : diff_f)
                                   : {ad_im, ad_re};
    reg [2*DW-1:0] out_r;""",
"""    // fh 段输出 fr 全 34 位透传(级间全精度;末级 reorder 后由 fft_top 截 16)
    wire [2*AW-1:0] out_c = fh_now ? ((S > 0) ? sr_front_w
                                              : {{(AW-DW+1){diff_f[2*DW-1]}}, diff_f[2*DW-1:DW],
                                                 {(AW-DW+1){diff_f[DW-1]}}, diff_f[DW-1:0]})
                                   : {{(AW-DW+1){ad_im[DW-1]}}, ad_im[DW-1:0],
                                      {(AW-DW+1){ad_re[DW-1]}}, ad_re[DW-1:0]};
    reg [2*AW-1:0] out_r;""")
t.rep("        out_r = {2*DW{1'b0}}; out_v = 1'b0;", "        out_r = {2*AW{1'b0}}; out_v = 1'b0;")
save('rtl/fft_stage.v', t.s)
print("fft_stage.v: %d 处替换" % t.n)

# ---------- fft_top.v ----------
t = Trans(load('rtl/fft_top.v'))
t.rep("    wire [2*DW-1:0] lk_tdata [0:M];",
      "    localparam AWL = DW + 1;\n    wire [2*AWL-1:0] lk_tdata [0:M];")
t.rep("    assign lk_tdata[0]  = s_axis_tdata;",
"""    assign lk_tdata[0]  = {s_axis_tdata[2*DW-1], s_axis_tdata[2*DW-1:DW],
                           s_axis_tdata[DW-1], s_axis_tdata[DW-1:0]};""")
t.rep("    wire [2*DW-1:0] raw_tdata = lk_tdata[M];",
      "    wire [2*AWL-1:0] raw_tdata = lk_tdata[M];")
t.rep("fft_reorder #(.M(M), .DW(DW)) u_reorder (",
      "fft_reorder #(.M(M), .DW(DW), .AW(AWL)) u_reorder (")
t.rep("        assign m_axis_tdata  = raw_tdata;",
      "        assign m_axis_tdata  = {raw_tdata[2*AWL-2:AWL], raw_tdata[DW-1:0]};")
t.rep("        assign m_axis_tdata  = rb_tdata;",
      "        assign m_axis_tdata  = {rb_tdata[2*AWL-2:AWL], rb_tdata[DW-1:0]};")
save('rtl/fft_top.v', t.s)
print("fft_top.v: %d 处替换" % t.n)

# ---------- fft_reorder.v ----------
t = Trans(load('rtl/fft_reorder.v'))
t.rep("    parameter DW = 16", "    parameter DW = 16,\n    parameter AW = DW + 1")
t.rep("    input  wire [2*DW-1:0]  x_tdata,", "    input  wire [2*AW-1:0]  x_tdata,")
t.rep("    output reg  [2*DW-1:0]  y_tdata,", "    output reg  [2*AW-1:0]  y_tdata,")
t.rep("    reg [2*DW-1:0] mem0 [0:N-1];", "    reg [2*AW-1:0] mem0 [0:N-1];")
t.rep("    reg [2*DW-1:0] mem1 [0:N-1];", "    reg [2*AW-1:0] mem1 [0:N-1];")
t.rep("        dv = 1'b0; df = 1'b0; dl = 1'b0; y_tdata = {2*DW{1'b0}};",
      "        dv = 1'b0; df = 1'b0; dl = 1'b0; y_tdata = {2*AW{1'b0}};")
t.rep("            mem0[zi] = {2*DW{1'b0}}; mem1[zi] = {2*DW{1'b0}};",
      "            mem0[zi] = {2*AW{1'b0}}; mem1[zi] = {2*AW{1'b0}};")
save('rtl/fft_reorder.v', t.s)
print("fft_reorder.v: %d 处替换" % t.n)

# ---------- tb_fft_top.v ----------
t = Trans(load('tb/tb_fft_top.v'))
t.rep("    wire [2*DW-1:0] lv_tdata [0:M_P-1];",
      "    wire [2*DW+1:0] lv_tdata [0:M_P-1];")
t.rep("                    lvl_mem[gi][lvl_cyc[gi]] <= lv_tdata[gi];",
      "                    lvl_mem[gi][lvl_cyc[gi]] <= {lv_tdata[gi][2*DW-1:DW], lv_tdata[gi][DW-1:0]};")
save('tb/tb_fft_top.v', t.s)
print("tb_fft_top.v: %d 处替换" % t.n)
