# KSP Investigative Intelligence System — Master Build Prompt v3.1

Target agent: **OpenCode GLM 5.2**. Single source of truth for the build.
Supersedes `graph-rag-llm-build-prompt-v2.md` and `v3`.

Read this entire document before writing code. Do not begin Step 1 until
Step 0 is complete.

---

## 0. Agent operating contract (non-negotiable)

1.  **No stubs.** Every file is complete and runnable. No `# TODO`, no
    `pass  # later`, no `...`, no "rest of file unchanged".
2.  **No invented APIs.** You may only import symbols that exist in the
    pinned versions in §3. Where this document says
    **`VERIFY:`**, you must run the stated command and write the real
    output to `artifacts/verification.md` *before* writing code that
    depends on it. If verification fails, emit `BLOCKED:` and stop that
    branch. Never substitute a plausible alternative silently.
3.  **No invented data fields.** The FIR JSON schema is discovered in
    Step 1. Any code reading a field absent from
    `artifacts/schema_report.json` is a defect.
4.  **Fail loud.** No `except Exception: pass`. No mock-data fallback.
    Dependency failures raise typed errors that surface as a 503 with a
    machine-readable code.
5.  **File notation** on everything you touch:
    -   `■` new file you create
    -   `▲` existing file you modify (state the rationale before editing)
    -   `□` existing file, read-only — do not modify
6.  **DAG order.** Follow §15. Do not start a step whose dependencies
    have not passed their gate.
7.  **Gate per step.** Each step ends with a runnable command and an
    expected observable. Run it. Paste real output. Fix before advancing.
8.  **Frontend is change-controlled, not frozen.** See §14. You may only
    make the enumerated changes. Everything else under `frontend/src/`
    is `□`.
9.  **Zero-hallucination at runtime.** Every answer carries citations
    mechanically validated against the retrieval set (§12.6). Uncited or
    fabricated references are suppressed, not shipped.
10. **On-premises only.** No runtime call to an external host. No cloud
    inference, no telemetry. Weights are fetched once at build time into
    a mounted volume.

---

## 1. Model: corrected facts

### 1.1 What the model actually is

**`Qwen/Qwen3.5-4B`**, quantized at
`bartowski/Qwen_Qwen3.5-4B-GGUF`.

Confirmed from the model card:

-   4B parameters, GGUF architecture identifier **`qwen35`**.
-   Base model `Qwen/Qwen3.5-4B-Base`; the finetuned chat model is
    `Qwen/Qwen3.5-4B`. Use the finetuned one.
-   Apache-2.0.
-   Quantized with llama.cpp release **b9222**. Your llama.cpp build must
    be **b9222 or newer** or it will not recognize the `qwen35`
    architecture and will fail at load with an unknown-arch error. This
    is the single most likely first-hour failure — pin the build.
-   The model is tagged **image-text-to-text**. It is multimodal, not
    text-only. See §1.4.
-   It is a **thinking model**. See §1.3.

### 1.2 Quantization — Q8_0

Real file sizes from the card:

| Quant     | Size    | Verdict                                        |
| --------- | ------- | ---------------------------------------------- |
| `Q8_0`    | 4.62 GB | **Default.** 16 GB VRAM makes this free.       |
| `Q6_K_L`  | 3.96 GB | Fallback if VRAM gate in §16 fails             |
| `Q6_K`    | 3.81 GB | Fallback                                       |
| `Q5_K_M`  | 3.44 GB | Do not use unless both above fail              |
| `Q4_K_M`  | 3.01 GB | **Rejected.** Destabilizes a 4B on a citation- |
|           |         | grounded extraction workload.                  |

The v3 recommendation of Q4_K_M was made under a CPU-only, 16 GB
system-RAM assumption. With 16 GB VRAM that trade-off is gone. **Q8_0.**

Download command:

```bash
huggingface-cli download bartowski/Qwen_Qwen3.5-4B-GGUF \
  --include "Qwen_Qwen3.5-4B-Q8_0.gguf" \
  --local-dir ./models
```

### 1.3 Thinking mode — this changes the whole answer path

The published prompt format is:

```
<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{prompt}<|im_end|>
<|im_start|>assistant
<think>
```

The assistant turn **opens with `<think>`**. This model reasons before
answering. Three consequences you must handle, and which v3 got wrong by
assuming a non-thinking model:

1.  **Reasoning tokens consume the generation budget.** A 1,024-token
    reserve that assumed pure answer text will now be mostly reasoning.
    The §11 budget reserves separately for reasoning and answer.
2.  **Reasoning must never reach the user as answer text.** An
    investigator reading the model's internal deliberation as if it were
    a finding is a serious failure mode for this tool. Reasoning is
    routed to a separate, collapsed UI panel (§14) and is **excluded from
    citation validation and from the audit log's answer field**.
3.  **Reasoning must be disabled for the deterministic sub-tasks** —
    intent classification and slot extraction. Those run at temperature 0
    and need a bare label, not 400 tokens of deliberation.

**`VERIFY:`** before writing any LLM client code:

```bash
llama-server --help | grep -iE "reasoning|think|chat-template-kwargs|jinja"
```

Record in `artifacts/verification.md` the exact flags available. Recent
llama.cpp exposes `--reasoning-format` (which separates reasoning into a
`reasoning_content` field on the response rather than inlining it) and
`--reasoning-budget` (where `0` disables thinking). **Do not assume these
names.** Write the client against what `--help` actually prints.

If neither flag exists in your build, the fallback is a streaming state
machine in `llm/client.py` that tracks whether the cursor is inside a
`<think>` block and emits tokens on the `reasoning` SSE channel vs the
`token` channel accordingly. Implement the fallback regardless — it costs
30 lines and protects you if the server is swapped.

Step 13 includes an A/B gate: run the 20-question intent benchmark with
thinking disabled and with a small thinking budget, and keep whichever
scores higher at acceptable latency. Record both numbers. Do not guess.

### 1.4 Multimodality — deliberately out of scope for v1

The model accepts images. In llama.cpp that requires a separate `mmproj`
projector file. The bartowski repo lists an additional variant beyond the
text quants, which may be the mmproj.

**`VERIFY:`**

```bash
huggingface-cli download bartowski/Qwen_Qwen3.5-4B-GGUF \
  --include "*mmproj*" --local-dir ./models || echo "NO_MMPROJ"
```

If present, record the filename. **Do not wire vision into v1.** Note it
in the README as a future path for evidence-photo and scanned-FIR
analysis — that is a strong finale talking point that costs you nothing
to mention and would cost you two days to build badly.

### 1.5 MTP speculative decoding — optional speedup

The card notes MTP layers are included and are used via:

```
--spec-type draft-mtp
```

requiring llama.cpp **b9180 or newer**. This is self-speculative decoding
and can materially raise tokens/sec. It also costs additional VRAM
(roughly 2 GB in reported cases).

Treat it as an **optional, benchmarked** flag: `ENABLE_MTP=false` in
`.env.example`. Step 16 measures with and without, and you keep it only
if it improves p50 time-to-first-token **and** the VRAM gate still
passes. Never enable it untested on demo day.

### 1.6 Sampling parameters

I do not have verified recommended sampling defaults for Qwen3.5-4B.

