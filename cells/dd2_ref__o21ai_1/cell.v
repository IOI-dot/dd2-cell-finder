// dd2_ref__o21ai_1: functional model generated from the truth table (A = bit 0)
module dd2_ref__o21ai_1 (A1, A2, B1, Y);
  input A1, A2, B1;
  output Y;
  wire [7:0] T = 8'h1F;
  assign Y = T[{B1, A2, A1}];
endmodule
