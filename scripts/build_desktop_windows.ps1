$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Get-VsDevCmdPath {
  $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
  if (-not (Test-Path $vswhere)) {
    return $null
  }
  $installCandidates = @(
    (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath),
    (& $vswhere -latest -products * -property installationPath)
  ) | Where-Object { $_ -and $_.Trim() -ne "" } | Select-Object -Unique

  foreach ($installPath in $installCandidates) {
    $vsDevCmd = Join-Path $installPath "Common7\Tools\VsDevCmd.bat"
    if (Test-Path $vsDevCmd) {
      return $vsDevCmd
    }

    $vcVars64 = Join-Path $installPath "VC\Auxiliary\Build\vcvars64.bat"
    if (Test-Path $vcVars64) {
      return $vcVars64
    }
  }

  return $null
}

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

$vsDevCmd = Get-VsDevCmdPath
if (-not $vsDevCmd) {
  throw @"
MSVC linker (link.exe) is not available.
Install Visual Studio Build Tools with C++ tools, then rerun:
  winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools"
"@
}

& "$RootDir/scripts/build_backend_dist.ps1"

Push-Location "$RootDir/desktop"
npm install
$escapedVsDevCmd = $vsDevCmd -replace '"', '""'
if ($vsDevCmd -like "*VsDevCmd.bat") {
  cmd /c "`"$escapedVsDevCmd`" -arch=x64 -host_arch=x64 && where link && npm run tauri:build"
} else {
  cmd /c "`"$escapedVsDevCmd`" && where link && npm run tauri:build"
}
if ($LASTEXITCODE -ne 0) {
  throw "tauri build failed (exit code $LASTEXITCODE)."
}
Pop-Location

Write-Host "Windows desktop bundles created under desktop/src-tauri/target/release/bundle"
