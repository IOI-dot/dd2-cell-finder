# DD2 Project 1, Option 2: default targets run the finder/checker workflow.
# Additional generator/platform work is retained behind explicit optional targets.
# The required targets (overview 5.1): setup check test all demo clean. Push and tag stay manual.

-include config/tools.mk
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
O1  = PYTHONPATH=src $(PY) -m cellgen
AG  = PYTHONPATH=src:agent $(PY) -m dd2_agent
SHA256 := $(shell command -v sha256sum >/dev/null 2>&1 && echo sha256sum || echo shasum -a 256)

# The flow image: repository, given/ and the PDK mounted at their own absolute paths so the
# links resolve unchanged; given/ and the PDK are read-only.
DOCKER_FLOW = docker run --rm -u $$(id -u):$$(id -g) -e HOME=/tmp -e DD2_IN_CONTAINER=1 -e DD2_PDK_REALPATH="$(realpath pdk)" \
	-v "$(CURDIR)":"$(CURDIR)" -w "$(CURDIR)" \
	-v "$(realpath given)":"$(realpath given)":ro -v "$(realpath pdk)":"$(realpath pdk)":ro \
	-v "$(realpath pdk)":"$(shell readlink pdk)":ro dd2-flow

.PHONY: setup setup-extended group check check-extended check-option1 check-option2 check-versions test test-extended all all-extended demo clean \
	m1 m1-reference m1-docker m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary \
	m2 m2-fit m2-aigs-cuts m2-tutorials m2-baseline m2-candidates m2-library m2-map m2-plots readiness ta \
	o1-image o1-sta o1-rules o1-m1 o1-m2 docker-flow test-docker \
	o3 o3-cells o3-map agent fixed agent-compare agent-check agent-server web

## ---- setup and checks -------------------------------------------------------------------------

setup:            ## links to the PDK, the given files and the tutorials (never copies), and the Python env
	@test -f "$(GIVEN)/hd_reduced.lib" || (echo "student pack given/ not found: $(GIVEN) (set GIVEN)"; exit 2)
	@test -f "$(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" || (echo "full HD Liberty missing under $(PDK_ROOT)/sky130A (set PDK_ROOT)"; exit 2)
	ln -sfn "$(PDK_ROOT)/sky130A" pdk
	ln -sfn "$(GIVEN)" given
	@if [ -f "$(TUTORIALS)/spm/SPM_tb.v" ]; then ln -sfn "$(TUTORIALS)" tutorials; \
	  else echo "NOTE tutorials not found at $(TUTORIALS): the Option 2 tutorial steps need them (set TUTORIALS)"; fi
	@test -x $(PY) || (command -v uv >/dev/null && uv venv --python ">=3.11" .venv || python3 -m venv .venv)
	$(PY) -m pip install -q -r requirements-option2.txt
	@$(PY) -c 'import sys; assert sys.version_info >= (3, 11), sys.version'
	@echo "setup: pdk -> $$(readlink pdk), given -> $$(readlink given)"

group:            ## record the DD2 group number Option 2 uses in its cell names
	@mkdir -p config
	@read -p 'Your actual DD2 group number: ' number; case "$$number" in ''|*[!0-9]*|0) echo 'A positive group number is required'; exit 1;; esac; printf '%s\n' "$$number" > config/group.txt

setup-extended: setup ## optional generator/agent/studio dependencies
	$(PY) -m pip install -q -e ".[cell,agent,web]" "uvicorn>=0.30"

check: check-option2 ## required Option 2 tools and inputs

check-extended: check-option2 check-option1 ## optional generator/physical-tool checks

check-option2:    ## Option 2: Yosys, ABC, Icarus, OpenSTA, Liberty imports and the supplied designs
	$(M2) check

check-option1:    ## Option 1: PDK views, the course image and the ngspice stress test
	@test -L pdk -a -L given || (echo "pdk/given links missing: run make setup" && exit 1)
	$(DD2) check

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

test:             ## complete Option 2 suite; original checks and negative cases unchanged
	cd tests/broken && $(SHA256) -c SHA256SUMS --quiet
	PYTHONPATH=src $(PY) -m pytest -q $(OPTION2_TESTS)

