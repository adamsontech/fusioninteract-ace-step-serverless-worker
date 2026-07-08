param(
  [string]$Python = "",
  [switch]$Docker
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workerDir = Resolve-Path (Join-Path $scriptDir "..")

if (-not $Python) {
  $Python = "python"
}

Push-Location $workerDir
try {
  & $Python -m py_compile handler.py
  if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed."
  }

  if ($Docker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
      throw "Docker is not installed or available on PATH."
    }
    & docker build -t fusioninteract/ace-step-serverless:smoke .
    if ($LASTEXITCODE -ne 0) {
      throw "Docker smoke build failed."
    }
  }
}
finally {
  Pop-Location
}
