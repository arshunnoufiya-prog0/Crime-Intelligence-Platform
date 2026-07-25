#!/usr/bin/env bash
set -euo pipefail

# Download Qwen2.5-4B-Instruct (GGUF, Q8_0) into inference/models/.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS="${ROOT}/models"
mkdir -p "${MODELS}"

FILE="Qwen2.5-4B-Instruct-Q8_0.gguf"

if command -v huggingface-cli >/dev/null 2>&1; then
  HF=huggingface-cli
else
  echo "[download_model] huggingface-cli not found; install 'huggingface_hub[cli]' first." >&2
  exit 1
fi

"$HF" download bartowski/Qwen2.5-4B-Instruct-GGUF \
  --include "${FILE}" \
  --local-dir "${MODELS}"

DEST="${MODELS}/${FILE}"
if [ ! -f "${DEST}" ]; then
  echo "[download_model] FATAL: ${DEST} not present after download" >&2
  exit 1
fi

SIZE_BYTES=$(stat -c %s "${DEST}" 2>/dev/null || stat -f %z "${DEST}")
SIZE_MB=$((SIZE_BYTES / 1024 / 1024))
CHECKSUM=$(sha256sum "${DEST}" | awk '{print $1}')

echo "[download_model] SUCCESS"
echo "  path:     ${DEST}"
echo "  size:     ${SIZE_MB} MB"
echo "  sha256:   ${CHECKSUM}"
