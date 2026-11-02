// dd2_ref__mux2_1: functional model generated from the truth table (A = bit 0)
module dd2_ref__mux2_1 (A0, A1, S, X);
  input A0, A1, S;
  output X;
  wire [7:0] T = 8'hCA;
  assign X = T[{S, A1, A0}];
endmodule
