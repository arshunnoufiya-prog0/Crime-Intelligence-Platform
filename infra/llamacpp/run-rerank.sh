#!/usr/bin/env bash
set -euo pipefail

# bge-reranker-v2-m3 Q8_0 on :8082 (spec §8). Default ENABLE_RERANK=true.
#
# RERANK_FLAGS: the exact flag and endpoint path MUST come from
# `llama-server --help | grep -i rerank` (spec §8 VERIFY — pending on the
# b9222 build). The default below follows llama.cpp's current convention
# (--reranking, /v1/rerank) but is env-overridable so the verified values
# can be recorded in artifacts/verification.md and pinned in .env without
# a code change. If the build has NO rerank support, leave this container
# stopped (no profile) and set ENABLE_RERANK=false — never emulate
# reranking with a generation prompt (spec §8).

MODEL_FILE="${MODEL_FILE:-bge-reranker-v2-m3-Q8_0.gguf}"
RERANK_FLAGS="${RERANK_FLAGS:---reranking}"

exec llama-server \
  --model "/models/${MODEL_FILE}" \
  --alias bge-reranker \
  --host 0.0.0.0 --port 8082 \
  --n-gpu-layers 99 \
  --ctx-size 2048 \
  --batch-size 2048 \
  --ubatch-size 2048 \
  ${RERANK_FLAGS}
