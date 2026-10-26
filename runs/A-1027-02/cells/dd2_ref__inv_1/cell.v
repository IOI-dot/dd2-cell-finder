// dd2_ref__inv_1: functional model generated from the truth table (A = bit 0)
module dd2_ref__inv_1 (A, Y);
  input A;
  output Y;
  wire [1:0] T = 2'h1;
  assign Y = T[{A}];
endmodule
