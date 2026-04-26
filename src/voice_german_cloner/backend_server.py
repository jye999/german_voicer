from __future__ import annotations

import argparse
from pathlib import Path

from .web import run_web_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Desktop backend worker for German Voicer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--sample-dir", default="voice_samples")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run_web_server(
        host=args.host,
        port=args.port,
        output_dir=Path(args.output_dir),
        sample_dir=Path(args.sample_dir),
        debug=False,
    )


if __name__ == "__main__":
    main()
