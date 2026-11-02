// dd2_t_xor2: functional model generated from the truth table (A = bit 0)
module dd2_t_xor2 (A, B, Y);
  input A, B;
  output Y;
  wire [3:0] T = 4'h6;
  assign Y = T[{B, A}];
endmodule
