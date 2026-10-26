# DD2 Project 1, Option 3. Active scope: Option 2 Milestone 1 (cp1).
# The required targets (overview 5.1): setup check test all demo clean.

PDK_ROOT ?= $(HOME)/.ciel
GIVEN    ?= ../DD2_Project1_student_pack/given
IN       ?=
TOP      ?=
SV       ?=
# Yosys used by the flow. Table 1 reference is 0.33 (research D-2); override e.g.
#   make m1 YOSYS="uv run --extra flow yowasp-yosys"
YOSYS    ?= yosys

PY  := .venv/bin/python
DD2 := DD2_YOSYS="$(YOSYS)" PYTHONPATH=src $(PY) -m dd2

.PHONY: setup check test all demo clean m1 m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary agent-check

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

m1: m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary

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

demo:             ## what the interview runs: make demo IN=<design.v> [TOP=<top>] [SV=1]
	@test -n "$(IN)" || (echo "usage: make demo IN=<design.v> [TOP=<top>] [SV=1]" && exit 2)
	$(DD2) demo "$(IN)" $(if $(TOP),--top $(TOP)) $(if $(SV),--sv)

clean:
	rm -rf build
