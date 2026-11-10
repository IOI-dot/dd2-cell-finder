module dd2_g4__n4_8aa0_1(input A, input B, input C, input D, output Y, inout VPWR, VGND, VPB, VNB);
  assign Y = ((A & ((B | ~(C)) | ~(D))) & (C | D));
endmodule
