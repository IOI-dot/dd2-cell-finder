// a_maj4_r0: functional model generated from the truth table (A = bit 0)
module a_maj4_r0 (A, B, C, D, Y);
  input A, B, C, D;
  output Y;
  wire [15:0] T = 16'hF880;
  assign Y = T[{D, C, B, A}];
endmodule
