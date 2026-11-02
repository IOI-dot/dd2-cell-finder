// a_and2_r1: functional model generated from the truth table (A = bit 0)
module a_and2_r1 (A, B, Y);
  input A, B;
  output Y;
  wire [3:0] T = 4'h8;
  assign Y = T[{B, A}];
endmodule
