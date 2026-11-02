// a_nand3_r3: functional model generated from the truth table (A = bit 0)
module a_nand3_r3 (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h7F;
  assign Y = T[{C, B, A}];
endmodule
