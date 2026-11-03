import json
import subprocess
import sys

from dd2 import paths

DD2 = [sys.executable, "-m", "dd2"]
_os = __import__("os")
ENV = {"PYTHONPATH": str(paths.ROOT / "src"), "PATH": _os.environ["PATH"]} | \
      {k: v for k, v in _os.environ.items() if k in ("DD2_PDK_REALPATH", "DD2_IN_CONTAINER")}


def run(*args):
    return subprocess.run(DD2 + list(args), capture_output=True, text=True, cwd=paths.ROOT, env=ENV)


def test_check_fails_on_missing_given(tmp_path):
    p = run("check", "--given", "tests/broken/missing_given", "--out", str(tmp_path / "env.json"))
    assert p.returncode == 1
    assert "hd_reduced.lib" in p.stdout and "make setup" in p.stdout
    assert json.loads((tmp_path / "env.json").read_text())["status"] == "fail"


def test_check_passes_on_real_inputs(tmp_path):
    p = run("check", "--out", str(tmp_path / "env.json"))
    assert p.returncode == 0, p.stdout + p.stderr
    env = json.loads((tmp_path / "env.json").read_text())
    assert env["liberty_import"] == {"hd_reduced.lib": 189, "hd_usable.lib": 307}
    assert env["full_hd_lib"]["cells"] == 428


def test_usage_error_exit_2():
    assert run("no-such-command").returncode == 2


def test_environment_record_is_portable(tmp_path):
    run("check", "--out", str(tmp_path / "env.json"))
    env = json.loads((tmp_path / "env.json").read_text())
    text = json.dumps(env)
    assert str(paths.ROOT) not in text and "/Users/" not in text    # relative paths only
    assert env["pdk_version"].startswith("ciel ")                   # PDK revision recorded


def test_course_image_and_stress_test_recorded(tmp_path):
    # overview 5.1: make check runs the ngspice stress test (Option 1)
    import os
    if os.environ.get("DD2_IN_CONTAINER"):
        return
    run("check", "--out", str(tmp_path / "env.json"))
    env = json.loads((tmp_path / "env.json").read_text())
    st = env["course_image"]
    assert st["stress_test"] == "pass" and st["ngspice"].startswith("ngspice-47")
    assert len(st["ngspice_sha256"]) == 64 and st["magic"].startswith("8.3") and st["netgen"]


def test_hd_views_required_and_hashed(tmp_path):
    # Option 1 needs the HD GDS and SPICE views; make check verifies them and records their hashes
    run("check", "--out", str(tmp_path / "env.json"))
    v = json.loads((tmp_path / "env.json").read_text())["hd_views"]
    for view in ("gds", "spice", "lef", "mag"):
        assert v[view]["present"], view
    assert len(v["gds"]["sha256"]) == 64 and len(v["spice"]["sha256"]) == 64
