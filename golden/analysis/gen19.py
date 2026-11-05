# -*- coding: utf-8 -*-
"""I-08 终版:fft 全链 38 位字(2x19)SR 值域转换器。
从 5fccc31 基线机械转换 + 逐段 assert。
位号对照(38 位 x_tdata/fr/sr_in = {im19[18:0], re19[18:0]}):
  [18:0] = re19、[37:19] = im19
  sr_in  = fh_sel ? x_tdata(38) : TRIVIAL ? tr 扩 19 : {cm_im[18:0], cm_re[18:0]}
  partner= S>0 ? fr 全 38 : x_tdata;pr_re = w[18:0]、pr_im = w[37:19]
  d/s    = 20 位([SW:0]);sb = 21 位;sat = s[19:15] 五位统一判定
  ad     = sat ? -32768/32767 : sb[16:1](16 位,黄金 min/max 语义)
  fh 段输出 = fr 全 38 透传(级间全精度);末级 fft_top 重组 32 位出"""

def load(p): return open(p, encoding='utf-8').read()
def save(p, s): open(p, 'w', encoding='utf-8').write(s)

class T:
    def __init__(self, s):
        self.s = s; self.n = 0
    def rep(self, old, new):
        assert self.s.count(old) == 1, "count=%d NOT UNIQUE: %r" % (self.s.count(old), old[:70])
        self.s = self.s.replace(old, new); self.n += 1

# ============ fft_cmult3.v:y 端口 19 位 ============
t = T(load('rtl/fft_cmult3.v'))
t.rep("""    output reg  signed [AW-1:0]    y_re,     // t+3 拍
    output reg  signed [AW-1:0]    y_im,""",
"""    output reg  signed [YW-1:0]    y_re,     // t+3 拍(19 位全精度,黄金 conv18 未截)
    output reg  signed [YW-1:0]    y_im,""")
t.rep("    output reg                     y_valid\n);",
      "    output reg                     y_valid,\n    parameter YW = 19\n);")
t.rep("""    always @(posedge clk) if (en) begin
        y_re    <= sre_b[PW-1:RSH];
        y_im    <= sim_b[PW-1:RSH];
        y_valid <= v2;
    end""",
"""    always @(posedge clk) if (en) begin
        y_re    <= sre_b[PW-1:RSH];      // [36:18] = 19 位全精度
        y_im    <= sim_b[PW-1:RSH];
        y_valid <= v2;
    end""")
save('rtl/fft_cmult3.v', t.s); print("fft_cmult3:", t.n)

# ============ fft_stage.v:全链 38 位 ============
t = T(load('rtl/fft_stage.v'))
t.rep("""    parameter M  = 12,
    parameter L  = 0,
    parameter DW = 16
)(""",
"""    parameter M  = 12,
    parameter L  = 0,
    parameter DW = 16,
    parameter SW = 19
)(""")
t.rep("    input  wire [2*DW-1:0]  x_tdata,    // {im, re}",
      "    input  wire [2*SW-1:0]  x_tdata,    // {im19, re19} 全精度级间")
t.rep("    output wire [2*DW-1:0]  y_tdata,",
      "    output wire [2*SW-1:0]  y_tdata,")
t.rep("""    wire signed [DW-1:0] x_re = x_tdata[DW-1:0];
    wire signed [DW-1:0] x_im = x_tdata[2*DW-1:DW];""",
"""    wire signed [SW-1:0] x_re = x_tdata[SW-1:0];
    wire signed [SW-1:0] x_im = x_tdata[2*SW-1:SW];""")
t.rep("    reg [2*DW-1:0] rp0, rp1, rp2;", "    reg [2*SW-1:0] rp0, rp1, rp2;")
t.rep("        rp0 = {2*DW{1'b0}}; rp1 = {2*DW{1'b0}}; rp2 = {2*DW{1'b0}};",
      "        rp0 = {2*SW{1'b0}}; rp1 = {2*SW{1'b0}}; rp2 = {2*SW{1'b0}};")
t.rep("            rp0 <= rp1;  rp1 <= rp2;  rp2 <= fh_now ? x_tdata : {2*DW{1'b0}};",
      "            rp0 <= rp1;  rp1 <= rp2;  rp2 <= fh_now ? x_tdata : {2*SW{1'b0}};")
t.rep("            rp0 <= fh_now ? x_tdata : {2*DW{1'b0}};",
      "            rp0 <= fh_now ? x_tdata : {2*SW{1'b0}};")
t.rep("    wire [2*DW-1:0] raw_f = rp0;", "    wire [2*SW-1:0] raw_f = rp0;")
t.rep("""    wire [2*DW-1:0] partner_w = (S > 0) ? sr_front_w : raw_f;
    wire signed [AW-1:0] pr_re = {{(AW-DW){partner_w[DW-1]}}, partner_w[DW-1:0]};
    wire signed [AW-1:0] pr_im = {{(AW-DW){partner_w[2*DW-1]}}, partner_w[2*DW-1:DW]};""",
"""    wire [2*SW-1:0] partner_w = (S > 0) ? sr_front_w : raw_f;
    wire signed [SW-1:0] pr_re = partner_w[SW-1:0];           // re19 = [18:0]
    wire signed [SW-1:0] pr_im = partner_w[2*SW-1:SW];        // im19 = [37:19]""")