**`VERIFY:`** read `https://huggingface.co/Qwen/Qwen3.5-4B` and record
the recommended `temperature`, `top_p`, `top_k`, `min_p`, and any
`presence_penalty` guidance in `artifacts/verification.md`. Use those as
the baseline for the synthesis task. The deterministic sub-tasks
(classification, extraction) override to `temperature=0, top_k=1`
regardless of what the card recommends.

Do not copy sampling numbers from Qwen3 or Qwen2.5 guidance. Thinking
models are sensitive to this and wrong values produce degenerate loops.

---

## 2. Architecture

### 2.1 Topology

```
                          ┌──────────────────────────────┐
                          │  React (Vite, JS/JSX)        │  ▲ change-
                          │  :5173 dev / :80 nginx prod  │    controlled
                          └──────────────┬───────────────┘
                                         │ HTTPS, JWT Bearer
                                         ▼
                          ┌──────────────────────────────┐
                          │  Django 4.2.13 (pure, no DRF)│  :8000
                          │  auth · RBAC · FIR CRUD      │
                          │  audit · SSE proxy           │
                          └──────┬────────────────┬──────┘
                                 │                │
              Cypher (bolt)      │                │  HTTP + SSE
                                 ▼                ▼
        ┌────────────────────────────┐   ┌────────────────────────────┐
        │  Neo4j 5.x Community       │   │  FastAPI RAG service :9000 │
        │  :7687 bolt / :7474 http   │◄──┤  LightRAG · NetworkX       │
        │  DOMAIN CRIME GRAPH ONLY   │   │  intent router · templates │
        └────────────────────────────┘   └───┬──────────────┬─────────┘
                                             │              │
                                   ┌─────────▼───┐   ┌──────▼──────────┐
                                   │ Qdrant :6333│   │ llama.cpp (CUDA)│
                                   │ vectors     │   │ :8080 LLM       │
                                   └─────────────┘   │ :8081 embed     │
                                                     │ :8082 rerank    │
                                                     └─────────────────┘
```

**Hard rule:** Django never talks to Qdrant, never talks to llama.cpp,
and never builds a prompt. Its only AI-adjacent job is authenticate,
authorize, stamp the audit log, attach RBAC scope, proxy the stream.

### 2.2 LightRAG replaces the custom Graph-RAG layer

LightRAG (`lightrag-hku`, HKUDS) is the retrieval framework. There is one
trap that will destroy this project if you follow its quickstart:

**LightRAG's default `insert()` runs LLM-driven entity and relationship
extraction on every chunk, with gleaning passes.** For ~1,000 FIRs that
is hours of GPU time *and* it injects model hallucination directly into
the knowledge graph — the exact failure this tool exists to prevent.

**Binding decision: build the KG deterministically from the structured
JSON and inject it via `insert_custom_kg()`. Zero LLM calls at index
time.** The dataset already contains explicit `criminal_network`,
`digital_evidence`, `physical_evidence` and `occurrence_location` blocks.
These are ground truth. Extracting them with a language model would be
strictly worse than reading them.

**`VERIFY:`** the real signature before use (see §3.2). The shape as of
recent releases:

```python
custom_kg = {
    "chunks":       [{"content": "...", "source_id": "FIR-2024-001"}],
    "entities":     [{"entity_name": "...", "entity_type": "Person",
                      "description": "...", "source_id": "FIR-2024-001"}],
    "relationships":[{"src_id": "...", "tgt_id": "...",
                      "description": "...", "keywords": "accused, named",
                      "weight": 1.0, "source_id": "FIR-2024-001"}],
}
rag.insert_custom_kg(custom_kg)
```

Newer versions may require a `file_path` per entity and may expose
`ainsert_custom_kg`. Write against the printed signature, not this
snippet.

### 2.3 Storage split — and why

| Store                | Holds                                    |
| -------------------- | ---------------------------------------- |
| Neo4j                | Domain crime graph **only**. Evidentiary. |
| LightRAG graph store | `NetworkXStorage` — in-process, file-backed |
| Qdrant               | LightRAG entity/relation/chunk vectors   |

Pointing LightRAG at Neo4j creates a label-namespace collision inside a
single Neo4j Community database (CE supports one user database). At this
data scale NetworkX is fast and has zero collision surface. **Neo4j's
native vector index is not used — drop it from the design.**

If a judge asks why the graph is split: the domain graph is *evidentiary*
and must be provably derived from FIR records; the LightRAG KG is a
*retrieval* index and is allowed to be lossy. Different guarantees,
different stores.

### 2.4 Port map

| Port | Service                   | Host-exposed  |
| ---- | ------------------------- | ------------- |
| 5173 | Vite dev server           | dev only      |
| 8000 | Django                    | yes           |
| 9000 | FastAPI RAG               | no            |
| 8080 | llama-server (generation) | no            |
| 8081 | llama-server (embeddings) | no            |
| 8082 | llama-server (rerank)     | no            |
| 7687 | Neo4j bolt                | no            |
| 7474 | Neo4j browser             | dev only      |
| 6333 | Qdrant HTTP               | no            |

### 2.5 VRAM budget — 16 GB

VRAM and system RAM are separate budgets. Only the three llama.cpp
services consume VRAM; Neo4j, Qdrant, Django and FastAPI consume system
RAM.

| VRAM consumer                          | Est.    |
| -------------------------------------- | ------- |
| Qwen3.5-4B Q8_0 weights                | 4.62 GB |
| KV cache @ 32,768 ctx, q8_0 K/V        | **measured in Step 9** |
| CUDA context + compute buffers         | ~1.0 GB |
| bge-m3 Q8_0 embedding server           | ~0.8 GB |
| bge-reranker-v2-m3 Q8_0 (optional)     | ~0.8 GB |
| MTP draft overhead (optional)          | ~2.0 GB |

**I cannot give you the KV-cache figure, because I do not have verified
layer/head counts for `qwen35`, and guessing them would be exactly the
kind of fabrication this document forbids.** Compute it from the GGUF
instead:

```
bytes_per_token(f16) = 2 (K and V) × n_layer × n_head_kv × head_dim × 2
```

**`VERIFY:`** launch the server once and read the real numbers it prints:

```bash
llama-server -m models/Qwen_Qwen3.5-4B-Q8_0.gguf -ngl 99 -c 4096 2>&1 \
  | grep -iE "n_layer|n_head_kv|n_embd_head|KV self size|freq_base"
```

`llama_context: KV self size = ...` is the authoritative number. Record
it at 4,096 and scale linearly to pick the production `--ctx-size`.
Target total VRAM ≤ **13.5 GB** so the display server and CUDA
fragmentation have room.

### 2.6 System RAM budget

| Component                      | Budget  |
| ------------------------------ | ------- |
| OS + Docker daemon             | 1.5 GB  |
| Neo4j (heap 2G, pagecache 2G)  | 4.5 GB  |
| Qdrant                         | 1.5 GB  |
| FastAPI + LightRAG + NetworkX  | 2.0 GB  |
| Django + Postgres              | 1.0 GB  |
| **Total**                      | **10.5 GB** |

**`VERIFY:`** `free -g` and record total system RAM in
`artifacts/verification.md`. If under 16 GB, drop Neo4j heap and
pagecache to 1G each and note it.

---

## 3. Pinned dependencies

### 3.1 `backend/requirements.txt` ■

```text
Django==4.2.13
PyJWT==2.8.0
neo4j==5.28.1
httpx==0.27.2
python-dotenv==1.0.1
psycopg2-binary==2.9.9
gunicorn==22.0.0
```

