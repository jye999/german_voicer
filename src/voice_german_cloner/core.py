from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .translation import translate_english_to_german_local

# Default: smaller Base checkpoint. Override with QWEN3_TTS_MODEL (HF id or local path).
_DEFAULT_QWEN_TTS_MODEL = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"


def _qwen_model_id() -> str:
    return os.environ.get("QWEN3_TTS_MODEL", _DEFAULT_QWEN_TTS_MODEL).strip() or _DEFAULT_QWEN_TTS_MODEL


def translate_english_to_german(text: str) -> str:
    """Translate English text to German using a local model (no external translation API)."""
    return translate_english_to_german_local(text)


def _load_kwargs() -> dict:
    """Device / dtype / attention backend for Qwen3TTSModel.from_pretrained."""
    import torch

    if torch.cuda.is_available():
        bf16_ok = getattr(torch.cuda, "is_bf16_supported", lambda: False)()
        dtype = torch.bfloat16 if bf16_ok else torch.float16
        return {
            "device_map": "cuda:0",
            "dtype": dtype,
            "attn_implementation": "sdpa",
        }
    return {
        "device_map": "cpu",
        "dtype": torch.float32,
        "attn_implementation": "sdpa",
    }


@lru_cache(maxsize=1)
def _qwen_clone_model():
    from qwen_tts import Qwen3TTSModel

    return Qwen3TTSModel.from_pretrained(_qwen_model_id(), **_load_kwargs())


def synthesize_german_voice(
    german_text: str,
    speaker_wav: Path,
    output_path: Path,
    *,
    ref_text: str | None = None,
    auto_transcribe_reference: bool = False,
    asr_model: str | None = None,
) -> None:
    """Speak German with Qwen3-TTS Base clone.

    If ``ref_text`` is set (or ``auto_transcribe_reference`` produces text), uses full ICL
    cloning with ``x_vector_only_mode=False``. Otherwise uses speaker-embedding-only mode.
    """
    if not german_text.strip():
        raise ValueError("German text cannot be empty.")
    if not speaker_wav.exists():
        raise FileNotFoundError(f"Speaker sample not found: {speaker_wav}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    import soundfile as sf

    effective_ref = (ref_text or "").strip()
    if auto_transcribe_reference and not effective_ref:
        from .ref_audio_transcribe import transcribe_reference_audio

        effective_ref = transcribe_reference_audio(speaker_wav, model_id=asr_model).strip()

    use_icl = bool(effective_ref)

    model = _qwen_clone_model()
    if use_icl:
        wavs, sr = model.generate_voice_clone(
            text=german_text.strip(),
            language="German",
            ref_audio=str(speaker_wav),
            ref_text=effective_ref,
            x_vector_only_mode=False,
        )
    else:
        wavs, sr = model.generate_voice_clone(
            text=german_text.strip(),
            language="German",
            ref_audio=str(speaker_wav),
            x_vector_only_mode=True,
        )
    sf.write(str(output_path), wavs[0], sr)
