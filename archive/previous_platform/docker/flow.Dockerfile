# DD2 flow image: the Option 2 toolchain on the same base as the course image.
# Ubuntu 24.04's yosys package is Yosys 0.33, the version the Option 2 handout's Table 1 used.
#   docker build -f docker/flow.Dockerfile -t dd2-flow .
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      yosys iverilog python3 python3-venv python3-pytest make git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# The repository, given/ and the PDK are mounted at run time (given/ and the PDK read-only).
WORKDIR /work