### 3.2 `rag_service/requirements.txt` ■

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
lightrag-hku==1.4.9
qdrant-client==1.12.1
neo4j==5.28.1
networkx==3.4.2
httpx==0.27.2
numpy==2.1.3
pydantic==2.10.4
pydantic-settings==2.7.0
python-dotenv==1.0.1
tenacity==9.0.0
```

**`VERIFY:`** `lightrag-hku` moves fast. After install:

```bash
python - <<'PY'
import inspect, lightrag
from lightrag import LightRAG, QueryParam
print("version:", getattr(lightrag, "__version__", "n/a"))
print("init   :", inspect.signature(LightRAG.__init__))
for name in ("insert_custom_kg", "ainsert_custom_kg",
             "query", "aquery", "initialize_storages"):
    fn = getattr(LightRAG, name, None)
    print(name, ":", inspect.signature(fn) if fn else "ABSENT")
print("QueryParam:", inspect.signature(QueryParam.__init__))
PY
```

Write the code against the **printed** signatures. If both
`insert_custom_kg` and `ainsert_custom_kg` are absent, emit `BLOCKED:` —
do not fall back to `insert()`.

If the pinned version cannot be resolved, try the nearest newer patch and
record the deviation. Do not silently float the pin.

### 3.3 llama.cpp build

Build from source, pinned to a release **≥ b9222**:

```dockerfile
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS build
ARG LLAMA_TAG=b9222
RUN apt-get update && apt-get install -y git cmake build-essential libcurl4-openssl-dev
RUN git clone --depth 1 --branch ${LLAMA_TAG} https://github.com/ggml-org/llama.cpp /src
WORKDIR /src
RUN cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=ON \
      -DCMAKE_CUDA_ARCHITECTURES=86 \
 && cmake --build build -j --target llama-server llama-cli
```

**`VERIFY:`** set `CMAKE_CUDA_ARCHITECTURES` to your actual GPU's compute
capability — run `nvidia-smi --query-gpu=name,compute_cap --format=csv`
and record it. `86` is Ampere (RTX 30-series / A-series). A wrong value
compiles but falls back to slow paths.

---

## 4. Repository layout

```
ksp-iis/
├── docker-compose.yml                          ■
├── docker-compose.prod.yml                     ■
├── .env.example                                ■
├── Makefile                                    ■
├── data/
│   └── bengaluru_40ps_1000_firs.json           □ SOURCE OF TRUTH
├── models/                                     (volume, gitignored)
│   ├── Qwen_Qwen3.5-4B-Q8_0.gguf
│   ├── bge-m3-Q8_0.gguf
│   └── bge-reranker-v2-m3-Q8_0.gguf
├── artifacts/                                  (generated, committed)
│   ├── verification.md                         ■ all VERIFY: outputs
│   ├── schema_report.json                      ■ Step 1
│   ├── frontend_inventory.md                   ■ Step 2
│   ├── backend_inventory.md                    ■ Step 2
│   └── perf_report.json                        ■ Step 16
├── frontend/                                   ▲ change-controlled, §14
├── backend/                                    (Django)
│   ├── Dockerfile                              ■
│   ├── requirements.txt                        ■
│   ├── manage.py                               ■/□ per Step 2
│   ├── config/{settings,urls,wsgi}.py          ■/▲
│   ├── common/{responses,errors,pagination}.py ■
│   ├── accounts/
│   │   ├── models.py  jwt_utils.py             ■/▲
│   │   ├── decorators.py  scope.py             ■/▲
│   │   └── views.py  urls.py                   ■/▲
│   ├── fir/
│   │   ├── models.py  neo4j_client.py          ■/▲
│   │   ├── queries.py  views.py  urls.py       ■/▲
│   ├── audit/{models,middleware,views}.py      ■/▲
│   └── intel/{proxy,views,urls}.py             ■/▲
├── rag_service/                                (FastAPI, all ■)
│   ├── Dockerfile  requirements.txt
│   ├── app/
│   │   ├── main.py  config.py  deps.py  schemas.py
│   │   ├── llm/{client,tokens,prompts,sampling,reasoning}.py
│   │   ├── retrieval/{lightrag_engine,embeddings,rerank,context_budget}.py
│   │   ├── graph/{neo4j_client,cypher_templates,centrality,serializers}.py
│   │   ├── router/{intent,plan}.py
│   │   ├── answer/{synthesize,citations}.py
│   │   └── routes/{health,query,graph,profile}.py
│   └── ingest/
│       ├── discover_schema.py  normalize.py
│       ├── load_neo4j.py  build_custom_kg.py  run_ingest.py
├── infra/
│   ├── llamacpp/{Dockerfile,run-generation.sh,run-embeddings.sh,run-rerank.sh}
│   ├── neo4j/constraints.cypher
│   └── nginx/default.conf
└── tests/
    ├── test_schema_contract.py      test_cypher_templates.py
    ├── test_context_budget.py       test_citation_validator.py
    ├── test_reasoning_split.py      test_rbac_scope.py
    └── test_e2e_query.py
