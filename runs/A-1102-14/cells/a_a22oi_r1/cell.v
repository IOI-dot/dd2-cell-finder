// a_a22oi_r1: functional model generated from the truth table (A = bit 0)
module a_a22oi_r1 (A, B, C, D, Y);
  input A, B, C, D;
  output Y;
  wire [15:0] T = 16'h0777;
  assign Y = T[{D, C, B, A}];
endmodule
