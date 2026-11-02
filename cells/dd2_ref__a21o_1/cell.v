// dd2_ref__a21o_1: functional model generated from the truth table (A = bit 0)
module dd2_ref__a21o_1 (A1, A2, B1, X);
  input A1, A2, B1;
  output X;
  wire [7:0] T = 8'hF8;
  assign X = T[{B1, A2, A1}];
endmodule
