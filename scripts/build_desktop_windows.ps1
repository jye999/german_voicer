$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  Write-Host "cargo not found. Installing Rust toolchain with rustup..."
  $RustupInstaller = Join-Path $env:TEMP "rustup-init.exe"
  Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile $RustupInstaller
  & $RustupInstaller -y --default-toolchain stable
  if ($LASTEXITCODE -ne 0) {
    throw "Rust installation failed. Install Rust manually from https://rustup.rs/ and retry."
  }
  $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
  throw "cargo still not found after installation. Open a new shell (or add %USERPROFILE%\\.cargo\\bin to PATH) and retry."
}

& "$RootDir/scripts/build_backend_dist.ps1"

Push-Location "$RootDir/desktop"
npm install
npm run tauri:build
Pop-Location

Write-Host "Windows desktop bundles created under desktop/src-tauri/target/release/bundle"