```

`■/▲` means: Step 2 inventories what already exists; files that exist
become `▲` and are extended, files that do not become `■`.

---

## 5. Data contract

### 5.1 Confirmed facts

-   Root key `"firs"`, an array.
-   Record identifier is **`fir_id`**, not `fir_no`. Any code referencing
    `fir_no` is a defect.
-   1,000 records, 40 Bengaluru police stations.
-   Nested blocks present: `criminal_network`, `digital_evidence`,
    `physical_evidence`, `ai_metadata`, `occurrence_location`.
-   **The records carry proper citation structure.** Step 1 must locate
    it precisely — see §5.3.

### 5.2 Step 1 — schema discovery before schema use

`ingest/discover_schema.py` ■ walks all 1,000 records and emits
`artifacts/schema_report.json` with, for every JSON path:

```json
{
  "path": "firs[].criminal_network.associates[].name",
  "type": "string",
  "present_count": 842,
  "present_pct": 84.2,
  "null_count": 12,
  "cardinality": 631,
  "examples": ["...", "...", "..."],
  "is_array": true,
  "max_array_len": 7
}
```

Rules:

-   Downstream modules import field names from a single generated module
    `ingest/_schema_constants.py`, produced *from* the report. No field
    name appears as a string literal anywhere else.
-   `tests/test_schema_contract.py` ■ re-runs discovery and asserts the
    report is unchanged, so a dataset swap fails loudly rather than the
    loader silently dropping fields.
-   Fields present in under 20% of records are marked `sparse` and
    treated as genuinely optional — never defaulted to empty strings,
    which creates phantom nodes.

### 5.3 Step 1b — the citation contract

Because the JSON carries proper citations, the whole zero-hallucination
gate keys off it. Step 1 must additionally emit
`artifacts/schema_report.json → citation_contract`:

```json
{
  "id_field": "fir_id",
  "id_regex": "^FIR-\\d{4}-\\d{4}$",
  "id_examples": ["FIR-2024-0188"],
  "narrative_fields": ["firs[].narrative", "firs[].summary"],
  "citable_leaf_paths": ["firs[].occurrence_location.locality", "..."],
  "per_field_provenance": true
}
```

-   `id_regex` is **derived from the observed IDs**, not assumed. It is
    the regex the citation validator (§12.6) compiles. If IDs turn out to
    have more than one format, the regex is a union and the report says
    so.
-   `narrative_fields` lists the free-text fields that get chunked.
    **If the report finds none**, the chunking strategy in §9 changes:
    chunks become rendered records (deterministic templated prose built
    from structured fields), and citations key off `(fir_id, field_path)`
    instead of `(fir_id, chunk_id)`. Implement whichever the report
    dictates. Do not assume prose exists.

### 5.4 Provisional Neo4j domain graph model

This is a **proposal to reconcile against `schema_report.json` in Step
6**, not a spec to implement blindly. Where the report contradicts it,
the report wins and you record the delta under `model_deltas`.

| Label       | Key property   |
| ----------- | -------------- |
| `FIR`       | `fir_id`       |
| `Person`    | `person_key`   |
| `Station`   | `station_code` |
| `Section`   | `section_code` |
| `Vehicle`   | `registration` |
| `Phone`     | `msisdn`       |
| `Account`   | `account_ref`  |
| `Device`    | `imei`         |
| `Location`  | `location_key` |
| `CrimeType` | `crime_code`   |

```
(:Person)-[:ACCUSED_IN     {role, source_fir}]->(:FIR)
(:Person)-[:VICTIM_IN      {source_fir}]->(:FIR)
(:Person)-[:COMPLAINANT_IN {source_fir}]->(:FIR)
(:Person)-[:WITNESS_IN     {source_fir}]->(:FIR)
(:Person)-[:ASSOCIATE_OF   {strength, basis, source_fir}]->(:Person)
(:Person)-[:SAME_NAME_AS   {confidence}]->(:Person)
(:FIR)-[:REGISTERED_AT     {source_fir}]->(:Station)
(:FIR)-[:OCCURRED_AT       {source_fir}]->(:Location)
(:FIR)-[:CLASSIFIED_AS     {source_fir}]->(:CrimeType)
(:FIR)-[:INVOKES           {source_fir}]->(:Section)
(:FIR)-[:HAS_EVIDENCE      {kind, source_fir}]->(:Vehicle|:Phone|:Account|:Device)
(:Phone)-[:CONTACTED       {count, window, source_fir}]->(:Phone)
(:Person)-[:USES           {source_fir}]->(:Phone|:Vehicle|:Account|:Device)
```

**Every relationship carries `source_fir`.** This is what makes the graph
evidentiary: any edge on screen traces to the FIR that created it, and
the UI answers "why is this edge here?" without invoking an LLM.

### 5.5 Constraints — `infra/neo4j/constraints.cypher` ■

```cypher
CREATE CONSTRAINT fir_id_unique IF NOT EXISTS
  FOR (f:FIR) REQUIRE f.fir_id IS UNIQUE;
CREATE CONSTRAINT person_key_unique IF NOT EXISTS
  FOR (p:Person) REQUIRE p.person_key IS UNIQUE;
CREATE CONSTRAINT station_code_unique IF NOT EXISTS
  FOR (s:Station) REQUIRE s.station_code IS UNIQUE;
CREATE CONSTRAINT phone_unique IF NOT EXISTS
  FOR (p:Phone) REQUIRE p.msisdn IS UNIQUE;
CREATE CONSTRAINT vehicle_unique IF NOT EXISTS
  FOR (v:Vehicle) REQUIRE v.registration IS UNIQUE;
CREATE CONSTRAINT account_unique IF NOT EXISTS
  FOR (a:Account) REQUIRE a.account_ref IS UNIQUE;
CREATE CONSTRAINT device_unique IF NOT EXISTS
  FOR (d:Device) REQUIRE d.imei IS UNIQUE;
CREATE CONSTRAINT location_unique IF NOT EXISTS
  FOR (l:Location) REQUIRE l.location_key IS UNIQUE;
CREATE CONSTRAINT crimetype_unique IF NOT EXISTS
  FOR (c:CrimeType) REQUIRE c.crime_code IS UNIQUE;
CREATE CONSTRAINT section_unique IF NOT EXISTS
  FOR (s:Section) REQUIRE s.section_code IS UNIQUE;

CREATE INDEX fir_date     IF NOT EXISTS FOR (f:FIR) ON (f.occurred_on);
CREATE INDEX fir_district IF NOT EXISTS FOR (f:FIR) ON (f.district);
CREATE INDEX person_name  IF NOT EXISTS FOR (p:Person) ON (p.name_normalized);
CREATE FULLTEXT INDEX fir_text IF NOT EXISTS
  FOR (f:FIR) ON EACH [f.narrative, f.summary];
```

Adjust the fulltext index to the real narrative fields from §5.3.

### 5.6 Entity resolution — the highest-risk decision

Do not fuzzy-match names across the dataset. It merges unrelated people
and manufactures a fake criminal network, which is a catastrophic failure
mode for a law-enforcement tool.

**Binding rule:** two `Person` records merge only on a strong identifier
— a government ID, a phone number, or exact normalized name **plus**
exact date of birth. Name-only similarity produces a `SAME_NAME_AS`
relationship with a `confidence` score, never a merge. The UI renders
these as dashed edges labeled "possible identity match — not confirmed".

Report the merge rate in `schema_report.json`. **If over 15% of persons
merge, stop and report** — the rule is too loose for this dataset.

---

## 6. llama.cpp — generation server

`infra/llamacpp/run-generation.sh` ■

```bash
#!/usr/bin/env bash
set -euo pipefail

# Qwen3.5-4B Q8_0, full GPU offload, 16 GB VRAM.
#
# --ctx-size is a PLACEHOLDER until Step 9 measures real KV size.
# Procedure: launch at -c 4096, read "KV self size" from the log, scale
# linearly, pick the largest power-of-two total that keeps measured VRAM
# (nvidia-smi) under 13.5 GB with the embedding and rerank servers up.
# Then replace CTX_SIZE below and re-run the gate.

CTX_SIZE="${CTX_SIZE:-32768}"
PARALLEL="${PARALLEL:-2}"

ARGS=(
  --model /models/Qwen_Qwen3.5-4B-Q8_0.gguf
  --alias qwen35-4b
  --host 0.0.0.0 --port 8080

  # ---- offload ----
  --n-gpu-layers 99          # all layers on GPU; 4B Q8_0 is 4.62 GB
  --ctx-size "${CTX_SIZE}"
  --parallel "${PARALLEL}"   # ctx is DIVIDED across slots: 32768/2 = 16384/req
  --cont-batching

  # ---- memory ----
  --flash-attn on            # MANDATORY: without it, KV quant is a silent no-op
  --cache-type-k q8_0
  --cache-type-v q8_0        # keep K and V IDENTICAL; mixed k/v fails on load
  --batch-size 2048          # prefill throughput; GPU can afford this
  --ubatch-size 512

  # ---- chat ----
  --jinja                    # use the GGUF's embedded qwen35 template

  # ---- ops ----
  --slots
  --metrics
  --timeout 600
)

# Optional self-speculative decoding (see §1.5). Benchmarked, not assumed.
if [[ "${ENABLE_MTP:-false}" == "true" ]]; then
  ARGS+=( --spec-type draft-mtp )
fi

# Reasoning control. Flag names MUST be confirmed via --help first (§1.3).
if [[ -n "${REASONING_FORMAT:-}" ]]; then
  ARGS+=( --reasoning-format "${REASONING_FORMAT}" )
fi

