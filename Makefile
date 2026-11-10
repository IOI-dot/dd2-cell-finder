# DD2 Project 1, Option 2: default targets run the finder/checker workflow.
# Historical Option 1/3 and agent work is archived under others/.
# The required targets (overview 5.1): setup check test all demo clean. Push and tag stay manual.

-include config/tools.mk
PINNED_BIN := $(HOME)/dd2-tools/oss-2026-10-27/bin
ifneq ($(wildcard $(PINNED_BIN)/yosys),)
export PATH := $(PINNED_BIN):$(HOME)/.local/bin:$(PATH)
export DD2_YOSYS ?= $(PINNED_BIN)/yosys
export DD2_ABC ?= $(PINNED_BIN)/yosys-abc
endif
PY        ?= .venv/bin/python
# Inputs live outside the repository. The defaults cover both machines the team uses (macOS and WSL);
# set PDK_ROOT, GIVEN or TUTORIALS to override.
PDK_ROOT  ?= $(firstword $(wildcard $(HOME)/.ciel $(HOME)/dd2-inputs) $(HOME)/.ciel)
GIVEN     ?= $(firstword $(wildcard ../DD2_Project1_student_pack/given $(HOME)/DD2_Project1_student_pack/given) ../DD2_Project1_student_pack/given)
TUTORIALS ?= $(firstword $(wildcard $(HOME)/dd2-inputs/tutorials ../tutorials) $(HOME)/dd2-inputs/tutorials)
GROUP     ?= $(shell cat config/group.txt 2>/dev/null)
# Option 2 M1 reproduces Table 1 only with Yosys 0.33: the reference binaries on WSL, or the dd2-flow image.
REFERENCE_YOSYS ?= /usr/bin/yosys
REFERENCE_ABC   ?= /usr/bin/yosys-abc
DESIGNS   ?= cpu8 dsp8 arlet6502 uart_apb risc8 fir10
LIMIT     ?= 10
IN        ?=
TOP       ?=
SV        ?=

DD2 = PYTHONPATH=src $(PY) -m dd2
M2  = PYTHONPATH=src $(PY) -m dd2m2
SHA256 := $(shell command -v sha256sum >/dev/null 2>&1 && echo sha256sum || echo shasum -a 256)

# The flow image: repository, given/ and the PDK mounted at their own absolute paths so the
# links resolve unchanged; given/ and the PDK are read-only.
DOCKER_FLOW = docker run --rm -u $$(id -u):$$(id -g) -e HOME=/tmp -e DD2_IN_CONTAINER=1 -e DD2_PDK_REALPATH="$(realpath pdk)" \
	-v "$(CURDIR)":"$(CURDIR)" -w "$(CURDIR)" \
	-v "$(realpath given)":"$(realpath given)":ro -v "$(realpath pdk)":"$(realpath pdk)":ro \
	-v "$(realpath pdk)":"$(shell readlink pdk)":ro dd2-flow

.PHONY: setup group check check-option2 check-versions test all reproduce demo demo-final clean \
	m1 m1-reference m1-docker m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary \
	m2 m2-fit m2-aigs-cuts m2-tutorials m2-baseline m2-candidates m2-library m2-map m2-plots readiness ta \
	m3-estimated m3-estimated-best m3-real docker-flow test-docker

## ---- setup and checks -------------------------------------------------------------------------

setup:            ## links to the PDK, the given files and the tutorials (never copies), and the Python env
	@test -f "$(GIVEN)/hd_reduced.lib" || (echo "student pack given/ not found: $(GIVEN) (set GIVEN)"; exit 2)
	@test -f "$(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" || (echo "full HD Liberty missing under $(PDK_ROOT)/sky130A (set PDK_ROOT)"; exit 2)
	ln -sfn "$(abspath $(PDK_ROOT))/sky130A" pdk
	ln -sfn "$(abspath $(GIVEN))" given
	@if [ -f "$(TUTORIALS)/spm/SPM_tb.v" ]; then ln -sfn "$(abspath $(TUTORIALS))" tutorials; \
	  else echo "NOTE tutorials not found at $(TUTORIALS): the Option 2 tutorial steps need them (set TUTORIALS)"; fi
	@test -x $(PY) || (command -v uv >/dev/null && uv venv --seed --python ">=3.11" .venv || python3 -m venv .venv)
	@$(PY) -m pip --version >/dev/null 2>&1 || $(PY) -m ensurepip --upgrade
	$(PY) -m pip install -q -r requirements-option2.txt
	@$(PY) -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
	@echo "setup: pdk -> $$(readlink pdk), given -> $$(readlink given)"

