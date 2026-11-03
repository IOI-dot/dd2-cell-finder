"""Speech to text: the audio stays on this machine, and only a valid short recording is accepted."""
import io
import wave

import pytest

pytest.importorskip("ag_ui_langgraph", reason="make setup installs the web extra")
from fastapi.testclient import TestClient

from dd2_agent import server, voice


def wav(rate=16000, channels=1, frames=1600):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x10" * frames * channels)
    return b.getvalue()


def test_a_wav_becomes_samples_between_minus_one_and_one():
    s = voice.samples(wav(frames=100))
    assert len(s) == 100 and abs(float(s[0]) - 0x1000 / 32768) < 1e-6


@pytest.mark.parametrize("bad", [b"", b"not audio", wav(rate=44100), wav(channels=2)])
def test_anything_else_is_refused(bad):
    with pytest.raises(ValueError):
        voice.samples(bad)


def test_the_route_returns_the_text(monkeypatch):
    monkeypatch.setattr(voice, "transcribe", lambda body: "build a nand gate")
    r = TestClient(server.create_app()).post("/api/transcribe", content=wav())
    assert r.status_code == 200 and r.json() == {"text": "build a nand gate"}


def test_the_route_refuses_bad_audio_and_oversize():
    client = TestClient(server.create_app())
    assert client.post("/api/transcribe", content=b"nope").status_code == 400
    assert client.post("/api/transcribe", content=b"0" * (voice.MAX_BYTES + 1)).status_code == 413


def test_a_missing_model_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(voice, "MODEL_DIR", tmp_path / "gone")
    monkeypatch.setattr(voice, "_model", None)
    r = TestClient(server.create_app()).post("/api/transcribe", content=wav())
    assert r.status_code == 503 and "gone" not in r.text
