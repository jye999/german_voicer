"""Local ASR for reference clips (Whisper via transformers)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _whisper_model_id() -> str:
    return os.environ.get("WHISPER_ASR_MODEL", "openai/whisper-tiny").strip() or "openai/whisper-tiny"


@lru_cache(maxsize=1)
def _asr_pipeline(model_id: str):
    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    return pipeline(
        "automatic-speech-recognition",
        model=model_id,
        device=device,
    )


def transcribe_reference_audio(path: Path, model_id: str | None = None) -> str:
    """Transcribe reference speech to text (16 kHz mono). Requires librosa (from qwen-tts deps)."""
    import librosa

    if not path.is_file():
        raise FileNotFoundError(f"Reference audio not found: {path}")
    y, sr = librosa.load(str(path), sr=16_000, mono=True)
    resolved_model_id = (model_id or _whisper_model_id()).strip() or _whisper_model_id()
    pipe = _asr_pipeline(resolved_model_id)
    result = pipe({"array": y, "sampling_rate": sr})
    return (result.get("text") or "").strip()
