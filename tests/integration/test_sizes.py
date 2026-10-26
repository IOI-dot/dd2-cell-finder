"""Repository rules (overview 5.1, AGENTS.md): no file over 50 MB, broken cases unchanged,
supplied inputs and the PDK not inside the repository."""
import hashlib
import subprocess

from dd2 import paths

LIMIT = 50 * 1024 * 1024


def test_no_result_file_over_50mb():
    big = [p for p in paths.results().rglob("*") if p.is_file() and p.stat().st_size > LIMIT]
    assert not big, big


def test_broken_cases_match_their_checksums():
    broken = paths.ROOT / "tests" / "broken"
    sums = (broken / "SHA256SUMS").read_text().split("\n")
    for line in filter(None, sums):
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((broken / name).read_bytes()).hexdigest() == digest, name
    listed = {l.split(maxsplit=1)[1].removeprefix("./") for l in sums if l}
    present = {str(p.relative_to(broken)) for p in broken.rglob("*") if p.is_file()} - {"SHA256SUMS"}
    assert present == listed, "a broken case was added or removed without updating SHA256SUMS"


def test_inputs_not_tracked():
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=paths.ROOT).stdout
    bad = [f for f in tracked.splitlines()
           if f.startswith(("DD2_Project1_student_pack/", "given/", "pdk/", "references/", "build/"))
           or f.endswith(".pdf")]
    assert not bad, bad[:5]
