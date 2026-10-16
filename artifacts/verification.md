# artifacts/verification.md — all VERIFY: outputs (spec §0 rule 2, Step 0)

Every entry below is REAL command output or fetched documentation from this
build session (2026-09-22/23). Pending items are the launch-gated VERIFYs,
deliberately on hold per the user's code-first directive; they gate their
downstream wiring exactly as §0 requires.

**Machine context:** the build/dev box is an AMD Ryzen 5 5500U, 7 GB RAM, NO
NVIDIA GPU, 63 GB disk free. User decision (2026-09-22): the final stack runs
on a separate 16 GB VRAM CUDA machine; GPU-gated VERIFYs run there. Dev-box
constraints are recorded, never silently substituted.

---

## §1.2 Quant file listing (HF API, real output)

Command: `curl -s https://huggingface.co/api/models/bartowski/Qwen_Qwen3.5-4B-GGUF/tree/main`

```
Qwen_Qwen3.5-4B-Q8_0.gguf   4622131168   (4.62 GB)  ✓ matches spec table — DEFAULT
Qwen_Qwen3.5-4B-Q6_K_L.gguf 3959314448   (3.96 GB)  ✓ fallback
Qwen_Qwen3.5-4B-Q6_K.gguf   3805358048   (3.81 GB)  ✓ fallback
Qwen_Qwen3.5-4B-Q5_K_M.gguf 3443763168   (3.44 GB)  ✓
Qwen_Qwen3.5-4B-Q4_K_M.gguf 3013027808   (3.01 GB)  ✓ rejected per §1.2
Qwen_Qwen3.5-4B-Q8_0 sha256: 5c74c0ede371924357dff0cb6ba145bd67208b9b2389ded681adfff3f7608db7
```

## §1.3 llama-server reasoning flags — PENDING (launch-gated)

Requires the b9222 build (`llama-server --help | grep -iE "reasoning|think|
chat-template-kwargs|jinja"`). Held per user directive. Code is written
against both paths: server-side `reasoning_content` separation AND the
mandatory fallback state machine (app/llm/reasoning.py — 6 tests GREEN,
including marker-split-across-deltas and dying-stream cases).

## §1.4 mmproj (HF API tree, real output)

```
mmproj-Qwen_Qwen3.5-4B-f16.gguf   672423488   (present, 605 MB)
mmproj-Qwen_Qwen3.5-4B-bf16.gguf  675569216   (present)
```
NOT wired into v1 per §1.4 — recorded as the README future path (evidence
photos, scanned FIRs).

## §1.6 Sampling parameters (fetched from https://huggingface.co/Qwen/Qwen3.5-4B, 2026-09-22)

Verbatim card recommendations:

| Mode | temperature | top_p | top_k | min_p | presence_penalty | repetition_penalty |
|---|---|---|---|---|---|---|
| Thinking / general | 1.0 | 0.95 | 20 | 0.0 | 1.5 | 1.0 |
| Thinking / precise coding | 0.6 | 0.95 | 20 | 0.0 | 0.0 | 1.0 |
| Instruct / general | 0.7 | 0.8 | 20 | 0.0 | 1.5 | 1.0 |
| Instruct / reasoning | 1.0 | 1.0 | 40 | 0.0 | 2.0 | 1.0 |

Additional card facts (recorded): thinking is ON by default, delimited by
` Mattis\n…\n\n` before the answer; **no `/think` / `/no_think` soft switch**
(unlike Qwen3) — disabled per-request via `chat_template_kwargs:
{"enable_thinking": false}`; recommended output length 32,768; native context
262,144; 4B params; 32-layer hybrid (Gated DeltaNet + Gated Attention, 4 KV
heads × 256 head dim); multimodal; Apache-2.0.

→ `app/llm/sampling.py` uses Thinking/general as the synthesis baseline;
deterministic sub-tasks override to temperature=0, top_k=1 with thinking OFF
(§11.5). Synthesis thinking remains switchable via `KSP_THINKING_SYNTHESIS`
until the Step 13 A/B records both numbers.

## §2.5 KV size — PENDING (launch-gated)

Requires llama-server + model file. The CTX_SIZE=32768 in `.env.example` is
the declared PLACEHOLDER per §6; the authoritative `llama_context: KV self
size` reading happens at Step 9 on the target machine, then the VRAM gate
(≤13.5 GB with embed+rerank up) re-runs.

## §2.6 free -g (dev box, verbatim)

```
               total        used        free      shared  buff/cache   available
Mem:               7           3           1           0           2           3
Swap:              3           2           1
```
UNDER 16 GB → per spec, Neo4j heap/pagecache drop to 1G each here; compose
parameterizes both (`NEO4J_HEAP_MAX`, `NEO4J_PAGECACHE`, defaults 2G per §16).
Target machine RAM must be re-verified with the same command.

## §3.2 LightRAG signatures — VERIFIED (lightrag-hku 1.4.9, .venv, 2026-10-03)

