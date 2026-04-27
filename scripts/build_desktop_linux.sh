#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo not found. Install Rust first (https://rustup.rs), then retry."
  echo "Quick install: curl https://sh.rustup.rs -sSf | sh -s -- -y"
  exit 1
fi

"$ROOT_DIR/scripts/build_backend_dist.sh"

cd "$ROOT_DIR/desktop"
npm install
npm run tauri:build

echo "Linux desktop bundles created under desktop/src-tauri/target/release/bundle"