exec llama-server "${ARGS[@]}"
```

Rationale for the non-obvious flags — do not "simplify" these away:

-   `--flash-attn on` is a **prerequisite** for KV quantization to take
    effect. Without it `--cache-type-k/v` is silently ignored and you get
    f16 KV at double the VRAM. Modern syntax is `-fa on|off|auto`; the
    bare `--flash-attn` form is deprecated. Confirm via `--help`.
-   `--cache-type-k q8_0 --cache-type-v q8_0` must be **symmetric**.
    Mixed configurations such as `k=q8_0, v=q4_0` are known to fail at
    load on several builds with a quantized-V-cache error.
-   `--parallel 2` divides the context across slots. Total 32,768 yields
    16,384 per concurrent request. Two slots lets one investigator's
    answer stream while another's prefill runs. Do not raise past 2
    without re-running the VRAM gate — KV scales linearly with slots.
-   `--batch-size 2048 --ubatch-size 512` — on GPU, prefill is compute
    bound and larger batches dominate. These are GPU numbers; the CPU
    values from v3 (512/256) would waste the card.
-   `--jinja` uses the embedded chat template. **Do not hand-write a
    `qwen35` chat template.** Getting the special tokens or the `<think>`
    opener wrong degrades output in ways that look like model weakness
    and will cost you a day of misdirected debugging.
-   `--slots --metrics` expose `/slots` and `/metrics` for Step 16.
-   `--mlock` / `--no-mmap` are **dropped** from v3 — irrelevant with
    full GPU offload, and `--mlock` needs a memlock ulimit you no longer
    need to configure.

## 7. llama.cpp — embedding server

`infra/llamacpp/run-embeddings.sh` ■

```bash
#!/usr/bin/env bash
set -euo pipefail

# bge-m3 as GGUF, served by llama.cpp rather than sentence-transformers.
# Rationale: sentence-transformers + torch costs ~2.2 GB for the same
# model and drags a second runtime into the image. A small llama-server
# reuses the CUDA context that is already resident.
#
# bge-m3 uses CLS pooling. Embedding models run non-causal attention, so
# n_ubatch must be >= the longest sequence in a batch -- hence ubatch
# equals ctx here, and chunk size is capped at ~1,000 tokens in §10.

exec llama-server \
  --model /models/bge-m3-Q8_0.gguf \
  --alias bge-m3 \
  --host 0.0.0.0 --port 8081 \
  --embedding \
  --pooling cls \
  --n-gpu-layers 99 \
  --ctx-size 2048 \
  --batch-size 2048 \
  --ubatch-size 2048
```

Output dimension is **1024**. Hard-code it as a constant and assert it on
the first embedding call. A silent dimension mismatch against the Qdrant
collection is the most common failure in this stack and presents as
"retrieval returns nothing" rather than as an error.

## 8. llama.cpp — reranker

`infra/llamacpp/run-rerank.sh` ■. With 16 GB VRAM this is affordable, so
default `ENABLE_RERANK=true`.

**`VERIFY:`** `llama-server --help | grep -i rerank` and record the exact
flag and endpoint path. If the build has no rerank support, set the flag
permanently false and record the limitation in §18 — **do not emulate
reranking with a generation prompt**, which is slow and unreliable.

Behavior when on: rerank top-30 to top-8 before context assembly. When
off: take top-8 by hybrid score. Both paths must be tested.

---

## 9. LightRAG configuration

`rag_service/app/retrieval/lightrag_engine.py` ■

```bash
LIGHTRAG_WORKING_DIR=/data/lightrag
LIGHTRAG_KV_STORAGE=JsonKVStorage
LIGHTRAG_VECTOR_STORAGE=QdrantVectorDBStorage
LIGHTRAG_GRAPH_STORAGE=NetworkXStorage
LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage
QDRANT_URL=http://qdrant:6333
QDRANT_WORKSPACE=ksp_iis
```

-   `llm_model_func` — a custom async callable hitting
    `http://llm:8080/v1/chat/completions`, used only on the query path.
    Add a module-level `INDEXING_IN_PROGRESS` flag that makes it **raise**
    if called during indexing. This is how you prove the zero-LLM-indexing
    guarantee actually holds rather than merely intending it.
-   `embedding_func` wraps `:8081`. `embedding_dim=1024`,
    `max_token_size=1024`.
-   `chunk_token_size=1000`, `chunk_overlap_token_size=120`, chosen so a
    chunk always fits the embedding server's 2048 ubatch with headroom.
-   Instantiate **once** in the FastAPI `lifespan`, store on `app.state`.
    Constructing `LightRAG` per request opens storage handles and will
    leak file descriptors until the service dies.
-   If the installed version requires `await rag.initialize_storages()`
    and a pipeline-status init, call them. Confirm from §3.2's dump.

Query modes:

| Mode     | Use for                                                |
| -------- | ------------------------------------------------------ |
| `local`  | Questions about one named entity (a person, a vehicle) |
| `global` | Thematic / pattern questions across the corpus         |
| `hybrid` | Default for free-text investigative questions          |
| `mix`    | When graph context AND raw chunk text both matter      |
| `naive`  | Fallback when the KG has no coverage; pure vector       |

The intent router picks the mode. Never expose it to the end user.

### 9.1 Deterministic KG construction

`ingest/build_custom_kg.py` ■:

1.  Entity names normalized, uppercase, whitespace-collapsed, and
    idempotent: `normalize(normalize(x)) == normalize(x)`.
2.  Every entity gets `source_id` = the `fir_id` it came from. Entities
    in multiple FIRs get one entry per source; let LightRAG merge.
3.  `description` strings are **template-generated from real fields**,
    never LLM-written:
    `f"{name}, {age}, {role} in {fir_id} ({crime_type}) registered at {station} on {date}."`
    This keeps descriptions factual and makes the embedding meaningful.
4.  Relationship `keywords` come from a fixed controlled vocabulary per
    relationship type. No free text.
5.  `weight` encodes **evidential strength**, not similarity:
    -   `1.0` explicit in the FIR (named accused, seized vehicle)
    -   `0.7` co-occurrence within one `criminal_network` block
    -   `0.4` shared identifier across FIRs (same phone, same vehicle)
    -   Never below `0.4`. If you cannot justify an edge at 0.4, omit it.
6.  `chunks` carry narrative text per §5.3 — real prose if it exists,
    otherwise deterministically rendered records — chunked at 1,000
    tokens with 120 overlap, each tagged with `fir_id` as `source_id`.
    This is what makes citation-by-`fir_id` mechanically possible.
7.  Batch at 200 FIRs per `insert_custom_kg` call with progress logging.
    A single 1,000-FIR call produces an opaque failure if anything is
    malformed.

**Gate:** after ingest, assert entities > 0, `INDEXING_IN_PROGRESS` was
never violated, and wall-clock ingest is **under 10 minutes**. If it runs
for hours you are on the LLM extraction path — stop and fix.

---

## 10. Retrieval pipeline

### 10.1 Two sources, joined

-   **Structured** — a parameterized Cypher template against Neo4j,
    chosen by intent. Returns exact rows. This is the *authoritative*
    source for every number.
-   **Narrative** — a LightRAG query returning entity/relation context
    plus source chunks. This is the *explanatory* material.

Numbers come from Cypher. Narrative comes from LightRAG. The system
prompt explicitly forbids the model from computing or estimating a
count — if a count is needed and Cypher did not supply one, it says so.

### 10.2 Embedding contract

`POST http://embed:8081/v1/embeddings` with
`{"input": [...], "model": "bge-m3"}`. Batch up to 16 texts per call.
Assert `len(vec) == 1024` on every response. Retry with `tenacity`:
3 attempts, exponential backoff, `retry_if_exception_type(httpx.HTTPError)`
only. Never retry a 4xx.

