module dd2_g4__n3_2e_1(input A, input B, input C, output Y, inout VPWR, VGND, VPB, VNB);
  assign Y = ((~(B) | ~(C)) & (A | B));
endmodule