```
version: v1.4.9
init: LightRAG(working_dir, kv_storage='JsonKVStorage',
      vector_storage='NanoVectorDBStorage', graph_storage='NetworkXStorage',
      doc_status_storage='JsonDocStatusStorage', workspace=<factory>,
      top_k=40, chunk_top_k=20, chunk_token_size=1200,
      chunk_overlap_token_size=100, embedding_func, llm_model_func, ...)
insert_custom_kg:   (custom_kg: dict[str, Any], full_doc_id: str = None) -> None
ainsert_custom_kg: (custom_kg: dict[str, Any], full_doc_id: str = None) -> None
query:  (query, param: QueryParam, system_prompt=None) -> str | Iterator[str]
aquery: (query, param: QueryParam, system_prompt=None) -> str | AsyncIterator[str]
initialize_storages: (self)      finalize_storages: (self)
QueryParam(mode='local|global|hybrid|naive|mix|bypass', top_k=40,
           chunk_top_k=20, ..., enable_rerank=True, include_references=False)
EmbeddingFunc(embedding_dim, func, max_token_size=None)   [lightrag.utils]
```
Storage registry (lightrag/kg/__init__.py STORAGES): `"QdrantVectorDBStorage":
".kg.qdrant_impl"` ✓ — valid vector_storage string. Qdrant connection comes
from env (kg/qdrant_impl.py:139-144): `QDRANT_URL`, `QDRANT_API_KEY`, and
`QDRANT_WORKSPACE` overrides the workspace — exactly the §9 env contract the
compose file passes. Engine wiring in app/retrieval/lightrag_engine.py needs
no changes; the insert entrypoint resolution (ainsert_custom_kg preferred)
matches the dumped surface.

## §3.3 GPU / llama.cpp tag — BLOCKED on dev box; tag VERIFIED

```
BLOCKED: Step 0/§3.3 — nvidia-smi — command: nvidia-smi --query-gpu=name,
compute_cap --format=csv — output: "/bin/bash: nvidia-smi: command not found".
Dev box has no NVIDIA GPU. CMAKE_CUDA_ARCHITECTURES (default 86) must be read
from the 16 GB VRAM target machine before its prod build.
```
Tag verification (bartowski README, fetched): *"Using llama.cpp release b9222
for quantization"* and *"Adding MTP layers now that support has been added
with release b9180"* → the pinned b9222 satisfies both the `qwen35` arch
requirement and MTP (§1.5).

## §8 Rerank support — PENDING (launch-gated)

`llama-server --help | grep -i rerank` runs on the b9222 build. Both paths
are implemented and must be tested per §8: rerank top-30→top-8 when
ENABLE_RERANK=true; top-8 by hybrid score when off/degraded — degradation
never raises mid-request and never emulates reranking with a generation prompt.

## Embedding/reranker GGUF sources (HF API, real output)

```
gpustack/bge-m3-GGUF:              bge-m3-Q8_0.gguf              634553760  (605 MB)
gpustack/bge-reranker-v2-m3-GGUF:  bge-reranker-v2-m3-Q8_0.gguf  635676416  (607 MB)
```
Used verbatim in `make fetch-models` — no invented repos.

## Local model file (dev box) — BLOCKED, user handling

```
User-provided models/Qwen3.5-4B-Q8_0.gguf was 4,482,403,488 bytes —
139,727,680 short of the published 4,622,131,168.
Resume via HTTP Range appended the missing bytes → full size 4,622,131,168.
Final sha256: 8fc33bee82e54788c8dadd85b8f94a78e5f2d5e29235ecb3bbc5bc50a7a03557
Expected:     5c74c0ede371924357dff0cb6ba145bd67208b9b2389ded681adfff3f7608db7 → MISMATCH
BLOCKED: the original download was corrupted mid-stream, not merely truncated.
Per user decision (2026-09-23) the model is ON HOLD; the user will place a
freshly downloaded file at models/Qwen_Qwen3.5-4B-Q8_0.gguf. All llama-server
gates wait for it.
```

## Docker host (real output)

```
Docker version 29.8.0, build 88096ef
Docker Compose version v5.5.1
```
`docker compose config -q` → valid (base and base+prod). Note: unrelated
container `docmind-neo4j` already binds host 7474/7687 → KSP Neo4j is
compose-internal; the dev browser port is overridable via NEO4J_BROWSER_PORT
(default 7474, e.g. 7475 locally).

## Step 1 gate (real run, §15 Step 1)

```
Step 1 — schema discovery: 68 JSON paths across 1000 records
  [PASS] n_records == 1000 (got 1000)
  [PASS] fir_id present 100% (got 100.0%)
  [PASS] id_regex derived & matches all ids: ^(?:\d{1}/\d{4}|\d{2}/\d{4}|\d{3}/\d{4})$ → 100.0%
  [PASS] narrative fields found: ['firs[].incident_details.truth_of_incident']
  [NOTE] fir_id globally unique: False (unique 700/1000; +station → 995; exact dup pairs: 5)
  [NOTE] sparse paths (<20% present): 2   [NOTE] enums: 17   [NOTE] stations: 40
GATE PASS
```
Narrative rule (data-derived): mean length ≥ 60 AND p90 ≥ 80 chars — truth_of_
incident sits at mean 115.3 / p90 145 (3× the next field) but only 280 distinct
values (sentence templates repeat), so a uniqueness criterion was rejected
after observing the data. Citations therefore key off (fir_id, chunk) with
repeated prose handled by the §12.6 retrieval-set check.

