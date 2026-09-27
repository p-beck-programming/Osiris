from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path
from threading import Lock

_model = None
_model_lock = Lock()


def whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _get_model():
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            model_name = os.getenv("OSIRIS_WHISPER_MODEL", "base.en")
            _model = WhisperModel(model_name, device="cpu", compute_type="int8")
    return _model


def transcribe_bytes(data: bytes, content_type: str | None = None) -> str:
    if not whisper_available():
        raise RuntimeError("Local Whisper support is not installed")

    suffix = ".webm"
    if content_type:
        if "mp4" in content_type or "m4a" in content_type:
            suffix = ".m4a"
        elif "wav" in content_type:
            suffix = ".wav"
        elif "ogg" in content_type:
            suffix = ".ogg"

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(data)
            temp_path = Path(handle.name)

        model = _get_model()
        segments, _ = model.transcribe(str(temp_path), vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
