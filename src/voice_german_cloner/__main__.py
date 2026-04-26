from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from .core import synthesize_german_voice, translate_english_to_german


def run_once(
    text: str,
    speaker: Path,
    out: Path,
    *,
    ref_text: str | None = None,
    auto_transcribe_reference: bool = False,
) -> None:
    german = translate_english_to_german(text)
    print(f"English: {text}")
    print(f"German:  {german}")
    synthesize_german_voice(
        german,
        speaker,
        out,
        ref_text=ref_text,
        auto_transcribe_reference=auto_transcribe_reference,
    )
    print(f"Saved audio: {out}")


def interactive_loop(
    speaker: Path,
    out_dir: Path,
    *,
    ref_text: str | None = None,
    auto_transcribe_reference: bool = False,
) -> None:
    """Interactive mode. Env overrides: VOICER_REF_TEXT, VOICER_AUTO_TRANSCRIBE=1."""
    ref_final = (os.environ.get("VOICER_REF_TEXT", "").strip() or None) or (ref_text and ref_text.strip()) or None
    auto_env = os.environ.get("VOICER_AUTO_TRANSCRIBE", "").lower() in ("1", "true", "yes")
    use_auto = (auto_transcribe_reference or auto_env) and not ref_final

    print("Enter English text. Press Ctrl+C or Ctrl+D to quit.")
    if ref_final:
        print("ICL mode: fixed reference transcript (CLI / VOICER_REF_TEXT).")
    elif use_auto:
        print("ICL mode: Whisper auto-transcribe on each generation (slow on CPU).")

    i = 1
    while True:
        try:
            text = input("English> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if not text:
            continue
        out = out_dir / f"german_voice_{i:03d}.wav"
        run_once(
            text,
            speaker,
            out,
            ref_text=ref_final,
            auto_transcribe_reference=use_auto,
        )
        i += 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate English to German locally, then speak German with Qwen3-TTS voice cloning."
    )
    parser.add_argument("--text", help="English text to translate and speak. Omit for interactive mode.")
    parser.add_argument(
        "--speaker",
        required=True,
        type=Path,
        help="Reference clip for voice cloning (WAV/MP3/M4A), e.g. voice_samples/my_voice.wav",
    )
    parser.add_argument(
        "--ref-text",
        type=str,
        default=None,
        help="Exact transcript of the reference clip for stronger ICL cloning (omit for embedding-only).",
    )
    parser.add_argument(
        "--auto-transcribe-reference",
        action="store_true",
        help="Run Whisper (English) on --speaker; ignored if --ref-text is set.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/german_voice.wav"),
        help="Output WAV path for one-shot mode.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("outputs"),
        help="Output directory for interactive mode.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    ref = (args.ref_text or "").strip() or None
    auto = bool(args.auto_transcribe_reference) and not ref
    if args.text:
        run_once(args.text, args.speaker, args.out, ref_text=ref, auto_transcribe_reference=auto)
    else:
        interactive_loop(
            args.speaker,
            args.out_dir,
            ref_text=ref,
            auto_transcribe_reference=auto,
        )


if __name__ == "__main__":
    main()
