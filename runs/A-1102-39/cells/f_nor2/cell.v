// f_nor2: functional model generated from the truth table (A = bit 0)
module f_nor2 (A, B, Y);
  input A, B;
  output Y;
  wire [3:0] T = 4'h1;
  assign Y = T[{B, A}];
endmodule
