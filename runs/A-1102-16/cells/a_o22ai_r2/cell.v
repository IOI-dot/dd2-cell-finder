// a_o22ai_r2: functional model generated from the truth table (A = bit 0)
module a_o22ai_r2 (A, B, C, D, Y);
  input A, B, C, D;
  output Y;
  wire [15:0] T = 16'h111F;
  assign Y = T[{D, C, B, A}];
endmodule
