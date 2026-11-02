// web_cell_r0: functional model generated from the truth table (A = bit 0)
module web_cell_r0 (A, B, C, Y);
  input A, B, C;
  output Y;
  wire [7:0] T = 8'hCA;
  assign Y = T[{C, B, A}];
endmodule
