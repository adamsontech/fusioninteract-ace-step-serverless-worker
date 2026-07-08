param(
  [string]$InstallDir = "C:\ace-step\ACE-Step-1.5",
  [string]$RepoUrl = "https://github.com/ace-step/ACE-Step-1.5.git",
  [switch]$SkipSync
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "Git is required to install ACE-Step."
}

if (-not (Test-Path -LiteralPath $InstallDir)) {
  New-Item -ItemType Directory -Path (Split-Path -Parent $InstallDir) -Force | Out-Null
  git clone $RepoUrl $InstallDir
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host "Installing uv..."
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
}

if (-not $SkipSync) {
  Push-Location $InstallDir
  try {
    uv sync
  }
  finally {
    Pop-Location
  }
}

Write-Host "ACE-Step local install staged at $InstallDir"
Write-Host "Launch API with: cd `"$InstallDir`"; uv run acestep-api --host 127.0.0.1 --port 8001"
