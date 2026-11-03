// dd2_g4__n3_9f_1: functional model generated from the truth table (A = bit 0)
module dd2_g4__n3_9f_1 (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h9F;
  assign Y = T[{C, B, A}];
endmodule
