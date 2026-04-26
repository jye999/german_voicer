"""Local ASR for reference clips (Whisper via transformers)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _whisper_model_id() -> str:
    return os.environ.get("WHISPER_ASR_MODEL", "openai/whisper-base").strip() or "openai/whisper-base"


@lru_cache(maxsize=1)
def _asr_pipeline():
    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    return pipeline(
        "automatic-speech-recognition",
        model=_whisper_model_id(),
        device=device,
    )


def transcribe_reference_audio(path: Path) -> str:
    """Transcribe reference speech to text (16 kHz mono). Requires librosa (from qwen-tts deps)."""
    import librosa

    if not path.is_file():
        raise FileNotFoundError(f"Reference audio not found: {path}")
    y, sr = librosa.load(str(path), sr=16_000, mono=True)
    pipe = _asr_pipeline()
    result = pipe({"array": y, "sampling_rate": sr})
    return (result.get("text") or "").strip()
