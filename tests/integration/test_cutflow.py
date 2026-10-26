import subprocess
import sys

from dd2 import cutflow, paths

ENV = {"PYTHONPATH": str(paths.ROOT / "src"), "PATH": __import__("os").environ["PATH"]}


def cli(*a):
    return subprocess.run([sys.executable, "-m", "dd2", *a], capture_output=True, text=True,
                          cwd=paths.ROOT, env=ENV)


def test_cli_rejects_broken_case():
    p = cli("cutcheck", "--aig", "tests/broken/wrong_truth_table.aig",
            "--cuts", "tests/broken/wrong_truth_table.json")
    assert p.returncode == 1 and "FAIL" in p.stdout


def test_process_cpu8(tmp_path):
    s = cutflow.process(paths.ROOT / "tests/broken/wrong_truth_table.aig", tmp_path,
                        tmp_path / "full.jsonl.gz", "synth")
    assert s["cuts_total"] == s["cuts_checked"] > 1000 and s["failures"] == []
    assert s["run"]["status"] == "pass" and s["pn_classes"] >= s["npn_classes"]
    # the full list round-trips through the independent checker
    assert cutflow.check_file(paths.ROOT / "tests/broken/wrong_truth_table.aig",
                              tmp_path / "full.jsonl.gz") == 0


def test_cutcheck_fails_on_empty_input(tmp_path):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")
    p = cli("cutcheck", "--aig", "tests/broken/wrong_truth_table.aig", "--cuts", str(empty))
    assert p.returncode == 1 and "no cuts" in p.stdout                # finding 13: was "0/0 agree", exit 0


def test_checked_count_is_independent_of_total(tmp_path):
    s = cutflow.process(paths.ROOT / "tests/broken/wrong_truth_table.aig", tmp_path,
                        tmp_path / "full.jsonl.gz", "synth")
    assert s["cuts_passed"] + len(s["failures"]) == s["cuts_checked"] == s["cuts_total"]
    assert sum(s["p_histogram"].values()) == s["cuts_total"]          # finding 14: P classes kept
