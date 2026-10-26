# Course tools image: dd2-layout-tools

Builds Magic 8.3.684, Netgen 1.5.133 and ngspice 47 with the BSIM4 stress-mobility fix.

    docker build -t dd2-layout-tools .

The image has the same name as the one Tutorial 3's `make image` builds, so Tutorial 3's
`tools.sh` uses it unchanged. The last build step runs the stress test, so an image that
builds has the fix.

## The fix
Stock ngspice computes each BSIM4 transistor's mobility with the stress of SA and SB, then
overwrites it with the value without stress. `ngspice-47-bsim4-stress-mobility.patch`
changes one line in each of the four BSIM4 versions so that the stressed value is kept.

## The stress test
`stress_test/check_stress.sh` runs `stress_test.cir`: two identical NMOS that differ only in
SA and SB, with a model card whose only stress effect is on mobility. It needs no PDK.

    ./stress_test/check_stress.sh                 # ngspice on the PATH
    NGSPICE=/path/to/ngspice ./stress_test/check_stress.sh

It passes (exit 0) on the fixed build and fails (exit 1) on a stock one. Run it from your
`make check`, and write the ngspice version and hash it prints into every Liberty file.