### 10.3 Qdrant

LightRAG manages its own collections — do not create them by hand. Do
assert post-ingest that the expected collections exist and their vector
size is 1024.

---

## 11. Context budget manager

`rag_service/app/retrieval/context_budget.py` ■ — this keeps a 4B model
from drowning, and it is not optional.

### 11.1 Exact token counting

Do not estimate with character heuristics and do not use `tiktoken`
(wrong tokenizer). Use the serving model's own tokenizer:

```python
async def count_tokens(client: httpx.AsyncClient, text: str) -> int:
    """Exact token count via the serving model's own tokenizer.

    Cheap (no generation) and correct for qwen35's BPE, including the
    Kannada text in this corpus, where a chars/4 heuristic under-counts
    by 2-3x and silently blows the window.
    """
    r = await client.post("/tokenize", json={"content": text})
    r.raise_for_status()
    return len(r.json()["tokens"])
```

Cache counts keyed by `hash(text)` in a 4,096-entry LRU — the same system
prompt and chunks are counted repeatedly.

### 11.2 Budget for a 16,384-token slot

Revised from v3 for the larger GPU context **and** for reasoning tokens,
which v3 did not account for.

| Segment                        | Max tokens | Overflow policy                    |
| ------------------------------ | ---------- | ---------------------------------- |
| System prompt (static)         | 500        | Hard fail — must never grow        |
| RBAC/scope preamble (static)   | 150        | Hard fail                          |
| Cypher result block            | 2,400      | Truncate rows, keep header + top-N |
| LightRAG context               | 6,500      | Drop lowest-scored chunks first    |
| Conversation history           | 1,800      | Summarize turns older than 3       |
| Current question               | 400        | 422 if longer                      |
| **Reserved: reasoning**        | **2,048**  | Never encroached                   |
| **Reserved: answer**           | **1,024**  | Never encroached                   |
| Safety margin                  | 1,562      | Absorbs template/token drift       |
| **Total**                      | **16,384** |                                    |

If §1.3's A/B test lands on thinking disabled, reclaim the 2,048
reasoning reserve into the LightRAG context and re-run the gate.

### 11.3 Eviction order

Over budget, drop in this order, recomputing after each step:

1.  Conversation turns older than 3, replaced by a one-line summary.
2.  LightRAG chunks, lowest score first, until ≤ 6,500.
3.  Cypher rows beyond the top 40, replaced by
    `"... and N more rows (truncated)"`.
4.  Entity descriptions inside the LightRAG block, keeping names + edges.

**Never drop** the system prompt, the scope preamble, the current
question, or either generation reserve. If still over after step 4,
return 422 with `code: "CONTEXT_OVERFLOW"` and a suggestion to narrow the
query. **Do not silently truncate mid-context** — a truncated evidence
block that looks complete is exactly how a tool like this produces a
confidently wrong finding.

### 11.4 Prefix-cache discipline

llama.cpp reuses the KV cache for a common prompt prefix with
`cache_prompt: true`. Exploit it:

-   Assemble **strictly most-static first**: system prompt → scope
    preamble → format instructions → retrieved context → history →
    current question.
-   **Never** interpolate a timestamp, request ID, or UUID into the
    static segments. One varying character at position 3 invalidates the
    entire cached prefix and costs a full prefill.
-   Send `"cache_prompt": true` on every generation request.

### 11.5 Sampling per task

`rag_service/app/llm/sampling.py` ■

| Task                      | temp | top_p | top_k | thinking | n_predict |
| ------------------------- | ---- | ----- | ----- | -------- | --------- |
| Intent classification     | 0.0  | 1.0   | 1     | **off**  | 16        |
| Slot extraction           | 0.0  | 1.0   | 1     | **off**  | 96        |
| Answer synthesis          | card | card  | card  | per A/B  | 1024      |
| Offender profile summary  | card | card  | card  | per A/B  | 768       |
| History summarization     | 0.2  | 0.8   | 20    | **off**  | 160       |

"card" = the verified values from §1.6. Thinking **must** be off for the
deterministic tasks; a classifier that deliberates for 400 tokens before
emitting one label is wasting your latency budget.

---

## 12. Query execution

`POST /v1/query` on the RAG service:

```json
{
  "question": "Chain snatching linked to two-wheelers in Jayanagar since January",
  "scope": {
    "role": "INVESTIGATOR",
    "districts": ["BENGALURU_SOUTH"],
    "stations": ["JAYANAGAR_PS"],
    "user_id": "u_1042"
  },
  "conversation_id": "c_88",
  "history": [{"role": "user", "content": "..."}]
}
```

`scope` is injected by Django from the validated JWT. The RAG service
**rejects any request whose scope is absent or malformed with a 400**,
and **never** accepts a scope supplied by the browser.

**12.1 Intent classification** — constrained prompt, temperature 0,
thinking off. Returns a bare label; validate against the enum. On any
unrecognized output fall back to `FREEFORM_SEARCH` rather than retrying.

Also extract a typed slot dict: person names, stations, date range, crime
type, vehicle/phone identifiers. Validate every station against the real
40-station list from `schema_report.json`; silently discard invented ones.

**12.2 Plan** — `router/plan.py` maps `(intent, slots, scope)` to a
Cypher template ID + params, a LightRAG mode + query, whether centrality
is required, and the response shape.

**12.3 Parallel retrieval** — `asyncio.gather` the Cypher and LightRAG
calls. `asyncio.wait_for` each: 5 s Cypher, 12 s LightRAG. A timeout
degrades to the other source and is reported in metadata; it never fails
the request.

**12.4 Assembly** — apply §11. Emit the assembled token count in metadata
so the UI can show it.

**12.5 Streaming synthesis** — stream with `"stream": true`. Re-emit as
SSE with reasoning on its own channel:

```
event: reasoning
data: {"t": "The question asks about"}

event: token
data: {"t": "Between"}

event: citations
data: {"citations": [{"fir_id": "FIR-2024-0188", "chunk_id": "c_31", "score": 0.81}]}

event: graph
data: {"nodes": [...], "links": [...]}

event: warning
data: {"code": "UNSOURCED_QUANTITY", "detail": "..."}

event: meta
data: {"prompt_tokens": 9104, "reasoning_tokens": 612, "completion_tokens": 288,
       "ttft_ms": 740, "latency_ms": 5120, "mode": "hybrid", "intent": "PATTERN_SEARCH"}

event: done
data: {}
```

`citations`, `graph`, `warning` and `meta` are emitted **after** the token
stream, because validation needs the finished text.

**`tests/test_reasoning_split.py`** ■ must assert that no byte emitted on
the `reasoning` channel ever appears on the `token` channel, using a
recorded stream that contains a `<think>` block.

**12.6 Citation validation — the zero-hallucination gate**

In `answer/citations.py` ■:

1.  Compile the regex from `citation_contract.id_regex` (§5.3) — not a
    hand-written pattern — and extract every ID-shaped token from the
    **answer text only**, never from reasoning.
2.  Check each against the retrieval set (Cypher rows ∪ LightRAG chunk
    `source_id`s).
3.  Any cited ID **not** in the retrieval set:
    -   do not ship the answer as-is,
    -   emit `{"code": "UNGROUNDED_CITATION", "ids": [...]}`,
    -   strike the offending sentence and mark it
        `[removed: unverifiable reference]`.
