"""Run the original Option 2 checks from the unchanged mixed-scope test file.
Only its two Option 1 simulation tests are excluded from active Option 2 scope.
"""
import importlib.util
from dd2.paths import ROOT

p=ROOT/'archive/option1/tests/integration/test_proposed_broken.py'
spec=importlib.util.spec_from_file_location('retained_mixed_broken_checks',p)
original=importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)
test_yosys_rejects_liberty=original.test_yosys_rejects_liberty
test_cec_rejects_nonequivalent_aig=original.test_cec_rejects_nonequivalent_aig
