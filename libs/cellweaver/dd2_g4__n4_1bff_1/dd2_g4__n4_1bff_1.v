module dd2_g4__n4_1bff_1(input A, input B, input C, input D, output Y, inout VPWR, VGND, VPB, VNB);
  assign Y = ((~(D) | (~(A) & ~(B))) | (A & ~(C)));
endmodule
