#!/usr/bin/env bash
set -euo pipefail

# Qwen3.5-4B Q8_0, full GPU offload (spec §6). llama.cpp pinned to b9222 via
# the image build (spec §1.1/§3.3) — required for the `qwen35` arch.
#
# --ctx-size is a PLACEHOLDER until Step 9 measures real KV size from the
# server log ("llama_context: KV self size = ...") and re-runs the VRAM gate
# (≤ 13.5 GB with embed + rerank servers up). Then replace CTX_SIZE and
# re-run the gate. Never enable MTP untested (spec §1.5).

CTX_SIZE="${CTX_SIZE:-32768}"
PARALLEL="${PARALLEL:-2}"
MODEL_FILE="${MODEL_FILE:-Qwen_Qwen3.5-4B-Q8_0.gguf}"

ARGS=(
  --model "/models/${MODEL_FILE}"
  --alias qwen35-4b
  --host 0.0.0.0 --port 8080

  --n-gpu-layers 99
  --ctx-size "${CTX_SIZE}"
  --parallel "${PARALLEL}"
  --cont-batching

  --flash-attn on
  --cache-type-k q8_0
  --cache-type-v q8_0
  --batch-size 2048
  --ubatch-size 512

  --jinja

  --slots
  --metrics
  --timeout 600
)

if [[ "${ENABLE_MTP:-false}" == "true" ]]; then
  ARGS+=( --spec-type draft-mtp )
fi

# Reasoning control: flag names MUST be confirmed against
# `llama-server --help | grep -iE "reasoning|think"` (spec §1.3 VERIFY).
# Leave REASONING_FORMAT empty until that output is recorded in
# artifacts/verification.md; llm/client.py ships the streaming fallback
# state machine regardless (spec §1.3).
if [[ -n "${REASONING_FORMAT:-}" ]]; then
  ARGS+=( --reasoning-format "${REASONING_FORMAT}" )
fi

exec llama-server "${ARGS[@]}"
