# KSP Investigative Intelligence System

An on-premises investigative intelligence platform for Karnataka State Police:
1,000 Bengaluru FIRs become an evidentiary Neo4j crime graph plus a LightRAG
retrieval index, queried in natural language by authenticated investigators,
answered by a local Qwen3.5-4B with mechanically validated citations.

**Specification:** `ksp-iis-build-prompt-v3.1.md` is the single source of truth.
Verification evidence lives in `artifacts/verification.md`.

## Architecture (spec §2.1)

```
React :5173/:80 ──HTTPS, JWT──▶ Django :8000 (auth · RBAC · audit · SSE proxy)
                                   │ bolt (Cypher)              │ HTTP+SSE
                                   ▼                             ▼
                     Neo4j :7687 DOMAIN CRIME GRAPH    FastAPI RAG :9000
                     (evidentiary; source_fir on       (LightRAG · NetworkX ·
                      every edge)                       intent router · templates)
                                                                     │
                                             Qdrant :6333 ◀──────────┤
                                             (LightRAG vectors)      ▼
                                                    llama.cpp :8080 gen · :8081 embed · :8082 rerank
                                                    (Qwen3.5-4B Q8_0 · bge-m3 · bge-reranker, CUDA)
```

**Storage split (§2.3):** the Neo4j domain graph is *evidentiary* — provably
derived from FIR records, every edge traces to the FIR that created it. The
LightRAG KG (NetworkX, in-process) is a *retrieval index* — allowed to be
lossy. Qdrant holds LightRAG's vectors. Different guarantees, different
stores; Neo4j's native vector index is deliberately unused.

**Hard boundary (§2.1):** Django never talks to Qdrant or llama.cpp and never
builds a prompt. Numbers always come from Cypher; narrative from LightRAG.

## Quick start (16 GB VRAM CUDA host)

```bash
cp .env.example .env            # fill the secrets — services fail hard without them
make fetch-models               # Qwen3.5-4B Q8_0 (4.62 GB) + bge-m3 + bge-reranker
make config                     # compose validation gate
make build && make up
make migrate && make seed
make constraints                # Neo4j constraints (Step 4 gate)
make ingest                     # Neo4j load + deterministic LightRAG KG (Steps 6+8)
make measure                    # perf gate: VRAM < 13.5 GB, p50 TTFT < 1.5 s (Step 16)
```

Frontend dev server: `cd frontend && npm install && npm run dev` (:5173 with
an `/api` proxy to Django :8000). Production: `docker compose -f
docker-compose.yml -f docker-compose.prod.yml up -d` (nginx serves the built
frontend; only Django and nginx publish host ports).

Default accounts (seed command, password `Admin@1234`): `admin@crime.local`
(SUPER_ADMIN), `analyst@crime.local` (ANALYST), `officer@crime.local`
(INVESTIGATOR, district-scoped), `viewer@crime.local` (READ_ONLY,
district-scoped).

## Tests (§15 gates)

```bash
python3 tests/test_schema_contract.py      # Step 1 — dataset unchanged
python3 tests/test_context_budget.py      # Step 11 — §11 budget rules
python3 tests/test_cypher_templates.py    # Step 12 — frozen templates (+EXPLAIN live)
python3 tests/test_reasoning_split.py      # Step 10 — reasoning never leaks into answers
python3 tests/test_citation_validator.py   # Step 15 — zero-hallucination gate
python3 tests/test_rbac_scope.py          # Step 17 — scope injection
python3 tests/test_e2e_query.py           # Step 19 — login → query → stream (stack required)
```

## Honest limitations (spec §18)

A government-facing tool that overstates its guarantees is worse than one
that is modest and correct.

1. **Identity resolution under-links by design.** Person records merge only
   on strong identifiers (government ID, phone, or exact name + date of
   birth). This corpus carries none of those, so the merge rate is exactly
   0%. Same-name individuals appear as dashed `SAME_NAME_AS` edges labeled
   *possible identity match — not confirmed* — never as merges (§5.6, §18.1).
2. **The LLM never generates Cypher and never computes counts.** Every
   quantitative claim originates from the Neo4j graph via frozen,
   parameterized templates; a count the retrieval did not supply triggers an
   `UNSOURCED_QUANTITY` warning instead of an answer (§10.1, §12.6).
3. **Model reasoning is displayed separately and is explicitly not a
   finding.** It is streamed on its own `reasoning` channel, excluded from
   citation validation, and never stored in the audit log — only its token
   count is (§1.3).
4. **Centrality on subgraphs above 2,000 nodes is approximate** (sampled
   betweenness, k ≤ 500) and is labeled as such in the UI (§13.1, §14.2-7).
5. **`fir_id` alone is not a unique record key** in this corpus (700 unique
   values across 1,000 FIRs; 5 exact (id, station) duplicates). Identity in
   the graph is the composite `fir_key = <fir_id>@<STATION_CODE>`; citations
   key off the citable `fir_id` with the station rendered alongside
   (artifacts/schema_report.json → citation_contract).
6. **The model is multimodal but vision is not wired in v1.** A verified
   `mmproj-Qwen_Qwen3.5-4B-f16.gguf` exists; evidence-photo and scanned-FIR
   analysis is a documented future path (§1.4).
7. **Corpus scale is 1,000 FIRs.** State-scale deployment (millions of FIRs)
   needs a different storage and indexing strategy and is out of scope (§18.7).
8. **Indexing is provably LLM-free.** The knowledge graph is built
   deterministically from the structured JSON (`insert_custom_kg`) — the
   `INDEXING_IN_PROGRESS` guard makes any indexing-time LLM call raise, and
   the ingest gate asserts the counter stayed at zero (§2.2, §9).

## Repository map

```
data/                        □ FIR dataset — source of truth (1,000 records, 40 stations)
artifacts/                   generated, committed: verification.md, schema_report.json,
                             frontend/backend inventories, ingest + perf reports
rag_service/                 FastAPI RAG (§9–§15): app/{llm,retrieval,graph,router,answer,routes}
                             ingest/{discover_schema, normalize, load_neo4j, build_custom_kg, run_ingest}
backend/                     Django 4.2 (§17): accounts (JWT+RBAC), fir, audit, intel proxy
frontend/                    React/Vite (§14.2 changes 1–8 applied; rest is change-controlled)
infra/                       llamacpp (b9222 CUDA build + 3 server scripts), neo4j constraints, nginx
tests/                       §15 gate suites + fixtures/intent_benchmark.json (20 questions)
scripts/measure.sh           Step 16 perf gate
```
