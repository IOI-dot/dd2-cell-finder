// dd2_g4__n4_e888_1: functional model generated from the truth table (A = bit 0)
module dd2_g4__n4_e888_1 (A, B, C, D, Y);
  input A, B, C, D;
  output Y;
  wire [15:0] T = 16'hE888;
  assign Y = T[{D, C, B, A}];
endmodule
