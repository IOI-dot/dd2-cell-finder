module dd2_g4__n4_000e_1(input A, input B, input C, input D, output Y, inout VPWR, VGND, VPB, VNB);
  assign Y = ((~(D) & ~(C)) & (A | B));
endmodule
