#!/usr/bin/env bash
set -euo pipefail

# Qwen3.5-4B-Instruct (GGUF, Q8_0) — placeholder/verification script.
#
# The GGUF model file is NOT downloaded automatically; it must be placed
# manually into inference/models/ before running the service. This script
# only verifies that the file is present and reports its size + checksum.
#
#   Expected path: inference/models/Qwen3.5-4B-Instruct-Q8_0.gguf
#
# Manual step (done outside this script):
#   - Either copy your local Qwen3.5-4B-Instruct-Q8_0.gguf into ./models/
#   - Or fetch it from Hugging Face and place it in ./models/ before running:
#
#       pip install -U "huggingface_hub[cli]"
#       huggingface-cli download <repo>/Qwen3.5-4B-Instruct-GGUF \
#           --include "Qwen3.5-4B-Instruct-Q8_0.gguf" \
#           --local-dir ./models
#
# This script simply validates that the model is in place.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS="${ROOT}/models"
mkdir -p "${MODELS}"

FILE="Qwen3.5-4B-Instruct-Q8_0.gguf"
DEST="${MODELS}/${FILE}"

if [ ! -f "${DEST}" ]; then
  echo "[check_model] FATAL: ${DEST} not found." >&2
  echo "[check_model] Please place the Qwen3.5-4B-Instruct Q8_0 GGUF file into ${MODELS}/ before starting the inference service." >&2
  exit 1
fi

SIZE_BYTES=$(stat -c %s "${DEST}" 2>/dev/null || stat -f %z "${DEST}")
SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
CHECKSUM=$(sha256sum "${DEST}" | awk '{print $1}')

echo "[check_model] SUCCESS"
echo "  path:     ${DEST}"
echo "  size:     ${SIZE_MB} MB"
echo "  sha256:   ${CHECKSUM}"
