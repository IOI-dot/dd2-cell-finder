// f_o21ai: functional model generated from the truth table (A = bit 0)
module f_o21ai (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'h1F;
  assign Y = T[{C, B, A}];
endmodule
