#!/usr/bin/env bash
set -euo pipefail

# bge-m3 as GGUF, served by llama.cpp on :8081 (spec §7).
# CLS pooling; non-causal attention means n_ubatch must be >= the longest
# sequence in a batch — hence ubatch equals ctx (2048) and chunk size is
# capped at ~1000 tokens downstream (§9). Output dimension is 1024 and is
# asserted on the first embedding call (§7).

MODEL_FILE="${MODEL_FILE:-bge-m3-Q8_0.gguf}"

exec llama-server \
  --model "/models/${MODEL_FILE}" \
  --alias bge-m3 \
  --host 0.0.0.0 --port 8081 \
  --embedding \
  --pooling cls \
  --n-gpu-layers 99 \
  --ctx-size 2048 \
  --batch-size 2048 \
  --ubatch-size 2048
