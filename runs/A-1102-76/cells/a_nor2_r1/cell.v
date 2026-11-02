// a_nor2_r1: functional model generated from the truth table (A = bit 0)
module a_nor2_r1 (A, B, Y);
  input A, B;
  output Y;
  wire [3:0] T = 4'h1;
  assign Y = T[{B, A}];
endmodule