t.rep("""    wire signed [AW-1:0] xr_re = {{(AW-DW){x_re[DW-1]}}, x_re};
    wire signed [AW-1:0] xr_im = {{(AW-DW){x_im[DW-1]}}, x_im};""",
"""    wire signed [SW-1:0] xr_re = x_re;
    wire signed [SW-1:0] xr_im = x_im;""")
t.rep("""    wire signed [AW-1:0] d_re = pr_re - xr_re;             // DIF: d = a − b(a=先存)
    wire signed [AW-1:0] d_im = pr_im - xr_im;
    wire signed [AW-1:0] s_re = xr_re + pr_re;
    wire signed [AW-1:0] s_im = xr_im + pr_im;""",
"""    wire signed [SW:0] d_re = pr_re - xr_re;               // DIF: d = a − b(a=先存)
    wire signed [SW:0] d_im = pr_im - xr_im;
    wire signed [SW:0] s_re = xr_re + pr_re;
    wire signed [SW:0] s_im = xr_im + pr_im;""")
# 加法路:sb 21 位 + sat 五位统一判定 + ad 16 位饱和
t.rep("    wire signed [AW:0] sb_re0 = {s_re[AW-1], s_re} + {{AW{1'b0}}, s_re[1]};",
      "    wire signed [SW+1:0] sb_re0 = {s_re[SW], s_re} + {{SW{1'b0}}, s_re[1]};")
t.rep("    wire signed [AW:0] sb_im0 = {s_im[AW-1], s_im} + {{AW{1'b0}}, s_im[1]};",
      "    wire signed [SW+1:0] sb_im0 = {s_im[SW], s_im} + {{SW{1'b0}}, s_im[1]};")
t.rep("    wire sat_re = sb_re0[AW] ^ sb_re0[AW-1];",
      "    wire sat_re = (s_re[SW] ^ s_re[SW-1]) | (s_re[SW-1] ^ s_re[SW-2]) | (s_re[SW-2] ^ s_re[SW-3]) | (s_re[SW-3] ^ s_re[SW-4]);")
t.rep("    wire sat_im = sb_im0[AW] ^ sb_im0[AW-1];",
      "    wire sat_im = (s_im[SW] ^ s_im[SW-1]) | (s_im[SW-1] ^ s_im[SW-2]) | (s_im[SW-2] ^ s_im[SW-3]) | (s_im[SW-3] ^ s_im[SW-4]);")
t.rep("    wire signed [DW-1:0] ad_re = sat_re ? (sb_re0[AW] ? -32768 : 32767) : sb_re0[DW:1];",
      "    wire signed [DW-1:0] ad_re = sat_re ? (s_re[SW] ? -32768 : 32767) : sb_re0[DW:1];")
t.rep("    wire signed [DW-1:0] ad_im = sat_im ? (sb_im0[AW] ? -32768 : 32767) : sb_im0[DW:1];",
      "    wire signed [DW-1:0] ad_im = sat_im ? (s_im[SW] ? -32768 : 32767) : sb_im0[DW:1];")
t.rep("""    wire [2*DW-1:0] diff_f = TRIVIAL ? {tr_y_im, tr_y_re}
                                     : {cm_im[DW-1:0], cm_re[DW-1:0]};

    assign sr_in = fh_sel ? raw_f : diff_f;""",
"""    wire [2*SW-1:0] diff_full = TRIVIAL ? {{3{tr_y_im[DW-1]}}, tr_y_im[DW-1:0],
                                          {3{tr_y_re[DW-1]}}, tr_y_re[DW-1:0]}
                                        : {cm_im[SW-1:0], cm_re[SW-1:0]};

    assign sr_in = fh_sel ? raw_f : diff_full;""")
t.rep("        reg [2*DW-1:0] fr;\n        initial fr = {2*DW{1'b0}};",
      "        reg [2*SW-1:0] fr;\n        initial fr = {2*SW{1'b0}};")
t.rep("        reg [2*DW-1:0] mem [0:S-1];\n        reg [AWD-1:0]  wptr;\n        reg [2*DW-1:0] fr;",
      "        reg [2*SW-1:0] mem [0:S-1];\n        reg [AWD-1:0]  wptr;\n        reg [2*SW-1:0] fr;")
t.rep("            fr = {2*DW{1'b0}}; wptr = {AWD{1'b0}};\n            for (zi = 0; zi < S; zi = zi + 1) mem[zi] = {2*DW{1'b0}};",
      "            fr = {2*SW{1'b0}}; wptr = {AWD{1'b0}};\n            for (zi = 0; zi < S; zi = zi + 1) mem[zi] = {2*SW{1'b0}};")
