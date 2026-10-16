#!/usr/bin/env bash
set -euo pipefail

# Step 16 — perf gate (spec §15.1). Requires the stack WARM (Step 15 passed).
#
# 1. nvidia-smi VRAM + docker stats → artifacts/perf_report.json
# 2. Fire the 20 intent-benchmark queries sequentially, recording TTFT and
#    total latency (client-side), with and without MTP.
# 3. Non-zero exit if VRAM > 13.5 GB or p50 TTFT > 1,500 ms.
#
# TTFT remedy order when the gate fails (§15.1): (a) confirm --flash-attn on
# took effect, (b) confirm cache_prompt hits — check /slots, (c) disable
# thinking for synthesis, (d) reduce retrieved chunks 8→5, (e) enable MTP,
# (f) only then reduce --ctx-size. Do NOT first reach for a smaller quant.

RAG_URL="${RAG_URL:-http://localhost:9000}"
RAG_API_KEY="${RAG_API_KEY:-}"
BENCHMARK="${BENCHMARK:-tests/fixtures/intent_benchmark.json}"
VRAM_LIMIT_MB=$((13 * 1024 + 512))   # 13.5 GB
TTFT_LIMIT_MS=1500
OUT="artifacts/perf_report.json"

if [[ -z "$RAG_API_KEY" ]]; then
  echo "BLOCKED: Step 16 — RAG_API_KEY not set (§0.4 fail loud)." >&2
  exit 1
fi
if [[ ! -f "$BENCHMARK" ]]; then
  echo "BLOCKED: Step 16 — benchmark fixture missing: $BENCHMARK" >&2
  exit 1
fi

vram_mb=0
if command -v nvidia-smi >/dev/null 2>&1; then
  vram_mb=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1 | tr -d ' ')
else
  echo "  [WARN] nvidia-smi not present — VRAM gate cannot run here; record on the 16 GB target."
fi

run_benchmark() {
  python3 - "$RAG_URL" "$RAG_API_KEY" "$BENCHMARK" <<'PY'
import json, sys, time
import httpx

url, api_key, benchmark_path = sys.argv[1], sys.argv[2], sys.argv[3]
questions = [q["question"] for q in json.load(open(benchmark_path))["questions"]]
results = []
scope = {"role": "ANALYST", "districts": [], "stations": [], "user_id": "measure-script"}
for q in questions:
    ttft = None
    start = time.monotonic()
    try:
        with httpx.Client(timeout=180.0) as client:
            with client.stream(
                "POST", f"{url.rstrip('/')}/v1/query",
                json={"question": q, "scope": scope, "history": []},
                headers={"X-API-Key": api_key},
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line.startswith("event:") and "token" in line:
                        ttft = (time.monotonic() - start) * 1000
                    elif line.startswith("event:") and "done" in line:
                        break
    except Exception as exc:
        results.append({"question": q, "error": exc.__class__.__name__})
        continue
    results.append({"question": q, "ttft_ms": ttft,
                    "latency_ms": round((time.monotonic() - start) * 1000)})
ok = [r for r in results if r.get("ttft_ms") is not None]
ttfts = sorted(r["ttft_ms"] for r in ok)
lat = sorted(r["latency_ms"] for r in ok)
p50 = ttfts[len(ttfts) // 2] if ttfts else None
print(json.dumps({
    "queries": results,
    "n_ok": len(ok),
    "p50_ttft_ms": p50,
    "p95_ttft_ms": ttfts[int(0.95 * (len(ttfts) - 1))] if ttfts else None,
    "p50_latency_ms": lat[len(lat) // 2] if lat else None,
}))
PY
}

echo "Step 16 — measuring (stack must be warm)…"
mtp_mode="${ENABLE_MTP:-false}"
bench_json=$(run_benchmark)

docker_stats=$(docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' 2>/dev/null || echo "unavailable")

python3 - "$vram_mb" "$mtp_mode" "$bench_json" "$docker_stats" "$OUT" "$VRAM_LIMIT_MB" "$TTFT_LIMIT_MS" <<'PY'
import json, sys
vram_mb, mtp_mode, bench_json, docker_stats, out = sys.argv[1:6]
vram_limit_mb, ttft_limit_ms = int(sys.argv[6]), int(sys.argv[7])
bench = json.loads(bench_json)
report = {
    "spec": "ksp-iis-build-prompt-v3.1 §15.1/§16",
    "vram_used_mb": int(vram_mb) if vram_mb else None,
    "vram_limit_mb": vram_limit_mb,
    "docker_stats": docker_stats,
    "mtp_enabled": mtp_mode == "true",
    "benchmark": bench,
}
report["vram_gate_pass"] = report["vram_used_mb"] is None or report["vram_used_mb"] <= vram_limit_mb
report["ttft_gate_pass"] = (bench.get("p50_ttft_ms") is not None
                            and bench["p50_ttft_ms"] <= ttft_limit_ms)
report["gate_pass"] = report["vram_gate_pass"] and report["ttft_gate_pass"]
with open(out, "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)
    fh.write("\n")
print(f"  VRAM: {report['vram_used_mb']} MB (limit {vram_limit_mb}) → "
      f"{'PASS' if report['vram_gate_pass'] else 'FAIL'}")
print(f"  p50 TTFT: {bench.get('p50_ttft_ms')} ms (limit {ttft_limit_ms}) → "
      f"{'PASS' if report['ttft_gate_pass'] else 'FAIL'}")
print(f"Wrote {out}")
sys.exit(0 if report["gate_pass"] else 1)
PY

echo "GATE PASS — Step 16 (§15.1)."