# crime-intelligence-platform

## Architecture

```
React (frontend/)  →  Django :8000  →  Graph-RAG :9000  →  inference :8080 (Qwen2.5-4B Q8_0)
                           ↑                      ↓
                      PostgreSQL            Neo4j :7687
                                           (graph + native vector index)
```

**Boundary rules:**
- React calls Django only. Never calls graph-rag or inference directly.
- Django calls graph-rag only. Django never touches Neo4j.
- graph-rag calls inference for (a) intent classification, (b) grounded summarization. Embedding is in-process (BAAI/bge-m3).
- The LLM never writes or executes Cypher — it only classifies intents via structured JSON. All Cypher is static and parameterized.

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (for Django)
- Neo4j 5.23 (local instance — Desktop app or `docker run neo4j:5.23`)
- For inference: Linux/WSL2 + CUDA-capable GPU (Qwen2.5-4B Q8_0 ≈ 4 GB VRAM)

## Quick Start

No Docker Compose orchestration. Run each service in its own terminal.

### 1. Neo4j (single local instance)

```
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/changeme neo4j:5.23
```

### 2. inference/ — llama.cpp + Qwen2.5-4B-Instruct Q8_0

```
cd inference
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
bash scripts/build_llamacpp.sh   # requires C++ toolchain + CUDA
bash scripts/download_model.sh   # downloads qwen2.5-4B-Instruct-Q8_0.gguf
python -m server.llama_server    # start llama.cpp on :8080
```

**Windows note:** inference build scripts are bash (target WSL2). For native Windows, use WSL or build llama.cpp manually with MSVC/CUDA.

The proxy at `inference/server/api.py` wraps llama-server with ./v1/chat/completions (OpenAI-compatible), /health, /metrics. Zero-hallucination enforce temperature Cap at 0.5 without X-Allow-Creative header.

### 3. graph-rag/ — FastAPI Graph-RAG service

```
cd graph-rag && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/setup_neo4j_schema.py
python scripts/ingest_firs.py --input ../data/bengaluru_40ps_1000_firs.json
uvicorn app.main:app --host 0.0.0.0 --port 9000
```

Endpoints: `POST /api/v1/query/stream` (SSE), `POST /api/v1/query/sync`, `GET /api/v1/subgraph/{fir_id}`.

### 4. backend/ — Django

```
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py create_default_users
python manage.py import_fir_json --file ../data/bengaluru_40ps_1000_firs.json
python manage.py runserver 8000
```

Default accounts (password `Admin@1234`):
- admin@crime.local (SUPER_ADMIN)
- analytics@crime.local (ANALYST)
- officer@crime.local (INVESTIGATOR)
- viewer@crime.local (READ_ONLY)

### 5. frontend/ — Vite + React

```
cd frontend && npm install && npm run dev
```

## Env Vars

| Service | File | Key vars |
|---|---|---|
| inference/ | .env.example | MODEL_PATH, TEMPERATURE=0.0, HOST/PORT |
| graph-rag/ | .env.example | NEO4J_URI, NEO4J_PASSWORD, LLM_BASE_URL, EMBED_MODEL |
| backend/ | .env.example | SECRET_KEY, JWT_SECRET, DB_*, GRAPH_RAG_URL, CORS_ALLOWED_ORIGINS |

## Quality Gates

- **inference:** POST /health → 200 within 60s; same prompt + temp=0.0 → identical output ×10
- **graph-rag:** GET /health → 200 within 2s; intent classifier routes 10 varied queries; empty results → no_context_event (zero LLM calls); /subgraph/{fir_id} returns force-graph JSON with centrality + communities
- **backend:** POST /api/llm/graph/query/ → SSE relay; GraphQuery row saved per request
- **frontend:** NetworkGraph renders from live subgraph endpoint; CrimeMap places FIR markers on leaflet; Analytics shows bar/pie/month chart from /firs/stats/