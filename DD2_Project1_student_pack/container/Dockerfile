# DD2 Project 1: course tools image dd2-layout-tools
# Magic and Netgen at the versions Tutorial 3 uses, and ngspice 47 with the
# BSIM4 stress-mobility fix (Option 1 handout, section 5).
#   docker build -t dd2-layout-tools .
FROM ubuntu:24.04

ARG MAGIC_VERSION=8.3.684
ARG NETGEN_VERSION=1.5.133
ARG NGSPICE_VERSION=47

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git m4 csh python3 \
      autoconf automake libtool bison flex \
      tcl-dev tk-dev libcairo2-dev libx11-dev libxpm-dev libglu1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

# Magic
RUN git clone --depth 1 --branch ${MAGIC_VERSION} https://github.com/RTimothyEdwards/magic.git /tmp/magic \
    && cd /tmp/magic && ./configure && make -j"$(nproc)" && make install \
    && rm -rf /tmp/magic

# Netgen
RUN git clone --depth 1 --branch ${NETGEN_VERSION} https://github.com/RTimothyEdwards/netgen.git /tmp/netgen \
    && cd /tmp/netgen && ./configure && make -j"$(nproc)" && make install \
    && rm -rf /tmp/netgen

# ngspice 47 with the four one-line BSIM4 fixes
COPY ngspice-47-bsim4-stress-mobility.patch /tmp/
RUN curl -sL https://codeload.github.com/imr/ngspice/tar.gz/refs/tags/ngspice-${NGSPICE_VERSION} | tar xz -C /tmp \
    && cd /tmp/ngspice-ngspice-${NGSPICE_VERSION} \
    && patch -p1 < /tmp/ngspice-47-bsim4-stress-mobility.patch \
    && ./autogen.sh && mkdir build && cd build \
    && ../configure --with-x=no --with-readline=no --disable-debug \
    && make -j"$(nproc)" && make install \
    && rm -rf /tmp/ngspice-ngspice-${NGSPICE_VERSION} /tmp/ngspice-47-bsim4-stress-mobility.patch

# The stress test; the build fails if the fix is not in place
COPY stress_test/ /opt/dd2/stress_test/
RUN /opt/dd2/stress_test/check_stress.sh

WORKDIR /work
