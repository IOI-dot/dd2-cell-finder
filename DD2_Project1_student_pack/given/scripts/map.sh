#!/bin/sh
# DD2 Project 1, Option 2 handout, section 2: map one design onto one library
# with ABC script A (amap) or B (&nf), and print its area.
#   usage: map.sh <design.v> <top> <liberty> <A|B> [-sv]
# Example: map.sh designs/cpu8.v cpu8 hd_reduced.lib A
set -e
[ $# -ge 4 ] || { echo "usage: map.sh <design.v> <top> <liberty> <A|B> [-sv]"; exit 2; }
V=$1; TOP=$2; LIB=$3; S=$4; SV=${5:-}
case $S in
  A) SCRIPT='+strash;dch,-f;amap;topo' ;;
  B) SCRIPT='+strash;&get,-n;&dch,-f;&nf,-R,1000;&put' ;;
  *) echo "script must be A or B"; exit 2 ;;
esac
yosys -q -p "read_verilog $SV $V; synth -flatten -top $TOP; dfflibmap -liberty $LIB; abc -liberty $LIB -script $SCRIPT; opt_clean -purge; tee -o /dev/stdout stat -liberty $LIB" 2>/dev/null | grep -E "Number of cells|Chip area" | tail -2
