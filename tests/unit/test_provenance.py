import json

from dd2 import provenance as pv


def test_sha256_and_record_roundtrip(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("abc")
    assert pv.sha256(f) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    rec = pv.RunRecord(argv=["echo"], inputs=pv.hash_inputs([f]))
    rec.finish(0, logs=[str(f)])
    out = tmp_path / "r.json"
    pv.write_json(out, {"run": rec.asdict()})
    d = json.loads(out.read_text())["run"]
    assert d["status"] == "pass" and d["exit_code"] == 0 and d["finished"] >= d["started"]
    rec2 = pv.RunRecord(argv=["false"])
    rec2.finish(1)
    assert rec2.status == "fail"
