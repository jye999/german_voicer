from __future__ import annotations

from pathlib import Path


def translate_english_to_german(text: str) -> str:
    """Translate English text to German."""
    text = text.strip()
    if not text:
        raise ValueError("Text cannot be empty.")

    from deep_translator import GoogleTranslator

    return GoogleTranslator(source="en", target="de").translate(text)


def synthesize_german_voice(german_text: str, speaker_wav: Path, output_path: Path) -> None:
    """Speak German text using a reference speaker WAV/MP3."""
    if not speaker_wav.exists():
        raise FileNotFoundError(f"Speaker sample not found: {speaker_wav}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    from TTS.api import TTS

    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    tts.tts_to_file(
        text=german_text,
        speaker_wav=str(speaker_wav),
        language="de",
        file_path=str(output_path),
    )
