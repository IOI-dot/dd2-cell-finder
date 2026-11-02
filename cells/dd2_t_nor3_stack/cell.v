// dd2_t_nor3_stack: functional model generated from the truth table (A = bit 0)
module dd2_t_nor3_stack (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h01;
  assign Y = T[{C, B, A}];
endmodule
