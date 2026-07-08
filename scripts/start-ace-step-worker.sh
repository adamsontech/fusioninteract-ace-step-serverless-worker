#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${ACESTEP_CHECKPOINTS_DIR:-/runpod-volume/ace-step-models}"
cd "${ACESTEP_HOME:-/opt/ACE-Step-1.5}"

exec python -u /worker/handler.py
