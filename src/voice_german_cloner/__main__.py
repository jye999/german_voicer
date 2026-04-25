from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .core import synthesize_german_voice, translate_english_to_german


def run_once(text: str, speaker: Path, out: Path) -> None:
    german = translate_english_to_german(text)
    print(f"English: {text}")
    print(f"German:  {german}")
    synthesize_german_voice(german, speaker, out)
    print(f"Saved audio: {out}")


def interactive_loop(speaker: Path, out_dir: Path) -> None:
    print("Enter English text. Press Ctrl+C or Ctrl+D to quit.")
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
        run_once(text, speaker, out)
        i += 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Translate English text to German and speak it using a cloned reference voice."
    )
    parser.add_argument("--text", help="English text to translate and speak. Omit for interactive mode.")
    parser.add_argument(
        "--speaker",
        required=True,
        type=Path,
        help="Path to a clean reference recording of your voice, e.g. voice_samples/my_voice.wav",
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
    if args.text:
        run_once(args.text, args.speaker, args.out)
    else:
        interactive_loop(args.speaker, args.out_dir)


if __name__ == "__main__":
    main()