## Step 5 gate (real run, §15 Step 5)

```
  [PASS] merge rate 0.0% < 15% (merges performed: 0; strong identifiers in corpus: False)
  [NOTE] distinct person nodes: 3824; placeholder-excluded: 752
  [NOTE] SAME_NAME_AS: 286 clusters → 3488 chained edges @ confidence 0.5
GATE PASS
```

## Step 6 expected graph (hand-computed from normalized records, live-load gate at launch)

```
FIR 1000 · Person 3824 · Station 40 · Section 9 · CrimeType 5 · Vehicle 518
Phone 518 · Account 480 · Device 486 · Location 997  = 10,072 nodes
REGISTERED_AT 1000 · OCCURRED_AT 1000 · CLASSIFIED_AS 1000 · INVOKES 1783
HAS_EVIDENCE 3576 · ACCUSED_IN 248 · COMPLAINANT_IN 1000 · INVESTIGATED_BY 1000
ASSOCIATE_OF 1812 · SAME_NAME_AS 3488                    = 15,907 relationships
```

## Step 8 payload verification (deterministic build, real run)

```
entities: 13183 | relationships: 16997 | chunks: 1000
rel weights: {1.0: 9009, 0.4: 5086, 0.7: 2902}   (§9.1 rule 5 semantics)
zero chunks missing source_id; FIR entity names station-disambiguated for the
300 duplicated fir_ids
```

## Test suites (real runs, 2026-09-23)

```
test_schema_contract.py    PASS (report current; gates hold; constants consistent)
test_context_budget.py     ALL 8 GREEN (eviction order, overflow 422, reserve reclaim)
test_cypher_templates.py   ALL GREEN (12 frozen constants; scope+LIMIT everywhere;
                           params whitelisted; live EXPLAIN SKIP-loud until stack)
test_reasoning_split.py    ALL 6 GREEN (marker split across deltas; no byte leak;
                           dying stream stays reasoning)
test_citation_validator.py ALL 6 GREEN (fabricated-id suppression + strike;
                           reasoning-only fabrication NOT flagged; derived regex
                           rejects the spec's example FIR-2024-0188 format)
test_rbac_scope.py         ALL 5 GREEN (admin/analyst unscoped; scoped passthrough;
                           every plan carries the scope)
Frontend: npm run build ✓ (vite 8, 6.01s) — §14.2 changes compile clean
Backend + rag_service: python compileall clean
```

## Decisions recorded (§17 "record the decision" clause)

1. **Response envelope:** frontend had no established shape → spec default
   `{"ok": …}` adopted for NEW `/api/intel/*` endpoints; legacy shapes kept
   (change control).
2. **`apps/llm` retired** in favor of `apps/intel` (§14.3-4): removed from
   INSTALLED_APPS and URLconf; files remain on disk until the cleanup commit.
3. **`fir` app stays on Postgres** for legacy CRUD; the evidentiary Neo4j graph
   serves the intel/RAG paths. FIR-CRUD-via-bolt is additive follow-up work
   outside §14.3's enumerated changes.
4. **§14.2 plumbing interpretations** (recorded, minimal): Login.jsx now calls
   the real login API (change 1 needs a Bearer token to function at all);
   App.jsx passes an `onOpenFir` callback (change 3's deep-link target);
   vite.config.js gains the dev proxy (build config outside `frontend/src/`,
   §0.8 scope). No other frontend files were touched beyond the 8 enumerated
   changes + their plumbing.
5. **Entity-resolution artifact location:** §5.6 says "report the merge rate in
   schema_report.json" — but the schema report is a deterministic discovery
   artifact gated byte-for-byte by test_schema_contract. The merge-rate
   therefore lives in `artifacts/entity_resolution.json` and is cross-linked
   from the report's id_uniqueness note.

## Still pending (launch-gated, per user's code-first order)

| VERIFY / gate | Where it runs |
|---|---|
| §1.3 llama-server reasoning flags | b9222 build on target |
| §2.5 KV self-size → CTX_SIZE replacement | llama-server + verified model |
| §3.2 LightRAG signature dump | rag venv/container at install |
| §8 rerank flag + endpoint | b9222 --help |
| Step 4 `SHOW CONSTRAINTS` (10) | stack launch |
| Step 6 live load counts vs expected | stack launch |
| Step 8 <10 min ingest, INDEXING never violated | stack launch |
| Step 9 /health on 8080/8081, embed dim 1024, VRAM recorded | target machine |
| Step 12 live EXPLAIN | Neo4j up |
| Step 13 intent benchmark ≥18/20 + thinking A/B numbers | llama stack up |
| Step 14 curl -N streams both channels | stack up |
| Step 16 perf gate (VRAM/RAM/TTFT) | warm stack on target |
| Step 17 login→query→stream (test_e2e_query.py) | full stack |
| Model file redownload + sha match | user (on hold) |
