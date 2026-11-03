# Option 2 only. Push/tag operations remain manual.
-include config/tools.mk
PY ?= .venv/bin/python
PDK_ROOT ?= $(HOME)/dd2-inputs
GIVEN ?= $(HOME)/DD2_Project1_student_pack/given
TUTORIALS ?= $(HOME)/dd2-inputs/tutorials
GROUP ?= $(shell cat config/group.txt 2>/dev/null)
REFERENCE_YOSYS ?= /usr/bin/yosys
REFERENCE_ABC ?= /usr/bin/yosys-abc
DESIGNS ?= cpu8 dsp8 arlet6502 uart_apb risc8 fir10
LIMIT ?= 10
IN ?=
TOP ?=
SV ?=
DD2 = PYTHONPATH=src $(PY) -m dd2
M2 = PYTHONPATH=src $(PY) -m dd2m2

.PHONY: setup group check check-versions test all m1 m1-reference m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary m2 m2-fit m2-aigs-cuts m2-tutorials m2-baseline m2-candidates m2-library m2-map m2-plots readiness ta demo clean
setup:
	@test -f "$(GIVEN)/hd_reduced.lib" || (echo 'Set GIVEN to the extracted pack given/ directory'; exit 1)
	@test -f "$(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib" || (echo 'Full HD Liberty missing: set PDK_ROOT'; exit 1)
	ln -sfn "$(GIVEN)" given
	ln -sfn "$(PDK_ROOT)/sky130A" pdk
	@test -f "$(TUTORIALS)/spm/SPM_tb.v" -a -f "$(TUTORIALS)/multiplier/mul_exhaustive_tb.v" || (echo 'Set TUTORIALS to the external spm/ and multiplier/ input directory'; exit 1)
	ln -sfn "$(TUTORIALS)" tutorials
	@test -x $(PY) || /usr/bin/python3 -m venv .venv
	$(PY) -m pip install -r requirements-option2.txt
group:
	@mkdir -p config
	@read -p 'Your actual DD2 group number: ' number; case "$$number" in ''|*[!0-9]*|0) echo 'A positive group number is required'; exit 1;; esac; printf '%s\n' "$$number" > config/group.txt
check:
	$(M2) check
check-versions:
	$(M2) check --strict
test:
	cd tests/broken && sha256sum -c SHA256SUMS --quiet
	PYTHONPATH=src $(PY) -m pytest -q tests
all: m1
	$(MAKE) m2
m1:
	$(MAKE) m1-reference DD2_YOSYS="$(REFERENCE_YOSYS)" DD2_ABC="$(REFERENCE_ABC)"
m1-reference:
	$(M2) check --out results/m1/environment.json
	$(MAKE) m1-baseline m1-aigs m1-cuts m1-hdclasses m1-redundancy m1-summary
m1-baseline:
	$(DD2) baseline
m1-aigs:
	$(DD2) aig
m1-cuts:
	$(DD2) cuts
m1-hdclasses:
	$(DD2) hdclasses
m1-redundancy:
	$(DD2) selftest
m1-summary:
	$(M2) m1-summary
m2:
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
readiness:
	$(M2) readiness
ta:
	$(M2) showcase
demo:
	@test -n "$(IN)" || (echo 'Set IN to a Verilog file'; exit 1)
	$(DD2) demo "$(IN)" $(if $(TOP),--top $(TOP)) $(if $(SV),--sv)
clean:
	rm -rf build
