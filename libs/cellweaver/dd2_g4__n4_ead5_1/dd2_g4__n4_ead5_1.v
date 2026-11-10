module dd2_g4__n4_ead5_1(input A, input B, input C, input D, output Y, inout VPWR, VGND, VPB, VNB);
  assign Y = (((~(A) & ~(D)) | (B & C)) | (A & D));
endmodule
