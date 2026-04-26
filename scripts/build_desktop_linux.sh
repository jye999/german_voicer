#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/build_backend_dist.sh"

cd "$ROOT_DIR/desktop"
npm install
npm run tauri:build

echo "Linux desktop bundles created under desktop/src-tauri/target/release/bundle"
