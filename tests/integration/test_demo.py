import hashlib
import subprocess
import sys

from dd2 import paths

ENV = {"PYTHONPATH": str(paths.ROOT / "src"), "PATH": __import__("os").environ["PATH"]}


def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p).encode() + p.read_bytes())
    return h.hexdigest()


def test_demo_dsp8_leaves_results_untouched():
    before = tree_hash(paths.results())
    p = subprocess.run([sys.executable, "-m", "dd2", "demo", "given/designs/dsp8.v", "--top", "dsp8"],
                       capture_output=True, text=True, cwd=paths.ROOT, env=ENV)
    assert p.returncode == 0, p.stdout + p.stderr
    assert (paths.build("demo", "dsp8", "demo_summary.json")).exists()
    assert tree_hash(paths.results()) == before


def test_demo_finds_top_module_without_TOP():
    # finding 17: risc8's top is "cpu", not the file stem
    from dd2 import demo
    assert demo.detect_top(paths.given() / "designs" / "risc8.v", False) == "cpu"