group:            ## record the DD2 group number Option 2 uses in its cell names
	@mkdir -p config
	@read -p 'Your actual DD2 group number: ' number; case "$$number" in ''|*[!0-9]*|0) echo 'A positive group number is required'; exit 1;; esac; printf '%s\n' "$$number" > config/group.txt

check: check-option2 ## required Option 2 tools and inputs

check-option2:    ## Option 2: Yosys, ABC, Icarus, OpenSTA, Liberty imports and the supplied designs
	$(M2) check --strict

check-versions:   ## Option 2 with the overview's minimum tool versions enforced
	$(M2) check --strict

OPTION2_TESTS = tests/contract/test_interface.py \
	tests/contract/test_map_command.py \
	tests/integration/test_aig.py \
	tests/integration/test_cutflow.py \
	tests/integration/test_demo.py \
	tests/integration/test_mapping.py \
	tests/integration/test_precedence.py \
	tests/integration/test_sizes.py \
	tests/m2/test_cost_regressions.py \
	tests/m2/test_equivalence.py \
	tests/m2/test_m2.py \
	tests/m2/test_timing_regressions.py \
	tests/m2/test_tutorials.py \
	tests/m2/test_final_flow.py \
	tests/unit/test_aiger_reader.py \
	tests/unit/test_boolfn.py \
	tests/unit/test_cutcheck.py \
	tests/unit/test_cuts.py \
	tests/unit/test_designs.py \
	tests/unit/test_hdclasses.py \
	tests/unit/test_liberty.py \
	tests/unit/test_paths.py \
	tests/unit/test_provenance.py \
	tests/unit/test_redundancy.py \
	tests/unit/test_stage.py \
	tests/unit/test_summary.py \
	tests/unit/test_tools.py \
	tests/integration/test_proposed_broken.py::test_yosys_rejects_liberty \
	tests/integration/test_proposed_broken.py::test_cec_rejects_nonequivalent_aig

test:             ## Option 2 suite and frozen fixture hashes
	cd tests/broken && $(SHA256) -c SHA256SUMS --quiet
	PYTHONPATH=src $(PY) -m pytest -q $(OPTION2_TESTS)

# The long run recomputes selection in build/. The short run uses the published selection.
ESTIMATED_DIR ?= results/m3/estimated-best
RESPONSES ?= libs/cellweaver
REAL_OUT ?= build/m3/reproduced-real
SWEEP_OUT ?= build/m3/reselected
DEMO_REAL ?= $(if $(wildcard results/m3/real/hd_extended_real.lib),results/m3/real,)

all:              ## full M1-M3 run, including a new best-of-all greedy sweep
	$(MAKE) m1
	$(MAKE) m2
	$(MAKE) m3-estimated-best SWEEP_OUT="$(SWEEP_OUT)"
	$(MAKE) m3-real ESTIMATED_DIR="$(SWEEP_OUT)"

reproduce: m3-real ## rerun real-cell measurements from the published selection

m3-estimated:     ## first-improvement greedy search
	$(M2) m3-estimated --group $(GROUP) --limit $(LIMIT)

m3-estimated-best: ## best-of-all greedy search; resume an interrupted sweep
	@if [ -s "$(SWEEP_OUT)/requests.json" ]; then echo "Using completed sweep: $(SWEEP_OUT)"; \
	else $(M2) m3-estimated --group $(GROUP) --limit $(LIMIT) --best-of-all --out "$(SWEEP_OUT)"; fi