4.  A digit-bearing quantitative claim ("47 cases", "three vehicles")
    with no Cypher result retrieved emits `{"code": "UNSOURCED_QUANTITY"}`.
5.  Log every warning to the audit trail with the prompt hash.

`tests/test_citation_validator.py` ■ must include a case with a
deliberately fabricated ID in the model output and assert suppression,
plus a case where the fabricated ID appears only inside `<think>` and
assert it is **not** flagged (reasoning is not an answer).

---

## 13. Cypher template library

`graph/cypher_templates.py` ■. **Every template is a frozen string
constant with `$`-parameters. No f-strings, no `.format()`, no
concatenation of user input into Cypher, ever.** This is both the
injection defense and the mechanism that makes "no LLM-generated Cypher"
a real guarantee rather than a claim.

Every template takes `$districts` and `$stations` and applies the scope
filter, even where it looks redundant. RBAC enforced at one layer only is
RBAC that will eventually be bypassed.

| Intent ID              | Purpose                                  |
| ---------------------- | ---------------------------------------- |
| `FIR_LOOKUP`           | One FIR with all linked entities         |
| `PERSON_PROFILE`       | All FIRs and roles for one person        |
| `PERSON_NETWORK`       | k-hop associate subgraph around a person |
| `PATTERN_SEARCH`       | FIRs by crime type + date + location     |
| `STATION_STATS`        | Counts by station over a window          |
| `CRIME_TREND`          | Time-bucketed counts by crime type       |
| `REPEAT_OFFENDERS`     | Persons accused in ≥ N FIRs              |
| `SHARED_IDENTIFIER`    | FIRs linked by phone/vehicle/account     |
| `GEO_CLUSTER`          | FIRs within a radius / locality          |
| `MODUS_OPERANDI_MATCH` | FIRs sharing MO attributes               |
| `EVIDENCE_TRAIL`       | Evidence chain for a FIR or person       |
| `FREEFORM_SEARCH`      | Fulltext fallback, no structured claim   |

Worked example — `PERSON_NETWORK`:

```python
PERSON_NETWORK = """
MATCH (p:Person {person_key: $person_key})
CALL {
  WITH p
  MATCH path = (p)-[:ASSOCIATE_OF*1..2]-(other:Person)
  RETURN path
  LIMIT 400
}
WITH p, path
UNWIND relationships(path) AS r
WITH p, r, startNode(r) AS a, endNode(r) AS b
MATCH (f:FIR {fir_id: r.source_fir})-[:REGISTERED_AT]->(s:Station)
WHERE ($districts IS NULL OR f.district IN $districts)
  AND ($stations  IS NULL OR s.station_code IN $stations)
RETURN DISTINCT
  a.person_key AS src, a.name AS src_name,
  b.person_key AS dst, b.name AS dst_name,
  r.strength   AS strength,
  r.basis      AS basis,
  r.source_fir AS source_fir
LIMIT 300
"""
```

Invariants to preserve when adapting to the real schema:

-   `LIMIT` on every template, always. An unbounded 2-hop traversal on a
    dense node hangs the demo.
-   Variable-length patterns capped at `*1..2`. `*1..3` on this graph is
    a trap.
-   Return **flat rows, never whole nodes** — flat rows serialize to far
    fewer tokens, which directly buys context budget.

`tests/test_cypher_templates.py` ■ asserts per template: no `%`, no `{`,
no `+` string ops; contains `$districts` and `$stations`; contains
`LIMIT`; and parses via `EXPLAIN` against a live Neo4j with dummy params.

### 13.1 NetworkX centrality

`graph/centrality.py` ■. Pull a subgraph via a template, build a
`networkx.Graph` in memory, compute:

-   `degree_centrality` — always
-   `betweenness_centrality` — **only when `n_nodes <= 2000`**; it is
    O(nm) and will stall the request otherwise. Above that, use
    `betweenness_centrality(G, k=min(500, n))` and label the result
    approximate in the response.
-   `eigenvector_centrality_numpy` — wrapped in try/except for
    non-convergence, falling back to degree.
-   `louvain_communities` for clustering.

Never run centrality over the whole graph on the request path.

---

## 14. Frontend and backend change control

**Yes — the idea change means both tiers change.** v3 treated the
frontend as frozen; that was based on stale state. Corrected model:

### 14.1 Step 2 obligation — inventory before touching anything

Before any edit, produce:

-   `artifacts/frontend_inventory.md` ■ — every file under
    `frontend/src/`, every API call (method, path, request shape,
    response shape as actually consumed), every component that renders
    AI output, the current SSE or fetch handling, and the
    react-force-graph data shape it expects.
-   `artifacts/backend_inventory.md` ■ — every existing Django app,
    model, view, URL, and migration; which of §4's files already exist
    and their current state.

Mark each §4 path `■` or `▲` based on that inventory. **You may not
create a file that already exists**, and you may not rewrite an existing
file wholesale when an additive change suffices.

### 14.2 Permitted frontend changes — this list is exhaustive

1.  **SSE event handling** — extend the stream consumer to the event
    types in §12.5 (`reasoning`, `token`, `citations`, `graph`,
    `warning`, `meta`, `done`). Unknown event types are ignored, not
    thrown on.
2.  **Reasoning panel** — a collapsed-by-default disclosure rendering the
    `reasoning` channel, visually distinct from the answer and labeled
    something like "model reasoning — not a finding".
3.  **Citation chips** — render `citations` as clickable chips that
    deep-link to the FIR detail view.
4.  **Warning banner** — amber banner for `UNGROUNDED_CITATION` and
    `UNSOURCED_QUANTITY`, with the offending text struck through inline.
5.  **Context meter** — show `prompt_tokens` / budget from `meta`. Small,
    unobtrusive; it is a credibility signal for judges.
6.  **Graph edge styling** — dashed edges for `SAME_NAME_AS`, with a
    legend entry "possible identity match — not confirmed".
7.  **Approximation label** — when centrality metadata says approximate,
    say so in the panel.
8.  **Removal of dead endpoints** — any component calling an endpoint
    that the LightRAG migration removes.

Anything not on this list is `□`. If you believe a ninth change is
required, emit `BLOCKED:` with the justification and stop; do not make it.

### 14.3 Permitted backend changes

1.  `intel/proxy.py` — pass through all §12.5 event types unmodified,
    including unknown ones.
2.  `audit/models.py` — add `intent`, `cypher_template_id`,
    `fir_ids_returned`, `prompt_token_count`, `reasoning_token_count`,
    `warnings`, `ttft_ms`, `latency_ms`. **Answer text stored; reasoning
    text NOT stored** — it is model deliberation, not a record.
3.  `accounts/scope.py` — scope injection into the RAG payload.
4.  Removal of any endpoint that spoke to Qdrant directly or to the old
    Graph-RAG service.

Everything else in the backend is additive.

---

## 15. DAG build order

