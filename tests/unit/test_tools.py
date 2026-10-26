from dd2 import tools


def test_run_captures_log_and_exit(tmp_path):
    log = tmp_path / "l.log"
    code, secs = tools.run(["sh", "-c", "echo hi; echo err 1>&2; exit 3"], log)
    assert code == 3 and secs >= 0
    assert "hi" in log.read_text() and "err" in log.read_text()


def test_run_timeout(tmp_path):
    code, _ = tools.run(["sh", "-c", "sleep 5"], tmp_path / "t.log", timeout=0.5)
    assert code == 124
    assert "timeout" in (tmp_path / "t.log").read_text()


def test_missing_tool_is_none():
    assert tools.version(["definitely-not-a-tool-xyz", "-V"]) is None
    assert tools.version(["sh", "-c", "echo v1.2"]) == "v1.2"
