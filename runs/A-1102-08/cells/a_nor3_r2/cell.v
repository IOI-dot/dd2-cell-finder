// a_nor3_r2: functional model generated from the truth table (A = bit 0)
module a_nor3_r2 (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h01;
  assign Y = T[{C, B, A}];
endmodule
