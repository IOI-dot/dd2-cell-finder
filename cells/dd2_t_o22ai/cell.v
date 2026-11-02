// dd2_t_o22ai: functional model generated from the truth table (A = bit 0)
module dd2_t_o22ai (A, B, C, D, Y);
  input A, B, C, D;
  output Y;
  wire [15:0] T = 16'h111F;
  assign Y = T[{D, C, B, A}];
endmodule
