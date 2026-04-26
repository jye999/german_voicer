$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DistDir = Join-Path $RootDir "backend-dist"

Write-Host "Building backend bundle into: $DistDir"
if (Test-Path $DistDir) {
  Remove-Item -Recurse -Force $DistDir
}
New-Item -ItemType Directory -Path $DistDir | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv not found. Install from https://github.com/astral-sh/uv"
}

Set-Location $RootDir
uv sync --extra bundle

uv run pyinstaller `
  --noconfirm `
  --onefile `
  --name voice-german-backend `
  --collect-all qwen_tts `
  --paths "$RootDir/src" `
  "$RootDir/src/voice_german_cloner/backend_server.py"

Copy-Item "$RootDir/dist/voice-german-backend.exe" "$DistDir/voice-german-backend.exe" -Force
Write-Host "Backend artifact ready: $DistDir/voice-german-backend.exe"
