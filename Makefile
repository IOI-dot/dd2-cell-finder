# DD2 Project 1, Option 3. Active scope: Option 2 Milestone 1 (cp1).
# The required targets (overview 5.1): setup check test all demo clean.

PDK_ROOT ?= $(HOME)/.ciel
GIVEN    ?= ../DD2_Project1_student_pack/given
IN       ?=
TOP      ?=
SV       ?=
# Yosys used by the flow. The handout's Table 1 is reproduced exactly only by Linux Yosys 0.33
# (Ubuntu 24.04's package), which the dd2-flow image provides: use `make m1-docker` for evidence.
YOSYS    ?= yosys

PY  ?= .venv/bin/python
DD2 := DD2_YOSYS="$(YOSYS)" PYTHONPATH=src $(PY) -m dd2

# The flow image: repository, given/ and the PDK mounted at their own absolute paths so the
# links resolve unchanged; given/ and the PDK are read-only.
DOCKER_FLOW = docker run --rm -u $$(id -u):$$(id -g) -e HOME=/tmp -e DD2_PDK_REALPATH="$(realpath pdk)" \
	-v "$(CURDIR)":"$(CURDIR)" -w "$(CURDIR)" \
	-v "$(realpath given)":"$(realpath given)":ro -v "$(realpath pdk)":"$(realpath pdk)":ro \
	-v "$(realpath pdk)":"$(shell readlink pdk)":ro dd2-flow

.PHONY: setup check test all demo clean m1 m1-env docker-flow m1-docker test-docker m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary agent-check

setup:            ## links to the PDK and the given files (never copies), and the Python env
	@test -d "$(PDK_ROOT)/sky130A" || (echo "PDK not found: $(PDK_ROOT)/sky130A (set PDK_ROOT)" && exit 2)
	@test -d "$(GIVEN)" || (echo "student pack given/ not found: $(GIVEN) (set GIVEN)" && exit 2)
	ln -sfn "$(PDK_ROOT)/sky130A" pdk
	ln -sfn "$(GIVEN)" given
	test -x $(PY) || uv venv --python ">=3.11" .venv
	uv pip install --python $(PY) -q "pytest>=8"
	@$(PY) -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
	@echo "setup: pdk -> $$(readlink pdk), given -> $$(readlink given)"

check:            ## tool versions, PDK, supplied inputs (OpenSTA and ngspice reported for later)
	@test -L pdk -a -L given || (echo "pdk/given links missing: run make setup" && exit 1)
	$(DD2) check

test:             ## every test, including the broken cases in tests/broken/
	cd tests/broken && shasum -a 256 -c SHA256SUMS --quiet
	DD2_YOSYS="$(YOSYS)" $(PY) -m pytest -q

all: m1           ## the whole flow implemented so far (M1)

m1: m1-env m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary

m1-env:           ## the environment record that goes with the evidence
	$(DD2) check --out results/m1/environment.json

m1-baseline:      ## Table 1: 6 designs x {usable, reduced} x {A, B}
	$(DD2) baseline

m1-aigs:          ## synth and restructured AIGs of the 6 required designs
	$(DD2) aig

m1-cuts: m1-aigs  ## 4-input cuts of the 12 AIGs, each checked by exhaustive simulation
	$(DD2) cuts

m1-hdclasses:     ## class table of HD
	$(DD2) hdclasses

m1-redundancy:    ## redundancy checker self-test against Table 4
	$(DD2) selftest

m1-summary:
	$(DD2) summary

agent-check:      ## cp1 agentic rows: wrapped tools, read-only checks, logged runs
	PYTHONPATH=src:agent $(PY) -m dd2_agent.selfcheck

docker-flow:      ## build the flow image (Ubuntu 24.04: Yosys 0.33, Icarus, Python 3.12)
	docker build -f docker/flow.Dockerfile -t dd2-flow docker

m1-docker:        ## the M1 flow inside dd2-flow: the evidence in results/m1 is made this way
	$(DOCKER_FLOW) make m1 PY=python3

test-docker:      ## the test suite inside dd2-flow
	$(DOCKER_FLOW) sh -c "cd tests/broken && sha256sum -c SHA256SUMS --quiet && cd ../.. && python3 -m pytest -q -p no:cacheprovider"

demo:             ## what the interview runs: make demo IN=<design.v> [TOP=<top>] [SV=1]
	@test -n "$(IN)" || (echo "usage: make demo IN=<design.v> [TOP=<top>] [SV=1]" && exit 2)
	$(DD2) demo "$(IN)" $(if $(TOP),--top $(TOP)) $(if $(SV),--sv)

clean:
	rm -rf build
