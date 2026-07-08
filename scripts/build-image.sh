#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-fusioninteract/ace-step-serverless:latest}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
PUSH="${PUSH:-false}"
NO_CACHE="${NO_CACHE:-false}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available on PATH." >&2
  exit 1
fi

args=(build -f "${DOCKERFILE}" -t "${IMAGE}")
if [[ "${NO_CACHE}" == "true" ]]; then
  args+=(--no-cache)
fi
args+=(.)

cd "${WORKER_DIR}"
docker "${args[@]}"

if [[ "${PUSH}" == "true" ]]; then
  docker push "${IMAGE}"
fi
