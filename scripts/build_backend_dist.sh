#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/backend-dist"

echo "Building backend bundle into: $DIST_DIR"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install from https://github.com/astral-sh/uv"
  exit 1
fi

cd "$ROOT_DIR"
uv sync --extra bundle

uv run pyinstaller \
  --noconfirm \
  --onefile \
  --name voice-german-backend \
  --collect-all qwen_tts \
  --paths "$ROOT_DIR/src" \
  "$ROOT_DIR/src/voice_german_cloner/backend_server.py"

cp "$ROOT_DIR/dist/voice-german-backend" "$DIST_DIR/voice-german-backend"
chmod +x "$DIST_DIR/voice-german-backend"

echo "Backend artifact ready: $DIST_DIR/voice-german-backend"
