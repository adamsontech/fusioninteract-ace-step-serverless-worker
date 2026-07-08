param(
  [string]$Image = "fusioninteract/ace-step-serverless:latest",
  [string]$Dockerfile = "Dockerfile",
  [switch]$NoCache,
  [switch]$Push
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workerDir = Resolve-Path (Join-Path $scriptDir "..")

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker is not installed or is not available on PATH. Install Docker Desktop or run this script from a build host with Docker."
}

$args = @("build", "-f", $Dockerfile, "-t", $Image)
if ($NoCache) {
  $args += "--no-cache"
}
$args += "."

Push-Location $workerDir
try {
  & docker @args
  if ($LASTEXITCODE -ne 0) {
    throw "docker build failed with exit code $LASTEXITCODE"
  }
  if ($Push) {
    & docker push $Image
    if ($LASTEXITCODE -ne 0) {
      throw "docker push failed with exit code $LASTEXITCODE"
    }
  }
}
finally {
  Pop-Location
}
