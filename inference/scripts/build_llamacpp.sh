#!/usr/bin/env bash
set -euo pipefail

# Build llama.cpp and copy the llama-server binary to inference/bin/.
# Linux/CUDA target. Run under WSL2 or a Linux host.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILDDIR="${ROOT}/build_llamacpp"
BINDIR="${ROOT}/bin"

mkdir -p "${BINDIR}"

if [ ! -d "${BUILDDIR}" ]; then
  git clone --depth 1 https://github.com/ggerganov/llama.cpp "${BUILDDIR}"
else
  echo "[build_llamacpp] repo clone already present at ${BUILDDIR}, updating..."
  git -C "${BUILDDIR}" pull --rebase || true
fi

# Enable CUDA if a CUDA toolkit is detected, otherwise fall back to CPU.
CMAKE_ARGS=(-DCMAKE_BUILD_TYPE=Release)
if command -v nvcc >/dev/null 2>&1 || [ -d /usr/local/cuda ]; then
  echo "[build_llamacpp] CUDA detected; enabling GGML_CUDA=ON"
  CMAKE_ARGS+=(-DGGML_CUDA=ON)
fi

cmake -S "${BUILDDIR}" -B "${BUILDDIR}/build" "${CMAKE_ARGS[@]}"
cmake --build "${BUILDDIR}/build" --config Release --target llama-server -- -j"$(nproc 2>/dev/null || echo 2)"

SERVER_BIN="${BUILDDIR}/build/bin/llama-server"
if [ ! -f "${SERVER_BIN}" ]; then
  # Alternative location (newer llama.cpp layout)
  SERVER_BIN="${BUILDDIR}/build/llama-server"
fi
if [ ! -f "${SERVER_BIN}" ]; then
  echo "[build_llamacpp] FATAL: llama-server binary not found after build" >&2
  exit 1
fi

cp "${SERVER_BIN}" "${BINDIR}/llama-server"
chmod +x "${BINDIR}/llama-server"
echo "[build_llamacpp] SUCCESS: ${BINDIR}/llama-server"
