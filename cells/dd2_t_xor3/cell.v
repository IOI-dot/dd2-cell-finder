// dd2_t_xor3: functional model generated from the truth table (A = bit 0)
module dd2_t_xor3 (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h96;
  assign Y = T[{C, B, A}];
endmodule