m3-real:          ## verified real remaps, curve and sensitivity test
	@test -s "$(ESTIMATED_DIR)/baseline_mappings.json" || (echo "Missing estimated baseline under $(ESTIMATED_DIR); see README."; exit 2)
	@test -s "$(RESPONSES)/responses.json" || (echo "Missing packaged responses under $(RESPONSES); see README."; exit 2)
	$(M2) m3-real --estimated "$(ESTIMATED_DIR)" --responses "$(RESPONSES)" --out "$(REAL_OUT)"

## ---- Option 2 -------------------------------------------------------------------------------

m1:               ## Option 2 M1 with the reference Yosys 0.33 (Table 1)
	$(MAKE) m1-reference DD2_YOSYS="$(REFERENCE_YOSYS)" DD2_ABC="$(REFERENCE_ABC)"

m1-reference:
	$(M2) check --out results/m1/environment.json
	$(MAKE) m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary

m1-docker:        ## the Yosys 0.33 steps of M1 inside dd2-flow, for a machine without the reference binaries
	$(DOCKER_FLOW) make m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy PY=python3
	$(MAKE) m1-summary

m1-baseline:      ## Table 1: 6 designs x {usable, reduced} x {A, B}
	$(DD2) baseline
m1-aigs:          ## synth and restructured AIGs of the 6 required designs
	$(DD2) aig
m1-cuts:          ## 4-input cuts of the 12 AIGs, each checked by exhaustive simulation
	$(DD2) cuts
m1-hdclasses:     ## class table of HD
	$(DD2) hdclasses
m1-redundancy:    ## redundancy checker self-test against Table 4
	$(DD2) selftest
m1-summary:
	$(M2) m1-summary

m2:               ## Option 2 M2: area model, candidates, requests and Liberty, mappings, proofs, timing, plots
	@test -n "$(GROUP)" || (echo 'Run make group first'; exit 1)
	$(M2) run --group $(GROUP) --limit $(LIMIT) --designs $(DESIGNS)
m2-fit:
	$(M2) fit
m2-aigs-cuts:
	$(M2) discovery --designs $(DESIGNS)
m2-tutorials:
	$(M2) tutorials --designs $(DESIGNS)
m2-baseline:
	$(M2) baseline --designs $(DESIGNS)
m2-candidates:
	$(M2) candidates --designs $(DESIGNS)
m2-library:
	@test -n "$(GROUP)" || (echo 'Run make group first'; exit 1)
	$(M2) library --group $(GROUP) --limit $(LIMIT)
m2-map:
	$(M2) map --designs $(DESIGNS)
m2-plots:
	$(M2) plots
readiness:        ## the Option 2 M2 readiness record
	$(M2) readiness
ta:               ## refresh the TA_M2/ copies from the saved Option 2 evidence (never recomputes)
	$(M2) showcase

docker-flow:      ## build the reference Yosys 0.33 image
	docker build -f docker/flow.Dockerfile -t dd2-flow docker

test-docker:      ## Option 2 tests in the reference image
	$(DOCKER_FLOW) make test PY=python3

## ---- the interview ----------------------------------------------------------------------------

demo-final:       ## map one design or the M3 suite with the saved characterized library
	@test -n "$(IN)" || (echo "usage: make demo-final IN=<design.v|benchmark|all> [TOP=<module>] [SV=1] [OPEN=1]"; exit 2)
	$(M2) demo-final "$(IN)" $(if $(TOP),--top "$(TOP)") $(if $(SV),--sv) $(if $(filter 1,$(OPEN)),--open)

demo:             ## complete Option 2 demo: make demo IN=<design.v> [TOP=<module>] [SV=1]
	@test -n "$(IN)" || (echo "usage: make demo IN=<design.v> [TOP=<module>] [SV=1]"; exit 2)
	$(M2) demo "$(IN)" --group $(GROUP) --limit $(LIMIT) $(if $(TOP),--top "$(TOP)") $(if $(SV),--sv) $(if $(DEMO_REAL),--real "$(DEMO_REAL)")

clean:
	rm -rf build
