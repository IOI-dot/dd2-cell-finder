#!/bin/bash
# OpenSTA for Option 1 Table 5 (Liberty load and SPM timing) and Option 2 T045. There is no arm64
# image, so it is compiled here. The tree needs about 3 GB, so it stays on a tmpfs in the VM and
# only the binary reaches the disk; image dd2-sta is ubuntu:24.04, Tcl and that binary.
set -e
REF=f2f431abf02a409f3e46aa8d95557353ef6f6a3a
OUT="$(cd "$(dirname "$0")/.." && pwd)/build/sta_out"
mkdir -p "$OUT"
docker run --rm --tmpfs /src:size=3800m,exec -v "$OUT:/out" ubuntu:24.04 bash -ec "
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends g++ make cmake flex libfl-dev bison \
    tcl-dev swig libeigen3-dev libgtest-dev zlib1g-dev git ca-certificates >/dev/null
  git clone -q --depth 1 https://github.com/ivmai/cudd.git /src/cudd
  cd /src/cudd && touch aclocal.m4 configure Makefile.am Makefile.in config.h.in
  ./configure --prefix=/usr/local >/dev/null && make -j3 >/dev/null 2>&1 && make install >/dev/null 2>&1
  git init -q /src/sta && cd /src/sta
  git fetch -q --depth 1 https://github.com/The-OpenROAD-Project/OpenSTA.git $REF && git checkout -q FETCH_HEAD
  git rev-parse HEAD > /out/sta_commit
  mkdir build && cd build && cmake .. -DCUDD_DIR=/usr/local -DCMAKE_BUILD_TYPE=Release >/dev/null
  make -j3 sta 2>&1 | tail -3
  cp sta /out/sta"
docker build -q -t dd2-sta -f - "$OUT" <<'D'
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libtcl8.6 zlib1g && rm -rf /var/lib/apt/lists/*
COPY sta /usr/local/bin/sta
COPY sta_commit /sta_commit
WORKDIR /w
D
docker run --rm dd2-sta sta -version
