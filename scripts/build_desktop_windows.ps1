$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

& "$RootDir/scripts/build_backend_dist.ps1"

Push-Location "$RootDir/desktop"
npm install
npm run tauri:build
Pop-Location

Write-Host "Windows desktop bundles created under desktop/src-tauri/target/release/bundle"