t.rep("    end else begin : g_sr0\n        assign sr_front_w = {2*DW{1'b0}};\n    end endgenerate",
      "    end else begin : g_sr0\n        assign sr_front_w = {2*SW{1'b0}};\n    end endgenerate")
t.rep("""    wire [2*DW-1:0] out_c = fh_now ? ((S > 0) ? sr_front_w : diff_f)
                                   : {ad_im, ad_re};
    reg [2*DW-1:0] out_r;""",
"""    // fh 段输出 fr 全 38 位透传(级间全精度;末级 reorder 后由 fft_top 截 16)
    wire [2*SW-1:0] out_c = fh_now ? ((S > 0) ? sr_front_w
                                              : {{3{diff_f[2*SW-1]}}, diff_f[2*SW-1:SW],
                                                 {3{diff_f[DW-1]}}, diff_f[DW-1:0]})
                                   : {{3{ad_im[DW-1]}}, ad_im[DW-1:0],
                                      {3{ad_re[DW-1]}}, ad_re[DW-1:0]};
    reg [2*SW-1:0] out_r;""")
t.rep("        out_r = {2*DW{1'b0}}; out_v = 1'b0;", "        out_r = {2*SW{1'b0}}; out_v = 1'b0;")
t.rep("    wire signed [AW-1:0] cm_re, cm_im;", "    wire signed [SW-1:0] cm_re, cm_im;")
t.rep("    fft_cmult3 #(.AW(AW), .BW(18), .RSH(18)) u_cmult (",
      "    fft_cmult3 #(.AW(SW), .BW(18), .RSH(18)) u_cmult (")
save('rtl/fft_stage.v', t.s); print("fft_stage:", t.n)

# ============ fft_top.v ============
t = T(load('rtl/fft_top.v'))
t.rep("    wire [2*DW-1:0] lk_tdata [0:M];",
      "    localparam SWL = SW;\n    wire [2*SWL-1:0] lk_tdata [0:M];")
t.rep("    assign lk_tdata[0]  = s_axis_tdata;",
"""    assign lk_tdata[0]  = {{3{s_axis_tdata[2*DW-1]}}, s_axis_tdata[2*DW-1:DW],
                           {3{s_axis_tdata[DW-1]}}, s_axis_tdata[DW-1:0]};""")
t.rep("    wire [2*DW-1:0] raw_tdata = lk_tdata[M];",
      "    wire [2*SWL-1:0] raw_tdata = lk_tdata[M];")
t.rep("fft_reorder #(.M(M), .DW(DW)) u_reorder (",
      "fft_reorder #(.M(M), .DW(DW), .SW(SWL)) u_reorder (")
t.rep("        assign m_axis_tdata  = raw_tdata;",
      "        assign m_axis_tdata  = {raw_tdata[2*SWL-4:SWL], raw_tdata[DW-1:0]};")
t.rep("        assign m_axis_tdata  = rb_tdata;",
      "        assign m_axis_tdata  = {rb_tdata[2*SWL-4:SWL], rb_tdata[DW-1:0]};")
save('rtl/fft_top.v', t.s); print("fft_top:", t.n)

# ============ fft_reorder.v ============
t = T(load('rtl/fft_reorder.v'))
t.rep("    parameter DW = 16", "    parameter DW = 16,\n    parameter SW = 19")
t.rep("    input  wire [2*DW-1:0]  x_tdata,", "    input  wire [2*SW-1:0]  x_tdata,")
t.rep("    output reg  [2*DW-1:0]  y_tdata,", "    output reg  [2*SW-1:0]  y_tdata,")
t.rep("    reg [2*DW-1:0] mem0 [0:N-1];", "    reg [2*SW-1:0] mem0 [0:N-1];")
t.rep("    reg [2*DW-1:0] mem1 [0:N-1];", "    reg [2*SW-1:0] mem1 [0:N-1];")
t.rep("        dv = 1'b0; df = 1'b0; dl = 1'b0; y_tdata = {2*DW{1'b0}};",
      "        dv = 1'b0; df = 1'b0; dl = 1'b0; y_tdata = {2*SW{1'b0}};")
t.rep("            mem0[zi] = {2*DW{1'b0}}; mem1[zi] = {2*DW{1'b0}};",
      "            mem0[zi] = {2*SW{1'b0}}; mem1[zi] = {2*SW{1'b0}};")
save('rtl/fft_reorder.v', t.s); print("fft_reorder:", t.n)

# ============ tb_fft_top.v ============
t = T(load('tb/tb_fft_top.v'))
t.rep("    wire [2*DW-1:0] lv_tdata [0:M_P-1];",
      "    localparam SW_P = SW;\n    wire [2*SW_P-1:0] lv_tdata [0:M_P-1];")
t.rep("                    lvl_mem[gi][lvl_cyc[gi]] <= lv_tdata[gi];",
      "                    lvl_mem[gi][lvl_cyc[gi]] <= {lv_tdata[gi][2*SW_P-4:SW_P], lv_tdata[gi][DW-1:0]};")
save('tb/tb_fft_top.v', t.s); print("tb:", t.n)
