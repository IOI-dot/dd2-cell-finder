// dd2_ref__nand2_1: functional model generated from the truth table (A = bit 0)
module dd2_ref__nand2_1 (A, B, Y);
  input A, B;
  output Y;
  wire [3:0] T = 4'h7;
  assign Y = T[{B, A}];
endmodule
