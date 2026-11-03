"""Speech to text with Parakeet TDT 0.6 v3, on this machine only.

The model is the copy Handy keeps, read in place. It loads on the first recording and stays loaded,
so that the server stays light for anyone who never presses the mic. Audio is never written to disk.
"""
import io
import threading
import wave
from pathlib import Path

import numpy as np

from . import model

RATE = 16000
MAX_BYTES = 2 * RATE * 120               # two minutes of 16-bit mono, as far as a message needs
MODEL_DIR = Path(model.load_config().get("voice", {}).get("model_dir", "")).expanduser()
_model = None
_lock = threading.Lock()


class Unavailable(RuntimeError):
    """The model or its runtime is not on this machine."""


def samples(body: bytes) -> np.ndarray:
    """16 kHz mono 16-bit WAV as floats in [-1, 1]. Anything else is a ValueError."""
    try:
        with wave.open(io.BytesIO(body)) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (RATE, 1, 2):
                raise ValueError("expected 16 kHz mono 16-bit audio")
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    except (wave.Error, EOFError) as e:
        raise ValueError("not a WAV recording") from e


def load():
    global _model
    with _lock:
        if _model is None:
            if not (MODEL_DIR / "encoder-model.int8.onnx").is_file():
                raise Unavailable("the Parakeet model is not at the configured path")
            try:
                import onnx_asr
            except ImportError as e:
                raise Unavailable("the speech runtime is not installed: make setup") from e
            _model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", MODEL_DIR, quantization="int8")
        return _model


def transcribe(body: bytes) -> str:
    audio = samples(body)
    return str(load().recognize(audio, sample_rate=RATE)).strip()