| #  | Step                                  | Depends | Gate                                             |
| -- | ------------------------------------- | ------- | ------------------------------------------------ |
| 0  | All `VERIFY:` blocks → verification.md | —      | Every VERIFY in this doc has real output recorded |
| 1  | Schema + citation contract discovery  | —       | 1,000 records; `fir_id` 100%; `id_regex` derived |
| 2  | Frontend + backend inventory          | —       | Every §4 path marked ■ or ▲                      |
| 3  | Docker Compose skeleton (nvidia rt.)  | 0       | `docker compose config` valid; `nvidia-smi` in container |
| 4  | Neo4j up + constraints                | 3       | `SHOW CONSTRAINTS` lists all 10                  |
| 5  | Normalizer + entity resolution        | 1       | Merge rate reported and < 15%                    |
| 6  | Neo4j loader                          | 4,5     | Node/rel counts match hand-computed expectation  |
| 7  | LightRAG install + signature dump     | 3       | verification.md has real signatures              |
| 8  | Custom KG builder + ingest            | 6,7     | < 10 min; `llm_model_func` never called          |
| 9  | llama.cpp: 3 servers up + KV measured | 0,3     | `/health` 200 on 8080/8081; embed dim 1024; VRAM recorded |
| 10 | LLM client + reasoning split + tokens | 9       | `test_reasoning_split.py` green                  |
| 11 | Context budget module                 | 10      | `test_context_budget.py` green                   |
| 12 | Cypher template library               | 6       | `test_cypher_templates.py` green (EXPLAIN passes)|
| 13 | Intent router + thinking A/B          | 11,12   | ≥ 18/20 on benchmark; both A/B numbers recorded  |
| 14 | Retrieval + assembly + synthesis + SSE| 8,12,13 | `curl -N /v1/query` streams both channels        |
| 15 | Citation validator                    | 14      | `test_citation_validator.py` green               |
| 16 | Perf gate (VRAM, RAM, TTFT)           | 15      | VRAM < 13.5 GB; sys RAM < budget; p50 TTFT < 1.5 s |
| 17 | Django: accounts, fir, audit, intel   | 14      | `test_rbac_scope.py` green; login→query→stream   |
| 18 | Frontend changes per §14.2            | 17      | All 8 changes present; nothing else diffed       |
| 19 | E2E + seed users + demo script        | 18      | `test_e2e_query.py` green                        |
| 20 | README incl. §18 limitations          | 19      | All §18 items present                            |

### 15.1 Step 16 detail

`scripts/measure.sh` ■ with the stack warm:

1.  `nvidia-smi --query-gpu=memory.used --format=csv` and
    `docker stats --no-stream` → `artifacts/perf_report.json`.
2.  Fire the 20 benchmark queries sequentially, recording TTFT and total
    latency, with and without MTP.
3.  Non-zero exit if VRAM > 13.5 GB, or p50 TTFT > 1,500 ms.

If the TTFT gate fails, remedies **in this order**: (a) confirm
`--flash-attn on` actually took effect; (b) confirm `cache_prompt` is
hitting — check `/slots`; (c) disable thinking for synthesis; (d) reduce
retrieved chunks 8 → 5; (e) enable MTP; (f) only then reduce `--ctx-size`.
**Do not first reach for a smaller quant** — you have the VRAM.

### 15.2 The 20-question intent benchmark

`tests/fixtures/intent_benchmark.json` ■ — 20 realistic investigator
questions covering all 12 intents, including two deliberately ambiguous
ones that should land on `FREEFORM_SEARCH`. Accuracy ≥ 18/20. If lower,
fix the intent prompt — **do not fix it by widening the accepted
answers.**

---

## 16. Docker Compose requirements

-   `deploy.resources.reservations.devices` with `driver: nvidia`,
    `capabilities: [gpu]` on all three llama.cpp services, or the
    equivalent `runtime: nvidia`. Verify `nvidia-container-toolkit` is
    installed on the host.
-   Neo4j: `NEO4J_server_memory_heap_max__size=2G`,
    `NEO4J_server_memory_pagecache_size=2G`. At defaults Neo4j claims
    far more than §2.6 allows.
-   Named volumes: `models`, `neo4j_data`, `qdrant_storage`,
    `lightrag_data`. `models` is populated once by `make fetch-models`,
    never at container start.
-   `healthcheck` on every service and `depends_on: condition:
    service_healthy` throughout — the RAG service crashes if it starts
    before Qdrant is ready.
-   nginx must set `proxy_buffering off` and pass
    `X-Accel-Buffering: no` for the SSE route, or the stream arrives all
    at once at the end and the demo looks broken.
-   In `docker-compose.prod.yml`, only Django and nginx publish host
    ports.

---

## 17. Django specifics

-   **JWT** `HS256`, secret from env, **fail hard at startup if unset** —
    no dev default. Access 30 min, refresh 12 h. Claims: `sub`, `role`,
    `districts`, `stations`, `iat`, `exp`, `jti`. Refresh tokens stored
    hashed, single-use, rotated. Always decode with
    `algorithms=["HS256"]`; never pass
    `options={"verify_signature": False}`, including in tests.

-   **RBAC matrix:**

    | Capability             | SUPER_ADMIN | ANALYST | INVESTIGATOR | READ_ONLY |
    | ---------------------- | ----------- | ------- | ------------ | --------- |
    | Read FIRs              | all         | all     | scoped       | scoped    |
    | Natural language query | ✔           | ✔       | scoped       | scoped    |
    | Network analysis       | ✔           | ✔       | scoped       | ✘         |
    | Create/update FIR      | ✔           | ✘       | ✔ scoped     | ✘         |
    | Read audit log         | ✔           | ✔       | own only     | ✘         |
    | Manage users           | ✔           | ✘       | ✘            | ✘         |

-   **SSE proxy** — Django is synchronous; stream with
    `httpx.Client.stream` inside a generator passed to
    `StreamingHttpResponse`. Set `Cache-Control: no-cache`,
    `X-Accel-Buffering: no`, `Content-Type: text/event-stream`. Run
    gunicorn as `--worker-class gthread --threads 8 --workers 2
    --timeout 300`; the default sync worker holds a thread per stream,
    acceptable at this scale but it must be documented.

-   **Audit is append-only.** No update or delete view exists. Index on
    `(user_id, ts)` and `(ts)`.

-   **Response envelope** — match whatever `frontend_inventory.md` shows
    the frontend already consumes. If the frontend has no established
    shape, use
    `{"ok": true, "data": {...}, "meta": {...}}` /
    `{"ok": false, "error": {"code", "message", "details"}}` and record
    the decision.

---

## 18. Honest limitations — put these in the README

A government-facing tool that overstates its guarantees is worse than one
that is modest and correct.

1.  Person identity resolution merges only on strong identifiers.
    Same-name individuals are shown as *possible* matches, never merged.
    The system under-links rather than over-links, by design.
2.  The LLM never generates Cypher and never computes counts. All
    quantitative claims originate from the graph database.
3.  Model reasoning is displayed separately and is explicitly not a
    finding. It is not stored in the audit record.
4.  Centrality on subgraphs above 2,000 nodes is approximate and labeled
    as such.
5.  Handwritten Kannada OCR via PaddleOCR achieves roughly 70% character
    accuracy on this corpus. OCR is optional, non-blocking, and its
    output is always marked low-confidence.
6.  The model is multimodal but vision is not wired in v1. Evidence-photo
    and scanned-FIR analysis is a documented future path.
7.  The corpus is 1,000 FIRs. State-scale deployment (millions of FIRs)
    would require a different storage and indexing strategy and is out of
    scope.

---

## 19. When you are stuck

Emit one line beginning `BLOCKED:` with: the step number, the exact
symbol or behavior you could not verify, the command you ran, and its
output. Stop that branch and continue with any step whose dependencies
are satisfied. Do not guess, do not stub, do not silently reduce scope.
