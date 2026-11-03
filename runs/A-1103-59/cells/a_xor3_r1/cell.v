// a_xor3_r1: functional model generated from the truth table (A = bit 0)
module a_xor3_r1 (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h96;
  assign Y = T[{C, B, A}];
endmodule