test-extended:    ## all retained generator/agent/studio tests as well
	cd tests/broken && $(SHA256) -c SHA256SUMS --quiet
	PYTHONPATH=src $(PY) -m pytest -q tests

all:              ## the submitted Option 2 M1 and M2 workflow
	$(MAKE) m1
	$(MAKE) m2

all-extended: all ## optional generator workflow after Option 2
	$(MAKE) o1-rules o1-m1 o1-m2

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

## ---- Option 1 -------------------------------------------------------------------------------

o1-image:         ## build the course image dd2-layout-tools from the student pack (unchanged)
	docker build -t dd2-layout-tools "$(realpath given)/../container"
o1-sta:           ## OpenSTA in image dd2-sta, compiled on a tmpfs
	docker/build_sta.sh
o1-rules:         ## the design-rule table behind the layout numbers -> results/option1/rules.csv
	PYTHONPATH=src $(PY) -m cellgen.rules_table
o1-m1:            ## Option 1 M1: frame check, inv_1 and nand2_1 regenerated and verified, request reader, network check
	PYTHONPATH=src $(PY) -m cellgen.m1
o1-m2:            ## Option 1 M2: references (Table 4), test cells (Table 6), characterizer (Table 5), summary
	PYTHONPATH=src $(PY) -m cellgen.m2 refs
	PYTHONPATH=src $(PY) -m cellgen.m2 tests
	PYTHONPATH=src $(PY) -m cellgen.m2 table5
	PYTHONPATH=src $(PY) -m cellgen.m2 timing
	PYTHONPATH=src $(PY) -m cellgen.m2 summary
docker-flow:      ## build the flow image (Ubuntu 24.04: Yosys 0.33, Icarus, Python 3.12)
	docker build -f docker/flow.Dockerfile -t dd2-flow docker
test-docker:      ## the test suite inside dd2-flow
	$(DOCKER_FLOW) sh -c "cd tests/broken && sha256sum -c SHA256SUMS --quiet && cd ../.. && python3 -m pytest -q -p no:cacheprovider"

## ---- Option 3: the two options connected ------------------------------------------------------

o3: o3-cells o3-map ## Option 1 builds Option 2's requests, then Option 2 remaps with the cells that passed

o3-cells:         ## Option 1 builds, checks and characterizes every cell in results/m2/requests.json
	PYTHONPATH=src $(PY) -m cellgen.deliver results/m2/requests.json

# Where no native OpenSTA is installed (macOS), docker/bin/sta runs it from image dd2-sta.
STA_PATH := $(if $(shell command -v sta 2>/dev/null),,$(CURDIR)/docker/bin:)

o3-map:           ## Option 2 maps the designs onto the real cells, into results/option3/
	PATH="$(STA_PATH)$$PATH" $(M2).option3

## ---- the agent and the studio ---------------------------------------------------------------

agent:            ## one headless agent run: make agent FUNC='!(A & (B | C))' [AGENT_FLAGS=--scripted]
	$(AG).graph --func '$(FUNC)' $(AGENT_FLAGS)
fixed:            ## the fixed-choice version on one function: make fixed FUNC='...'
	$(AG).fixed_choice '$(FUNC)'
agent-compare:    ## agent against fixed choices on the test cells -> results/option1/m2/agent_vs_fixed.csv
	$(AG).compare
agent-check:      ## cp1 agentic rows: wrapped tools, read-only checks, logged runs
	$(AG).selfcheck
agent-server:     ## the studio's back end, on 127.0.0.1:8123
	$(AG).server
web:              ## the studio on 127.0.0.1:5173 (run agent-server too)
	cd web && pnpm install --frozen-lockfile && pnpm dev

## ---- the interview ----------------------------------------------------------------------------

demo:             ## make demo IN=<request.json | design.v> [TOP=<top>] [SV=1]
	@test -n "$(IN)" || (echo "usage: make demo IN=<request.json | design.v> [TOP=<top>] [SV=1]" && exit 2)
	@case "$(IN)" in \
	  *.json) $(O1) request "$(IN)" --out build/demo/cells --work build/demo/work ;; \
	  *) $(DD2) demo "$(IN)" $(if $(TOP),--top $(TOP)) $(if $(SV),--sv) ;; \
	esac

clean:
	rm -rf build
