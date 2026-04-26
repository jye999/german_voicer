from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from .core import synthesize_voice, translate_text
from .translation import language_name, supported_language_flows


def run_once(
    text: str,
    speaker: Path,
    out: Path,
    *,
    language_flow: str = "en-de",
    ref_text: str | None = None,
    auto_transcribe_reference: bool = False,
) -> None:
    flow = supported_language_flows()[language_flow]
    source_language = flow.source_language
    target_language = flow.target_language
    target_text = (
        text.strip()
        if source_language == target_language
        else translate_text(text, source_language, target_language)
    )
    print(f"{language_name(source_language)}: {text}")
    if source_language == target_language:
        print("Translation skipped.")
    print(f"{language_name(target_language)}: {target_text}")
    synthesize_voice(
        target_text,
        speaker,
        out,
        language=language_name(target_language),
        ref_text=ref_text,
        auto_transcribe_reference=auto_transcribe_reference,
    )
    print(f"Saved audio: {out}")


def interactive_loop(
    speaker: Path,
    out_dir: Path,
    *,
    language_flow: str = "en-de",
    ref_text: str | None = None,
    auto_transcribe_reference: bool = False,
) -> None:
    """Interactive mode. Env overrides: VOICER_REF_TEXT, VOICER_AUTO_TRANSCRIBE=1."""
    flow = supported_language_flows()[language_flow]
    ref_final = (os.environ.get("VOICER_REF_TEXT", "").strip() or None) or (ref_text and ref_text.strip()) or None
    auto_env = os.environ.get("VOICER_AUTO_TRANSCRIBE", "").lower() in ("1", "true", "yes")
    use_auto = (auto_transcribe_reference or auto_env) and not ref_final

    prompt_language = language_name(flow.source_language)
    print(f"Enter {prompt_language} text. Press Ctrl+C or Ctrl+D to quit.")
    if ref_final:
        print("ICL mode: fixed reference transcript (CLI / VOICER_REF_TEXT).")
    elif use_auto:
        print("ICL mode: Whisper auto-transcribe on each generation (slow on CPU).")

    i = 1
    while True:
        try:
            text = input(f"{prompt_language}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if not text:
            continue
        out = out_dir / f"voice_{flow.target_language}_{i:03d}.wav"
        run_once(
            text,
            speaker,
            out,
            language_flow=language_flow,
            ref_text=ref_final,
            auto_transcribe_reference=use_auto,
        )
        i += 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate selected local language pairs, or speak directly, with Qwen3-TTS voice cloning."
    )
    parser.add_argument("--text", help="Text to speak. Omit for interactive mode.")
    parser.add_argument(
        "--language-flow",
        choices=tuple(supported_language_flows()),
        default="en-de",
        help="Source/target flow. Same-language flows speak directly without translation.",
    )
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
        default=Path("outputs/voice.wav"),
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
        run_once(
            args.text,
            args.speaker,
            args.out,
            language_flow=args.language_flow,
            ref_text=ref,
            auto_transcribe_reference=auto,
        )
    else:
        interactive_loop(
            args.speaker,
            args.out_dir,
            language_flow=args.language_flow,
            ref_text=ref,
            auto_transcribe_reference=auto,
        )


if __name__ == "__main__":
    main()
