// web_cell_r0: functional model generated from the truth table (A = bit 0)
module web_cell_r0 (A, B, S, Y);
  input A, B, S;
  output Y;
  wire [7:0] T = 8'h3E;
  assign Y = T[{S, B, A}];
endmodule
