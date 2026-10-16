# AGENT.md — KSP Investigative Intelligence System

**Authority:** `ksp-iis-build-prompt-v3.1.md` is the single source of truth and the only architecture spec. Read it in full before writing any code. Where this repo's existing code contradicts it, **the spec wins**. This file is a map to the spec and the tooling — not a substitute for either.

## Mission

An on-premises investigative intelligence platform for Karnataka State Police: 1,000 Bengaluru FIRs become an evidentiary Neo4j crime graph plus a LightRAG retrieval index, queried in natural language by Django-authenticated investigators, answered by a local Qwen3.5-4B with mechanically validated citations. Non-negotiables: zero LLM at index time, zero LLM-generated Cypher, zero unsourced numbers, reasoning never shown as findings, everything runs on one 16 GB-VRAM box.

## Skills and MCP servers actually available

| Tool | Use it for |
|---|---|
| **Skill: graphify** | Build/query a `.graphify/` knowledge graph of this codebase; codebase & architecture questions |
| **Skill: context7-mcp** | Fetch current docs for any library (Django, FastAPI, LightRAG, llama.cpp) before coding against it |
| **Skill: ai-sdk** | AI SDK / streaming / tool-calling questions (rare here) |
| **Skill: research** | Investigate high-trust primary sources, capture findings as repo Markdown |
| **Skill: firecrawl-deep-research** | Cited multi-source analytical reports (model cards, llama.cpp release notes) |
| **Skill: pdf / docx / pptx** | Read or produce PDF/Word/PowerPoint artifacts (README, demo decks) |
| **Skill: ai-research-explore** | ML research candidate exploration (out of scope for this build) |
| **Skill: customize-opencode** | Editing opencode's own config — never app code |
| **neo4j MCP** | Live Cypher read/write on local Neo4j: verify constraints, counts, `EXPLAIN` templates |
| **docker-mcp MCP** | Inspect/list/start/stop/restart containers, read logs — stack health gates |
| **serena MCP (LSP)** | Symbol-aware navigation: `find_symbol`, `find_referencing_symbols`, `get_diagnostics_for_file` (pyright/typescript) instead of grep |
| **playwright MCP** | Browser verification of the React UI: flows, screenshots, UI regressions |
| **shadcn MCP** | Pull pre-validated UI components when wiring frontend changes |
| **gh_grep MCP** | Real-world usage examples from public GitHub (e.g. `insert_custom_kg` signatures) |
| **filesystem MCP** | File tree/list/read outside workspace boundary |
| **sequential_thinking MCP** | Step-by-step plans for complex refactors/debugging |
| **headroom MCP** | Compress/retrieve large tool outputs to manage context |
| **memory MCP** | Cross-session knowledge-graph persistence (use `DOCMIND-*` prefixed entities) |
| Built-ins | `bash`, `read`/`write`/`edit`, `glob`/`grep`, `webfetch`, `task` (subagents), `todowrite`, `question` |

*Context7 is named in the global AGENTS.md; if its tools are not exposed in the current session, use `webfetch` + `gh_grep` instead of guessing.*

## Hard rules (spec §0 — non-negotiable)

1. **No stubs.** Every file complete and runnable. No `TODO`, no `pass # later`, no "rest unchanged".
2. **No invented APIs.** Import only symbols verified in the pinned versions (§3). Every `VERIFY:` must be run, with real output pasted into `artifacts/verification.md`, **before** writing dependent code. On failure emit `BLOCKED:` — never silently substitute.
3. **No invented data fields.** All field names come from `artifacts/schema_report.json` (via `ingest/_schema_constants.py`). Fields <20% present are `sparse` — never defaulted.
4. **Fail loud.** No `except: pass`, no mock fallbacks. Typed errors → 503 with machine-readable code.
5. **File notation** on everything touched: `■` new file · `▲` modified (state rationale first) · `□` read-only.
6. **DAG order** (§15). Never start a step whose dependencies haven't passed their gate. Each step ends with a runnable gate command and its real output.
7. **Frontend is change-controlled** (§14.2): only the 8 enumerated changes; anything else is `□`. A needed ninth change → `BLOCKED:` + justification.
8. **Zero-hallucination at runtime** (§12.6): every answer's citations mechanically validated against the retrieval set; offenders struck, not shipped.
9. **On-premises only.** No runtime external hosts, no cloud inference, no telemetry.

**`BLOCKED:` format** — one line: step number, the exact symbol/behavior you could not verify, the command you ran, its output. Stop that branch; continue steps whose dependencies are satisfied. Do not guess, do not stub, do not silently reduce scope.

## Architecture in one screen

```
React :5173/:80 ──HTTPS, JWT──▶ Django :8000 (auth·RBAC·audit·SSE proxy)
                                   │ bolt (Cypher)              │ HTTP+SSE
                                   ▼                             ▼
                     Neo4j :7687 DOMAIN CRIME GRAPH    FastAPI RAG :9000
                     (evidentiary, source_fir on        (LightRAG·NetworkX·intent
                      every edge)                       router·Cypher templates)
                                                                    │
                                             Qdrant :6333 ◀─────────┤
                                             (LightRAG vectors)     ▼
                                                    llama.cpp :8080 gen · :8081 embed · :8082 rerank
                                                    (Qwen3.5-4B Q8_0 · bge-m3 · bge-reranker, CUDA)
```

**Storage split rationale** (§2.3): the Neo4j domain graph is *evidentiary* — provably derived from FIR records, every edge traceable via `source_fir`. The LightRAG KG (NetworkX, in-process) is a *retrieval index* — allowed to be lossy. Qdrant holds LightRAG's vectors. Different guarantees → different stores. Pointing LightRAG at Neo4j risks a label-namespace collision (Community = one DB); **Neo4j's native vector index is dropped from the design**. Django never talks to Qdrant, llama.cpp, or prompts — it authenticates, authorizes, audits, scopes, proxies.

## Repo state snapshot (audited 2026-09-22; full plan in spec §15 DAG)

- **Verified data facts:** `fir_id` format is `^\d+/\d{4}$` and **not unique** (700/1000; composite `(fir_id, police_station)` leaves 5 dupes) — Step 1's citation contract must handle this. Only narrative field: `incident_details.truth_of_incident`. `known_associates` are scalar name strings. 40 stations, all `Bengaluru Urban`.
- **Legacy v2 code present (superseded):** `graph-rag/` (LangChain + Neo4j vector index + in-process bge-m3 — replaced by `rag_service/` per §2.2), `inference/` (wrong model filename, unpinned llama.cpp, hand-written `chatml` template), `backend/` (Postgres FIR source-of-truth, no scope injection, JWT without jti/rotation), frontend (mock chat, fake login, no SSE consumer, no vite proxy).
- **Not started:** everything in spec §15 Steps 0–20 that isn't listed above — incl. `artifacts/`, `rag_service/`, `docker-compose*.yml`, `Makefile`, root `.env.example`, `infra/` (llama.cpp scripts, neo4j constraints, nginx), spec's `tests/`, `scripts/measure.sh`, README §18 limitations.
- **Repo hygiene:** `backend/venv` (6,704 files) and parts of `frontend/node_modules` + `dist.zip` are committed; no `.gitignore` exists.
